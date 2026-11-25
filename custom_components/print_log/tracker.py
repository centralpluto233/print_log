"""Follows the Moonraker entities and logs a print when it ends."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_FILAMENT_ENTITY, CONF_FILENAME_ENTITY, CONF_LENGTH_UNIT, CONF_STATE_ENTITY,
    END_STATES, EVENT_PRINT_FINISHED, UNIT_FACTORS,
)
from .data import PrintLogData

_LOGGER = logging.getLogger(__name__)
_BAD = (STATE_UNKNOWN, STATE_UNAVAILABLE, None, "")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PrintTracker:
    def __init__(self, hass: HomeAssistant, data: PrintLogData, conf: dict) -> None:
        self.hass = hass
        self.data = data
        self.state_id = conf[CONF_STATE_ENTITY]
        self.file_id = conf.get(CONF_FILENAME_ENTITY)
        self.fil_id = conf.get(CONF_FILAMENT_ENTITY)
        self.default_unit = conf.get(CONF_LENGTH_UNIT, "mm")
        self.session: dict | None = None
        self._unsub = None

    async def async_start(self) -> None:
        self.session = await self.hass.async_add_executor_job(self.data.store.get_setting, "session")
        ids = [e for e in (self.state_id, self.file_id, self.fil_id) if e]
        self._unsub = async_track_state_change_event(self.hass, ids, self._handle)
        st = self.hass.states.get(self.state_id)
        if st and st.state == "printing" and not self.session:
            self._begin()

    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()

    def _persist(self) -> None:
        self.hass.async_add_executor_job(self.data.store.set_setting, "session", self.session)

    def _length_m(self, state) -> float | None:
        if state is None or state.state in _BAD:
            return None
        try:
            value = float(state.state)
        except ValueError:
            return None
        unit = state.attributes.get("unit_of_measurement") or self.default_unit
        return value * UNIT_FACTORS.get(unit, UNIT_FACTORS[self.default_unit])

    def _begin(self) -> None:
        fst = self.hass.states.get(self.file_id) if self.file_id else None
        lst = self.hass.states.get(self.fil_id) if self.fil_id else None
        self.session = {
            "started_at": _iso(datetime.now(timezone.utc)),
            "filename": fst.state if fst and fst.state not in _BAD else "",
            "length_m": self._length_m(lst) or 0.0,
        }
        self._persist()

    @callback
    def _handle(self, event: Event) -> None:
        entity = event.data["entity_id"]
        new = event.data.get("new_state")
        if new is None:
            return
        if entity == self.fil_id and self.session:
            length = self._length_m(new)
            if length is not None and length > self.session["length_m"]:
                self.session["length_m"] = length
                self._persist()
        elif entity == self.file_id and self.session and new.state not in _BAD:
            self.session["filename"] = new.state
            self._persist()
        elif entity == self.state_id:
            state = (new.state or "").lower()
            if state == "printing" and not self.session:
                self._begin()
            elif self.session and (state in END_STATES or state == "standby"):
                self.hass.async_create_task(self._finish(END_STATES.get(state, "cancelled")))

    async def _finish(self, status: str) -> None:
        session, self.session = self.session, None
        if not session:
            return
        await self.hass.async_add_executor_job(self.data.store.set_setting, "session", None)
        ended = datetime.now(timezone.utc)
        store = self.data.store

        def _create():
            s = store.get_settings()
            return store.add_print({
                "filename": session["filename"], "status": status, "source": "auto",
                "started_at": session["started_at"], "ended_at": _iso(ended),
                "length_m": round(session["length_m"], 3), "length_auto_m": round(session["length_m"], 3),
                "person_id": s.get("current_person_id"), "role_id": s.get("current_role_id"),
                "filament_id": s.get("current_filament_id"),
            })

        try:
            row = await self.hass.async_add_executor_job(_create)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Could not log print")
            return
        self.hass.bus.async_fire(EVENT_PRINT_FINISHED, {"id": row["id"], "filename": row["filename"], "status": status,
                                                         "incomplete": row["incomplete"]})
        await self.data.async_refresh()
