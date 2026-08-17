"""Config flow for OPCOM PZU."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_PERCENTILE,
    CONF_THRESHOLD,
    CONF_WINDOW,
    DEFAULT_PERCENTILE,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW,
    DOMAIN,
    MAX_PERCENTILE,
    MAX_THRESHOLD,
    MIN_PERCENTILE,
    MIN_THRESHOLD,
    NAME,
    WINDOW_CHOICES,
    WINDOW_OPTIONS,
    window_label,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_WINDOW, default=window_label(defaults.get(CONF_WINDOW, DEFAULT_WINDOW))
            ): SelectSelector(
                SelectSelectorConfig(options=WINDOW_OPTIONS, mode=SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(
                CONF_THRESHOLD, default=defaults.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_THRESHOLD,
                    max=MAX_THRESHOLD,
                    step=10,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="Lei/MWh",
                )
            ),
            vol.Required(
                CONF_PERCENTILE, default=defaults.get(CONF_PERCENTILE, DEFAULT_PERCENTILE)
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PERCENTILE,
                    max=MAX_PERCENTILE,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                    unit_of_measurement="%",
                )
            ),
        }
    )


def _normalise(data: dict[str, Any]) -> dict[str, Any]:
    """Window label -> hours, and numbers as float."""
    raw = data.get(CONF_WINDOW, DEFAULT_WINDOW)
    hours = WINDOW_CHOICES[raw][0] if raw in WINDOW_CHOICES else float(raw)
    return {
        CONF_WINDOW: hours,
        CONF_THRESHOLD: float(data.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)),
        CONF_PERCENTILE: float(data.get(CONF_PERCENTILE, DEFAULT_PERCENTILE)),
    }


class OpcomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adding the integration from the UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title=NAME, data={}, options=_normalise(user_input)
            )

        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OpcomOptionsFlow:
        return OpcomOptionsFlow()


class OpcomOptionsFlow(OptionsFlow):
    """Subsequent settings, from Configure."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_normalise(user_input))

        return self.async_show_form(
            step_id="init", data_schema=_schema(dict(self.config_entry.options))
        )
