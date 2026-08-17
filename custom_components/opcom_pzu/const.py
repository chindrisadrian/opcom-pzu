"""Constants for the OPCOM PZU integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "opcom_pzu"
NAME: Final = "OPCOM PZU"
MANUFACTURER: Final = "OPCOM"
MODEL: Final = "Day-Ahead Market (ROPEX_DAM_15min)"

UPDATE_INTERVAL: Final = timedelta(minutes=5)
REQUEST_TIMEOUT: Final = 30
PRICE_UNIT: Final = "Lei/MWh"

# --- configurable options --------------------------------------------------
CONF_THRESHOLD: Final = "threshold"
CONF_PERCENTILE: Final = "percentile"
CONF_WINDOW: Final = "window_hours"

DEFAULT_THRESHOLD: Final = 900.0
DEFAULT_PERCENTILE: Final = 80.0
DEFAULT_WINDOW: Final = 2.0

MIN_THRESHOLD: Final = 0.0
MAX_THRESHOLD: Final = 5000.0
MIN_PERCENTILE: Final = 50.0
MAX_PERCENTILE: Final = 99.0

# displayed label -> hours, and the window key from payload
WINDOW_CHOICES: Final[dict[str, tuple[float, str]]] = {
    "30 min": (0.5, "best_window_30m"),
    "1 h": (1.0, "best_window_1h"),
    "2 h": (2.0, "best_window_2h"),
    "3 h": (3.0, "best_window_3h"),
    "4 h": (4.0, "best_window_4h"),
}
WINDOW_OPTIONS: Final[list[str]] = list(WINDOW_CHOICES)


def window_label(hours: float) -> str:
    """Select label for a duration in hours."""
    for label, (h, _) in WINDOW_CHOICES.items():
        if abs(h - hours) < 1e-6:
            return label
    return "2 h"


def window_key(hours: float) -> str:
    """The payload key for a duration in hours."""
    for _, (h, key) in WINDOW_CHOICES.items():
        if abs(h - hours) < 1e-6:
            return key
    return "best_window_2h"


# --- frontend resource -----------------------------------------------------
CARD_FILENAME: Final = "opcom-pzu-card.js"
CARD_URL_BASE: Final = f"/{DOMAIN}_static"
CARD_REGISTERED: Final = f"{DOMAIN}_card_registered"
