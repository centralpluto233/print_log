"""Runtime data shared between platforms."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import SIGNAL_UPDATED
from .store import Store


class PrintLogData:
    def __init__(self, hass: HomeAssistant, store: Store) -> None:
        self.hass = hass
        self.store = store
        self.summary: dict = {"prints": 0, "total_cost": 0.0, "length_m": 0.0, "last": None}
        self.settings: dict = {}
        self.manager = None
        self.notifier = None

    async def async_refresh(self, reload: bool = False) -> None:
        """Refresh summary sensors. With reload=True also re-read settings and restart the printer trackers."""
        self.summary = await self.hass.async_add_executor_job(self.store.summary)
        if reload:
            self.settings = await self.hass.async_add_executor_job(self.store.get_settings)
            if self.manager:
                await self.manager.async_reload()
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)
