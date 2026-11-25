"""Summary sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED
from .data import PrintLogData

SENSORS = (
    ("total_prints", "Total prints", None, SensorStateClass.TOTAL, "mdi:printer-3d", lambda s: s["prints"]),
    ("total_cost", "Total cost", "EUR", SensorStateClass.TOTAL, "mdi:currency-eur", lambda s: s["total_cost"]),
    ("total_length", "Total filament used", "m", SensorStateClass.TOTAL, "mdi:ruler", lambda s: s["length_m"]),
    ("last_print", "Last print", None, None, "mdi:file-clock", lambda s: (s["last"] or {}).get("filename") or None),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    data: PrintLogData = hass.data[DOMAIN][entry.entry_id]["data"]
    async_add_entities(PrintLogSensor(entry, data, *s) for s in SENSORS)


class PrintLogSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry, data, key, name, unit, state_class, icon, getter) -> None:
        self._data, self._getter = data, getter
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name="Print Log")

    @property
    def native_value(self):
        return self._getter(self._data.summary)

    @property
    def extra_state_attributes(self):
        last = self._data.summary.get("last")
        if self._attr_unique_id.endswith("last_print") and last:
            return {k: last.get(k) for k in ("person", "role", "filament", "status", "length_m", "total_cost", "ended_at")}
        return None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._refresh))

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()
