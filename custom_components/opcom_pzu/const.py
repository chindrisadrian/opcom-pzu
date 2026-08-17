"""Constante pentru integrarea OPCOM PZU."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "opcom_pzu"
NAME: Final = "OPCOM PZU"
MANUFACTURER: Final = "OPCOM"
MODEL: Final = "Piata pentru Ziua Urmatoare (ROPEX_DAM_15min)"

UPDATE_INTERVAL: Final = timedelta(minutes=5)
REQUEST_TIMEOUT: Final = 30
PRICE_UNIT: Final = "Lei/MWh"

# --- optiuni configurabile -------------------------------------------------
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

# eticheta afisata -> ore, si cheia ferestrei din payload
WINDOW_CHOICES: Final[dict[str, tuple[float, str]]] = {
    "30 min": (0.5, "best_window_30m"),
    "1 h": (1.0, "best_window_1h"),
    "2 h": (2.0, "best_window_2h"),
    "3 h": (3.0, "best_window_3h"),
    "4 h": (4.0, "best_window_4h"),
}
WINDOW_OPTIONS: Final[list[str]] = list(WINDOW_CHOICES)


def window_label(hours: float) -> str:
    """Eticheta de select pentru o durata in ore."""
    for label, (h, _) in WINDOW_CHOICES.items():
        if abs(h - hours) < 1e-6:
            return label
    return "2 h"


def window_key(hours: float) -> str:
    """Cheia din payload pentru o durata in ore."""
    for _, (h, key) in WINDOW_CHOICES.items():
        if abs(h - hours) < 1e-6:
            return key
    return "best_window_2h"


# --- resursa de frontend ---------------------------------------------------
CARD_FILENAME: Final = "opcom-pzu-card.js"
CARD_URL_BASE: Final = f"/{DOMAIN}_static"
CARD_REGISTERED: Final = f"{DOMAIN}_card_registered"
