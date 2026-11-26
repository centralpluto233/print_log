"""Config flow for Print Log: sets up the first printer. More printers are managed in the panel."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ENERGY_ENTITY, CONF_FILAMENT_ENTITY, CONF_FILENAME_ENTITY, CONF_LENGTH_UNIT, CONF_NAME,
    CONF_PROGRESS_ENTITY, CONF_REMAINING_ENTITY, CONF_STATE_ENTITY, DOMAIN,
)

_ENT = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "input_text", "input_number", "input_select"]))
_UNIT = selector.SelectSelector(selector.SelectSelectorConfig(options=["mm", "cm", "m"], mode=selector.SelectSelectorMode.DROPDOWN))

SCHEMA = vol.Schema({
    vol.Required(CONF_NAME, default="Printer"): str,
    vol.Required(CONF_STATE_ENTITY): _ENT,
    vol.Optional(CONF_FILENAME_ENTITY): _ENT,
    vol.Optional(CONF_FILAMENT_ENTITY): _ENT,
    vol.Required(CONF_LENGTH_UNIT, default="mm"): _UNIT,
    vol.Optional(CONF_PROGRESS_ENTITY): _ENT,
    vol.Optional(CONF_REMAINING_ENTITY): _ENT,
    vol.Optional(CONF_ENERGY_ENTITY): _ENT,
})


class PrintLogConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Print Log", data=user_input)
        return self.async_show_form(step_id="user", data_schema=SCHEMA)
