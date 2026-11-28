"""Print Log: log 3D prints per person and filament roll, for one or more printers."""
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
from .notifier import Notifier
from .store_ext import ExtStore
from .tracker import PrinterManager

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]
SERVICES = ("add_print", "set_current", "test_notification")

ADD_PRINT_SCHEMA = vol.Schema({
    vol.Required("length_m"): vol.Coerce(float),
    vol.Optional("filename", default=""): str,
    vol.Optional("printer"): str,
    vol.Optional("person"): str,
    vol.Optional("filament"): str,
    vol.Optional("role"): str,
    vol.Optional("status", default="complete"): vol.In(["complete", "cancelled", "error"]),
    vol.Optional("notes"): str,
})
SET_CURRENT_SCHEMA = vol.Schema({
    vol.Optional("printer"): str,
    vol.Optional("person"): vol.Any(None, str),
    vol.Optional("filament"): vol.Any(None, str),
    vol.Optional("role"): vol.Any(None, str),
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = ExtStore(hass.config.path("print_log", "prints.db"), hass.config.time_zone)
    await hass.async_add_executor_job(store.init)
    legacy = Path(hass.config.path("prints.db"))
    if legacy.exists():
        try:
            n = await hass.async_add_executor_job(store.import_legacy, legacy)
            if n:
                _LOGGER.info("Imported %s prints from the old prints.db", n)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Import of the old prints.db failed (it was left untouched)")
    # first install, or upgrade from 0.1.x: create the first printer from the config entry
    await hass.async_add_executor_job(store.ensure_default_printer, {**entry.data, **entry.options})

    data = PrintLogData(hass, store)
    data.notifier = Notifier(hass, data)
    data.manager = PrinterManager(hass, data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"data": data}
    hass.data[DOMAIN]["_current"] = data
    await data.async_refresh(reload=True)

    if not hass.data[DOMAIN].get("_web"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)])
        async_register_views(hass)
        hass.data[DOMAIN]["_web"] = True
    await panel_custom.async_register_panel(
        hass, frontend_url_path=PANEL_URL, webcomponent_name="print-log-panel",
        sidebar_title="Print log", sidebar_icon="mdi:printer-3d",
        module_url=f"{STATIC_URL}/panel.js?v={VERSION}", require_admin=False, config={})

    def _resolve(call_data: dict) -> dict:
        out = {}
        printers = store.list_table("printers", False)
        name = call_data.get("printer")
        printer = next((p for p in printers if p["name"].lower() == (name or "").lower()), None) or (printers[0] if printers else None)
        if printer:
            out["printer_id"] = printer["id"]
        for key, table in (("person", "people"), ("filament", "filaments"), ("role", "roles")):
            if key in call_data:
                out[f"{key}_id"] = store.get_or_create(table, call_data[key]) if call_data[key] else None
        return out

    async def add_print(call: ServiceCall) -> None:
        d = dict(call.data)
        names = {k: d.pop(k) for k in ("printer", "person", "filament", "role") if k in d}
        ids = await hass.async_add_executor_job(_resolve, names)
        await hass.async_add_executor_job(store.add_print, {**d, **ids, "source": "manual"})
        await data.async_refresh()

    async def set_current(call: ServiceCall) -> None:
        ids = await hass.async_add_executor_job(_resolve, dict(call.data))
        pid = ids.pop("printer_id", None)
        if pid:
            await hass.async_add_executor_job(
                store.update_item, "printers", pid, {f"current_{k}": v for k, v in ids.items()})
        await data.async_refresh(reload=True)

    async def test_notification(call: ServiceCall) -> None:
        await data.notifier.test()

    hass.services.async_register(DOMAIN, "add_print", add_print, ADD_PRINT_SCHEMA)
    hass.services.async_register(DOMAIN, "set_current", set_current, SET_CURRENT_SCHEMA)
    hass.services.async_register(DOMAIN, "test_notification", test_notification)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)["data"].manager.async_stop()
        hass.data[DOMAIN].pop("_current", None)
        for svc in SERVICES:
            hass.services.async_remove(DOMAIN, svc)
        frontend.async_remove_panel(hass, PANEL_URL)
    return ok
