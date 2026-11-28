"""Companion-app notifications: one progress notification that is updated in place (same tag)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .data import PrintLogData
from .defaults import DEFAULT_NOTIFICATIONS, TEXTS
from .helpers import fmt_duration, render

_LOGGER = logging.getLogger(__name__)
ICON = "mdi:printer-3d"


class Notifier:
    def __init__(self, hass: HomeAssistant, data: PrintLogData) -> None:
        self.hass, self.data = hass, data
        self._last: dict[int, tuple[float, float]] = {}

    @property
    def cfg(self) -> dict:
        return {**DEFAULT_NOTIFICATIONS, **(self.data.settings.get("notifications") or {})}

    def _lang(self) -> str:
        lang = (self.hass.config.language or "en")[:2]
        return lang if lang in TEXTS else "en"

    def text(self, key: str) -> str:
        return self.cfg.get(key) or TEXTS[self._lang()][key]

    @staticmethod
    def tag(printer: dict) -> str:
        return f"print_log_{printer['id']}"

    def _targets(self) -> list[str]:
        out = []
        for t in self.cfg["targets"]:
            name = t.split(".", 1)[1] if t.startswith("notify.") else t
            if name:
                out.append(name)
        return out

    async def _send(self, message: str, title: str | None = None, data: dict | None = None) -> None:
        payload: dict[str, Any] = {"message": message}
        if title:
            payload["title"] = title
        if data:
            payload["data"] = data
        for target in self._targets():
            try:
                await self.hass.services.async_call("notify", target, payload, blocking=False)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Notification to notify.%s failed", target, exc_info=True)

    def _ctx(self, printer: dict, **kw) -> dict[str, Any]:
        unknown = TEXTS[self._lang()]["unknown"]
        ctx = {"printer": printer["name"], "filename": "", "percent": 0, "remaining": "?", "person": unknown,
               "filament": unknown, "length": 0, "cost": "", "status": ""}
        ctx.update({k: v for k, v in kw.items() if v is not None})
        return ctx

    async def progress(self, printer: dict, filename: str, pct: float, remaining_s: float | None,
                       force: bool = False) -> None:
        c = self.cfg
        if not (c["enabled"] and c["progress"] and self._targets()):
            return
        now, pct_i = time.monotonic(), int(pct)
        last = self._last.get(printer["id"])
        if not force and last:
            if pct_i == last[0] or pct_i - last[0] < c["min_step_pct"] and pct_i < 100 or now - last[1] < c["min_interval_s"]:
                return
        self._last[printer["id"]] = (pct_i, now)
        ctx = self._ctx(printer, filename=filename, percent=pct_i,
                        remaining=fmt_duration(remaining_s) if remaining_s is not None else "?")
        data = {"tag": self.tag(printer), "progress": pct_i, "progress_max": 100, "sticky": "true",
                "alert_once": True, "channel": "Print progress", "importance": "low", "notification_icon": ICON}
        if c["live_update"]:
            data["live_update"] = True
        await self._send(render(self.text("progress_message"), ctx), render(self.text("progress_title"), ctx), data)

    async def finished(self, printer: dict, status: str, ctx_in: dict) -> None:
        self._last.pop(printer["id"], None)
        c = self.cfg
        if not self._targets():
            return
        if not (c["enabled"] and c.get(f"on_{status}", True)):
            await self.clear(printer)
            return
        ctx = self._ctx(printer, status=status, **ctx_in)
        data = {"tag": self.tag(printer), "channel": "Print finished", "notification_icon": ICON}
        await self._send(render(self.text(f"{status}_message"), ctx), render(self.text(f"{status}_title"), ctx), data)
        if c["clear_after_min"] > 0:
            async_call_later(self.hass, c["clear_after_min"] * 60,
                             lambda _now: self.hass.async_create_task(self.clear(printer)))

    async def low_stock(self, rolls: list[dict]) -> None:
        """One notification per roll that just dropped below the limit. Can be switched off in the settings."""
        c = self.cfg
        if not (c["enabled"] and c.get("on_low_stock", True) and self._targets()):
            return
        limit = self.data.settings.get("low_stock_m")
        for roll in rolls:
            ctx = {"filament": roll.get("name") or "", "remaining": round(roll.get("remaining_m") or 0, 1),
                   "limit": limit if limit is not None else ""}
            await self._send(render(self.text("low_stock_message"), ctx), render(self.text("low_stock_title"), ctx),
                             {"tag": f"print_log_low_{roll['id']}", "channel": "Filament stock", "notification_icon": ICON})

    async def clear(self, printer: dict) -> None:
        await self._send("clear_notification", None, {"tag": self.tag(printer)})

    async def test(self) -> None:
        """Send a fake progress notification that is updated in place, then a finished message."""
        printer = {"id": 0, "name": "Test"}
        for pct in (10, 45, 80):
            await self.progress(printer, "test print", pct, (100 - pct) * 60, force=True)
            await asyncio.sleep(4)
        await self.finished(printer, "complete", {"filename": "test print", "percent": 100, "length": 12.3,
                                                  "cost": "EUR 0.50", "person": "Test", "filament": "Test"})
