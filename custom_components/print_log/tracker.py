"""Follows the entities of each printer and logs a print when it ends."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import EVENT_PRINT_FINISHED
from .data import PrintLogData
from .helpers import map_state, pretty_name, to_kwh, to_meters, to_percent, to_seconds, to_float

_LOGGER = logging.getLogger(__name__)
END_STATUS = {"complete": "complete", "cancelled": "cancelled", "error": "error", "idle": "cancelled"}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PrinterTracker:
    def __init__(self, hass: HomeAssistant, data: PrintLogData, printer: dict) -> None:
        self.hass, self.data, self.p = hass, data, printer
        self.key = f"session_{printer['id']}"
        self.session: dict | None = None
        self._unsub = None
        self._persisted = 0.0

    def _state(self, entity: str | None):
        return self.hass.states.get(entity) if entity else None

    async def async_start(self) -> None:
        self.session = await self.hass.async_add_executor_job(self.data.store.get_setting, self.key)
        ids = [self.p[k] for k in ("state_entity", "filename_entity", "filament_entity", "progress_entity",
                                   "remaining_entity") if self.p.get(k)]
        self._unsub = async_track_state_change_event(self.hass, ids, self._handle)
        st = self._state(self.p["state_entity"])
        if st and map_state(st.state, self.p["state_map"]) == "printing" and not self.session:
            self._begin()

    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        self._persist(force=True)

    def _persist(self, force: bool = False) -> None:
        if not force and time.monotonic() - self._persisted < 60:
            return
        self._persisted = time.monotonic()
        self.hass.async_add_executor_job(self.data.store.set_setting, self.key, self.session)

    def _length(self, state) -> float | None:
        return to_meters(state.state, state.attributes.get("unit_of_measurement"), self.p["length_unit"]) if state else None

    def _energy(self) -> float | None:
        st = self._state(self.p.get("energy_entity"))
        return to_kwh(st.state, st.attributes.get("unit_of_measurement")) if st else None

    def _percent(self) -> float | None:
        st = self._state(self.p.get("progress_entity"))
        return to_percent(st.state, st.attributes.get("unit_of_measurement")) if st else None

    def _remaining(self) -> float | None:
        st = self._state(self.p.get("remaining_entity"))
        return to_seconds(st.state, st.attributes.get("unit_of_measurement")) if st else None

    def _begin(self) -> None:
        fst = self._state(self.p.get("filename_entity"))
        self.session = {
            "started_at": _iso(datetime.now(timezone.utc)),
            "filename": fst.state if fst and fst.state not in ("unknown", "unavailable") else "",
            "length_m": self._length(self._state(self.p.get("filament_entity"))) or 0.0,
            "energy_start": self._energy(), "percent": 0.0,
        }
        self._persist(force=True)
        self.hass.async_create_task(self._notify_progress(force=True))
        self.hass.async_create_task(self._capture_thumb(5))

    async def _notify_progress(self, force: bool = False) -> None:
        if not self.session or not self.data.notifier:
            return
        pct = self._percent()
        if pct is not None:
            self.session["percent"] = pct
        await self.data.notifier.progress(self.p, pretty_name(self.session["filename"]), self.session["percent"],
                                          self._remaining(), force=force)

    # ---------- thumbnails ----------
    async def _grab_thumb(self) -> str | None:
        """Fetch the printer's thumbnail camera image and store it. Returns the file name, or None."""
        entity, store = self.p.get("thumbnail_entity"), self.data.store
        if not entity or not hasattr(store, "save_thumbnail"):
            return None
        try:
            from homeassistant.components.camera import async_get_image
            image = await async_get_image(self.hass, entity, timeout=10)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("No thumbnail available from %s", entity, exc_info=True)
            return None
        return await self.hass.async_add_executor_job(store.save_thumbnail, image.content, image.content_type)

    def _drop_thumb(self, name: str | None) -> None:
        path = self.data.store.thumbnail_path(name) if name and hasattr(self.data.store, "thumbnail_path") else None
        if path:
            path.unlink(missing_ok=True)

    async def _capture_thumb(self, delay: float = 0) -> None:
        """Keep the newest thumbnail of the running print (the file name entity can change a moment after the start)."""
        session = self.session
        if not session or not self.p.get("thumbnail_entity"):
            return
        if delay:
            await asyncio.sleep(delay)
        if self.session is not session:
            return
        name = await self._grab_thumb()
        if not name:
            return
        if self.session is not session:
            await self.hass.async_add_executor_job(self._drop_thumb, name)
            return
        old, session["thumb"] = session.get("thumb"), name
        self._persist(force=True)
        if old:
            await self.hass.async_add_executor_job(self._drop_thumb, old)

    @callback
    def _handle(self, event: Event) -> None:
        entity, new = event.data["entity_id"], event.data.get("new_state")
        if new is None:
            return
        if entity == self.p.get("state_entity"):
            mapped = map_state(new.state, self.p["state_map"])
            if mapped == "printing" and not self.session:
                self._begin()
            elif self.session and mapped in END_STATUS:
                self.hass.async_create_task(self._finish(END_STATUS[mapped]))
            elif self.session and mapped == "paused":
                self.hass.async_create_task(self._notify_progress(force=True))
        elif not self.session:
            return
        elif entity == self.p.get("filament_entity"):
            length = self._length(new)
            if length is not None and length > self.session["length_m"]:
                self.session["length_m"] = length
                self._persist()
        elif entity == self.p.get("filename_entity") and new.state not in ("unknown", "unavailable", ""):
            self.session["filename"] = new.state
            self._persist(force=True)
            self.hass.async_create_task(self._capture_thumb(3))
        elif entity in (self.p.get("progress_entity"), self.p.get("remaining_entity")):
            self.hass.async_create_task(self._notify_progress())

    async def _finish(self, status: str) -> None:
        session, self.session = self.session, None
        if not session:
            return
        store, ended = self.data.store, datetime.now(timezone.utc)
        await self.hass.async_add_executor_job(store.set_setting, self.key, None)
        kwh = None
        end_energy = self._energy()
        if session.get("energy_start") is not None and end_energy is not None and end_energy >= session["energy_start"]:
            kwh = round(end_energy - session["energy_start"], 4)
        percent = 100.0 if status == "complete" else session.get("percent", 0.0)
        if not session.get("thumb"):
            session["thumb"] = await self._grab_thumb()

        def _create():
            settings = store.get_settings()
            printer = next((r for r in store.list_table("printers") if r["id"] == self.p["id"]), self.p)
            row = {"filename": session["filename"], "status": status, "source": "auto", "printer_id": self.p["id"],
                   "started_at": session["started_at"], "ended_at": _iso(ended),
                   "length_m": round(session["length_m"], 3), "length_auto_m": round(session["length_m"], 3),
                   "person_id": printer.get("current_person_id"), "role_id": printer.get("current_role_id"),
                   "filament_id": printer.get("current_filament_id"), "energy_kwh": kwh,
                   "thumbnail": session.get("thumb")}
            price = None
            if kwh is not None:
                ent = settings.get("energy_price_entity")
                est = self.hass.states.get(ent) if ent else None
                value = to_float(est.state) if est else None
                price = int(round(value * 1_000_000)) if value is not None else settings.get("energy_price_micro", 0)
                row["energy_price_micro"] = price
            return store.add_print(row)

        try:
            row = await self.hass.async_add_executor_job(_create)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Could not log print")
            await self.hass.async_add_executor_job(self._drop_thumb, session.get("thumb"))
            return
        self.hass.bus.async_fire(EVENT_PRINT_FINISHED, {"id": row["id"], "filename": row["filename"], "status": status,
                                                         "printer": self.p["name"], "incomplete": row["incomplete"]})
        await self.data.async_refresh()
        if self.data.notifier:
            await self.data.notifier.finished(self.p, status, {
                "filename": pretty_name(row["filename"]), "percent": int(percent), "length": round(row["length_m"], 1),
                "cost": f"EUR {row['total_cost']:.2f}", "person": row["person"], "filament": row["filament"]})
        await self._check_low_stock()

    async def _check_low_stock(self) -> None:
        store = self.data.store
        if not hasattr(store, "low_stock_check"):
            return
        try:
            rolls = await self.hass.async_add_executor_job(store.low_stock_check)
            if rolls and self.data.notifier:
                await self.data.notifier.low_stock(rolls)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Low stock check failed")


class PrinterManager:
    def __init__(self, hass: HomeAssistant, data: PrintLogData) -> None:
        self.hass, self.data = hass, data
        self.trackers: dict[int, PrinterTracker] = {}

    async def async_reload(self) -> None:
        self.async_stop()
        printers = await self.hass.async_add_executor_job(self.data.store.list_table, "printers", False)
        for p in printers:
            if not p.get("state_entity"):
                continue
            tracker = PrinterTracker(self.hass, self.data, p)
            await tracker.async_start()
            self.trackers[p["id"]] = tracker

    def async_stop(self) -> None:
        for t in self.trackers.values():
            t.async_stop()
        self.trackers.clear()
