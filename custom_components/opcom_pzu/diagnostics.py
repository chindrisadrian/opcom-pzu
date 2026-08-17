"""Diagnostice pentru OPCOM PZU."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Datele utile pentru raportarea unei probleme (fara informatii personale)."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator
    data = coordinator.data or {}
    return {
        "options": dict(entry.options),
        "settings": runtime.settings.as_options(),
        "last_update_success": coordinator.last_update_success,
        "last_error": coordinator.last_error,
        "today_valid": data.get("today_valid"),
        "tomorrow_valid": data.get("tomorrow_valid"),
        "slots_today": len(data.get("raw_today", [])),
        "slots_tomorrow": len(data.get("raw_tomorrow", [])),
        "horizon_slots": data.get("horizon_slots"),
        "today_stats": data.get("today"),
        "tomorrow_stats": data.get("tomorrow"),
        "best_window": coordinator.window(),
        "sample_slots": data.get("raw_today", [])[:4],
    }
