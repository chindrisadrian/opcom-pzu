"""Numeric settings: injection threshold and percentile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MAX_PERCENTILE,
    MAX_THRESHOLD,
    MIN_PERCENTILE,
    MIN_THRESHOLD,
    PRICE_UNIT,
)
from .coordinator import OpcomCoordinator, Settings
from .entity import OpcomEntity


@dataclass(frozen=True, kw_only=True)
class OpcomNumberDescription(NumberEntityDescription):
    value_fn: Callable[[Settings], float]
    set_fn: Callable[[Settings, float], None]


NUMBERS: tuple[OpcomNumberDescription, ...] = (
    OpcomNumberDescription(
        key="threshold",
        icon="mdi:cash-multiple",
        native_min_value=MIN_THRESHOLD,
        native_max_value=MAX_THRESHOLD,
        native_step=10,
        native_unit_of_measurement=PRICE_UNIT,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.threshold,
        set_fn=lambda s, v: setattr(s, "threshold", v),
    ),
    OpcomNumberDescription(
        key="percentile",
        icon="mdi:percent",
        native_min_value=MIN_PERCENTILE,
        native_max_value=MAX_PERCENTILE,
        native_step=1,
        native_unit_of_measurement="%",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda s: s.percentile,
        set_fn=lambda s, v: setattr(s, "percentile", v),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OpcomCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(OpcomNumber(coordinator, d) for d in NUMBERS)


class OpcomNumber(OpcomEntity, NumberEntity):
    """The value is saved in the entry options, so it survives restarts."""

    entity_description: OpcomNumberDescription

    def __init__(
        self, coordinator: OpcomCoordinator, description: OpcomNumberDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return True  # settings remain usable even if OPCOM doesn't respond

    @property
    def native_value(self) -> float:
        return self.entity_description.value_fn(self.settings)

    async def async_set_native_value(self, value: float) -> None:
        settings = self.settings
        self.entity_description.set_fn(settings, float(value))
        self.hass.config_entries.async_update_entry(
            self.coordinator.config_entry, options=settings.as_options()
        )
        self.async_write_ha_state()
