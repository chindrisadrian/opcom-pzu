"""Binary signals for injection automations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import OpcomCoordinator
from .entity import OpcomEntity


def _in_window(c: OpcomCoordinator) -> bool | None:
    win = c.window()
    if not win:
        return None
    start = dt_util.parse_datetime(win["start"])
    end = dt_util.parse_datetime(win["end"])
    if start is None or end is None:
        return None
    return start <= dt_util.now() < end


def _above_threshold(c: OpcomCoordinator) -> bool | None:
    price = (c.data or {}).get("state")
    if price is None:
        return None
    return float(price) >= c.settings.threshold


def _in_percentile(c: OpcomCoordinator) -> bool | None:
    pct = (c.data or {}).get("current_percentile_today")
    if pct is None:
        return None
    return float(pct) >= c.settings.percentile


def _good_moment(c: OpcomCoordinator) -> bool | None:
    win, thr = _in_window(c), _above_threshold(c)
    if win is None and thr is None:
        return None
    return bool(win) or bool(thr)


def _reason(c: OpcomCoordinator) -> dict[str, Any]:
    if _in_window(c):
        win = c.window() or {}
        return {"reason": f"optimal window ({win.get('label')})"}
    if _above_threshold(c):
        return {
            "reason": f"price above threshold ({(c.data or {}).get('state')} Lei/MWh)",
        }
    return {"reason": "not the right time"}


@dataclass(frozen=True, kw_only=True)
class OpcomBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[OpcomCoordinator], bool | None]
    attrs_fn: Callable[[OpcomCoordinator], dict[str, Any]] | None = None


BINARY_SENSORS: tuple[OpcomBinaryDescription, ...] = (
    OpcomBinaryDescription(
        key="good_moment",
        icon="mdi:flash",
        value_fn=_good_moment,
        attrs_fn=_reason,
    ),
    OpcomBinaryDescription(
        key="in_window",
        icon="mdi:transmission-tower-export",
        value_fn=_in_window,
        attrs_fn=lambda c: {
            "starts_at": (c.window() or {}).get("start"),
            "ends_at": (c.window() or {}).get("end"),
            "average_price": (c.window() or {}).get("avg"),
        },
    ),
    OpcomBinaryDescription(
        key="above_threshold",
        icon="mdi:cash-check",
        value_fn=_above_threshold,
        attrs_fn=lambda c: {"threshold": c.settings.threshold},
    ),
    OpcomBinaryDescription(
        key="in_percentile",
        icon="mdi:podium-gold",
        value_fn=_in_percentile,
        attrs_fn=lambda c: {"percentile": c.settings.percentile},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OpcomCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(OpcomBinarySensor(coordinator, d) for d in BINARY_SENSORS)


class OpcomBinarySensor(OpcomEntity, BinarySensorEntity):
    entity_description: OpcomBinaryDescription

    def __init__(
        self, coordinator: OpcomCoordinator, description: OpcomBinaryDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        return super().available and self.is_on is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        attrs = self.entity_description.attrs_fn(self.coordinator)
        return {k: v for k, v in attrs.items() if v is not None}
