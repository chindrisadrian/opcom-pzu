"""OPCOM PZU sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PRICE_UNIT
from .coordinator import OpcomCoordinator
from .entity import OpcomEntity

# heavy attributes shouldn't be stored in the database
BULK_ATTRS = frozenset(
    {
        "raw_today",
        "raw_tomorrow",
        "best_slots",
        "today",
        "tomorrow",
        "best_window_30m",
        "best_window_1h",
        "best_window_2h",
        "best_window_3h",
        "best_window_4h",
        "next_peak",
        "window",
        "intervals",
    }
)


def _get(payload: dict[str, Any], *path: str) -> Any:
    node: Any = payload
    for part in path:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


@dataclass(frozen=True, kw_only=True)
class OpcomSensorDescription(SensorEntityDescription):
    """Sensor description with value and attribute functions."""

    value_fn: Callable[[OpcomCoordinator], StateType]
    attrs_fn: Callable[[OpcomCoordinator], dict[str, Any]] | None = None


def _minutes_to_peak(c: OpcomCoordinator) -> StateType:
    start = _get(c.data or {}, "next_peak", "start")
    if not start:
        return None
    moment = dt_util.parse_datetime(start)
    if moment is None:
        return None
    return max(0, round((moment - dt_util.now()).total_seconds() / 60))


SENSORS: tuple[OpcomSensorDescription, ...] = (
    OpcomSensorDescription(
        key="price_now",
        icon="mdi:transmission-tower-export",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: (c.data or {}).get("state"),
        # the card reads everything from here, so it doesn't need other entities
        attrs_fn=lambda c: {
            **{k: v for k, v in (c.data or {}).items() if k not in ("state", "last_update")},
            "threshold": c.settings.threshold,
            "percentile": c.settings.percentile,
            "window_hours": c.settings.window_hours,
            "window": c.window(),
        },
    ),
    OpcomSensorDescription(
        key="max_today",
        icon="mdi:arrow-up-bold",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: _get(c.data or {}, "today", "max"),
        attrs_fn=lambda c: {"hour": _get(c.data or {}, "today", "max_hour")},
    ),
    OpcomSensorDescription(
        key="min_today",
        icon="mdi:arrow-down-bold",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: _get(c.data or {}, "today", "min"),
        attrs_fn=lambda c: {"hour": _get(c.data or {}, "today", "min_hour")},
    ),
    OpcomSensorDescription(
        key="mean_today",
        icon="mdi:chart-line",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: _get(c.data or {}, "today", "mean"),
        attrs_fn=lambda c: {
            "median": _get(c.data or {}, "today", "median"),
            "p75": _get(c.data or {}, "today", "p75"),
            "p90": _get(c.data or {}, "today", "p90"),
        },
    ),
    OpcomSensorDescription(
        key="peak_hour_today",
        icon="mdi:clock-star-four-points",
        value_fn=lambda c: _get(c.data or {}, "today", "max_hour"),
    ),
    OpcomSensorDescription(
        key="max_tomorrow",
        icon="mdi:calendar-arrow-right",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: _get(c.data or {}, "tomorrow", "max"),
        attrs_fn=lambda c: {
            "hour": _get(c.data or {}, "tomorrow", "max_hour"),
            "mean": _get(c.data or {}, "tomorrow", "mean"),
            "min": _get(c.data or {}, "tomorrow", "min"),
            "published": (c.data or {}).get("tomorrow_valid"),
        },
    ),
    OpcomSensorDescription(
        key="price_position",
        icon="mdi:gauge",
        native_unit_of_measurement="%",
        suggested_display_precision=0,
        value_fn=lambda c: (c.data or {}).get("current_percentile_today"),
        attrs_fn=lambda c: {
            "rank_today": (c.data or {}).get("current_rank_today"),
            "of": _get(c.data or {}, "today", "slots"),
        },
    ),
    OpcomSensorDescription(
        key="best_window",
        icon="mdi:transmission-tower-export",
        value_fn=lambda c: (c.window() or {}).get("label"),
        attrs_fn=lambda c: {
            "start": (c.window() or {}).get("start"),
            "end": (c.window() or {}).get("end"),
            "average_price": (c.window() or {}).get("avg"),
            "min_price": (c.window() or {}).get("min"),
            "max_price": (c.window() or {}).get("max"),
            "duration_hours": (c.window() or {}).get("hours"),
        },
    ),
    OpcomSensorDescription(
        key="best_window_price",
        icon="mdi:cash",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: (c.window() or {}).get("avg"),
    ),
    OpcomSensorDescription(
        key="next_peak",
        icon="mdi:chart-bell-curve",
        native_unit_of_measurement=PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda c: _get(c.data or {}, "next_peak", "value"),
        attrs_fn=lambda c: {
            "hour": _get(c.data or {}, "next_peak", "label"),
            "start": _get(c.data or {}, "next_peak", "start"),
        },
    ),
    OpcomSensorDescription(
        key="minutes_to_peak",
        icon="mdi:timer-outline",
        native_unit_of_measurement="min",
        value_fn=_minutes_to_peak,
    ),
    OpcomSensorDescription(
        key="top_slots",
        icon="mdi:format-list-numbered",
        value_fn=lambda c: ", ".join(
            s["label"] for s in (c.data or {}).get("best_slots", [])
        )
        or None,
        attrs_fn=lambda c: {"intervals": (c.data or {}).get("best_slots", [])},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: OpcomCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(OpcomSensor(coordinator, d) for d in SENSORS)


class OpcomSensor(OpcomEntity, SensorEntity):
    """A sensor described by OpcomSensorDescription."""

    entity_description: OpcomSensorDescription
    _unrecorded_attributes = BULK_ATTRS

    def __init__(
        self, coordinator: OpcomCoordinator, description: OpcomSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        attrs = self.entity_description.attrs_fn(self.coordinator)
        return {k: v for k, v in attrs.items() if v is not None}
