"""Print Log: log 3D prints from Moonraker per person and filament roll."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .api import async_register_views
from .const import DOMAIN, PANEL_URL, STATIC_URL, VERSION
from .data import PrintLogData
from .store import Store
from .tracker import PrintTracker

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

ADD_PRINT_SCHEMA = vol.Schema({
    vol.Required("length_m"): vol.Coerce(float),
    vol.Optional("filename", default=""): str,
    vol.Optional("person"): str,
    vol.Optional("filament"): str,
    vol.Optional("role"): str,
    vol.Optional("status", default="complete"): vol.In(["complete", "cancelled", "error"]),
    vol.Optional("notes"): str,
})
SET_CURRENT_SCHEMA = vol.Schema({
    vol.Optional("person"): vol.Any(None, str),
    vol.Optional("filament"): vol.Any(None, str),
    vol.Optional("role"): vol.Any(None, str),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = Store(hass.config.path("print_log", "prints.db"), hass.config.time_zone)
    await hass.async_add_executor_job(store.init)
    legacy = Path(hass.config.path("prints.db"))
    if legacy.exists():
        try:
            n = await hass.async_add_executor_job(store.import_legacy, legacy)
            if n:
                _LOGGER.info("Imported %s prints from the old prints.db", n)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Import of the old prints.db failed (it was left untouched)")

    data = PrintLogData(hass, store)
    await data.async_refresh()
    tracker = PrintTracker(hass, data, {**entry.data, **entry.options})
    await tracker.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"data": data, "tracker": tracker}

    hass.data[DOMAIN]["_current"] = data
    if not hass.data[DOMAIN].get("_web"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)])
        async_register_views(hass)
        hass.data[DOMAIN]["_web"] = True
    await panel_custom.async_register_panel(
        hass, frontend_url_path=PANEL_URL, webcomponent_name="print-log-panel",
        sidebar_title="Print log", sidebar_icon="mdi:printer-3d",
        module_url=f"{STATIC_URL}/panel.js?v={VERSION}", require_admin=False, config={}, )

    async def _ids(call_data: dict) -> dict:
        def work():
            out = {}
            for key, table in (("person", "people"), ("filament", "filaments"), ("role", "roles")):
                if key in call_data:
                    name = call_data[key]
                    out[f"{key}_id"] = store.get_or_create(table, name) if name else None
            return out
        return await hass.async_add_executor_job(work)

    async def add_print(call: ServiceCall) -> None:
        d = dict(call.data)
        ids = await _ids({k: d.pop(k) for k in ("person", "filament", "role") if k in d})
        await hass.async_add_executor_job(store.add_print, {**d, **ids, "source": "manual"})
        await data.async_refresh()

    async def set_current(call: ServiceCall) -> None:
        ids = await _ids(dict(call.data))
        await hass.async_add_executor_job(store.update_settings, {f"current_{k}": v for k, v in ids.items()})
        await data.async_refresh()

    hass.services.async_register(DOMAIN, "add_print", add_print, ADD_PRINT_SCHEMA)
    hass.services.async_register(DOMAIN, "set_current", set_current, SET_CURRENT_SCHEMA)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)["tracker"].async_stop()
        hass.data[DOMAIN].pop("_current", None)
        hass.services.async_remove(DOMAIN, "add_print")
        hass.services.async_remove(DOMAIN, "set_current")
        frontend.async_remove_panel(hass, PANEL_URL)
    return ok
