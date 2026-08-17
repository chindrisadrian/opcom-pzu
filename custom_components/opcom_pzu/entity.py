"""Clasa de baza pentru entitatile OPCOM PZU."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, NAME
from .coordinator import OpcomCoordinator


class OpcomEntity(CoordinatorEntity[OpcomCoordinator]):
    """Toate entitatile apartin aceluiasi dispozitiv logic."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OpcomCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.opcom.ro/grafice-ip-raportPIP-si-volumTranzactionat/ro",
        )

    @property
    def payload(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    @property
    def settings(self):
        return self.coordinator.settings
