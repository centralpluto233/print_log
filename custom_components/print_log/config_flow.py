"""Config flow for Print Log."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_FILAMENT_ENTITY, CONF_FILENAME_ENTITY, CONF_LENGTH_UNIT, CONF_STATE_ENTITY, DOMAIN,
)

_ENT = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "input_text", "input_number"]))
_STATE = selector.EntitySelector(selector.EntitySelectorConfig(domain=["sensor", "input_select"]))
_UNIT = selector.SelectSelector(selector.SelectSelectorConfig(options=["mm", "cm", "m"], mode=selector.SelectSelectorMode.DROPDOWN))


def _schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_STATE_ENTITY, default=d.get(CONF_STATE_ENTITY, vol.UNDEFINED)): _STATE,
        vol.Required(CONF_FILENAME_ENTITY, default=d.get(CONF_FILENAME_ENTITY, vol.UNDEFINED)): _ENT,
        vol.Required(CONF_FILAMENT_ENTITY, default=d.get(CONF_FILAMENT_ENTITY, vol.UNDEFINED)): _ENT,
        vol.Required(CONF_LENGTH_UNIT, default=d.get(CONF_LENGTH_UNIT, "mm")): _UNIT,
    })


class PrintLogConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Print Log", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return PrintLogOptionsFlow()


class PrintLogOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=_schema({**self.config_entry.data, **self.config_entry.options}))
