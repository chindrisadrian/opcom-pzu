"""Selectorul pentru durata ferestrei de injectie."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, WINDOW_CHOICES, WINDOW_OPTIONS, window_label
from .coordinator import OpcomCoordinator
from .entity import OpcomEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OpcomCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities([OpcomWindowSelect(coordinator)])


class OpcomWindowSelect(OpcomEntity, SelectEntity):
    """Cat dureaza descarcarea ta: 30 min, 1 h, 2 h, 3 h sau 4 h."""

    _attr_icon = "mdi:timer-sand"
    _attr_options = WINDOW_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: OpcomCoordinator) -> None:
        super().__init__(coordinator, "window_duration")

    @property
    def available(self) -> bool:
        return True

    @property
    def current_option(self) -> str:
        return window_label(self.settings.window_hours)

    async def async_select_option(self, option: str) -> None:
        if option not in WINDOW_CHOICES:
            return
        settings = self.settings
        settings.window_hours = WINDOW_CHOICES[option][0]
        self.hass.config_entries.async_update_entry(
            self.coordinator.config_entry, options=settings.as_options()
        )
        self.async_write_ha_state()
