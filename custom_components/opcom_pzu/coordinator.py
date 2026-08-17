"""Coordinator: aduce preturile OPCOM si recalculeaza valorile derivate."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import opcom
from .const import (
    CONF_PERCENTILE,
    CONF_THRESHOLD,
    CONF_WINDOW,
    DEFAULT_PERCENTILE,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW,
    DOMAIN,
    NAME,
    REQUEST_TIMEOUT,
    UPDATE_INTERVAL,
    window_key,
)

_LOGGER = logging.getLogger(__name__)

# preturile pentru ziua urmatoare apar de regula intre 13:00 si 14:00
TOMORROW_FROM_HOUR = 12
TOMORROW_RETRY = timedelta(minutes=10)
USER_AGENT = "HomeAssistant-OPCOM-PZU (+https://github.com/chindrisadrian/opcom)"


@dataclass
class Settings:
    """Reglajele ajustabile din UI, tinute in memorie si in optiunile intrarii."""

    threshold: float = DEFAULT_THRESHOLD
    percentile: float = DEFAULT_PERCENTILE
    window_hours: float = DEFAULT_WINDOW

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> Settings:
        return cls(
            threshold=float(options.get(CONF_THRESHOLD, DEFAULT_THRESHOLD)),
            percentile=float(options.get(CONF_PERCENTILE, DEFAULT_PERCENTILE)),
            window_hours=float(options.get(CONF_WINDOW, DEFAULT_WINDOW)),
        )

    def as_options(self) -> dict[str, Any]:
        return {
            CONF_THRESHOLD: self.threshold,
            CONF_PERCENTILE: self.percentile,
            CONF_WINDOW: self.window_hours,
        }


@dataclass
class RuntimeData:
    """Ce tine integrarea la runtime pentru o intrare de configurare."""

    coordinator: OpcomCoordinator
    settings: Settings = field(default_factory=Settings)


class OpcomCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Descarca CSV-ul o singura data pe zi si recalculeaza restul din memorie."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=NAME,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self._session = async_get_clientsession(hass)
        self._days: dict[date, list[dict[str, Any]]] = {}
        self._last_tomorrow_try: datetime | None = None
        self.last_error: str | None = None

    # -- retea --------------------------------------------------------------
    async def _fetch_day(self, day: date) -> list[dict[str, Any]]:
        """Descarca si parseaza o zi. Lista goala inseamna 'inca nepublicat'."""
        url = opcom.build_url(day)
        try:
            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                headers={"User-Agent": USER_AGENT},
            ) as resp:
                resp.raise_for_status()
                text = await resp.text(errors="replace")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Nu am putut prelua %s: %s", url, err)
            self.last_error = f"{type(err).__name__}: {err}"
            return []

        slots = await self.hass.async_add_executor_job(
            opcom.parse_csv, text, day, dt_util.DEFAULT_TIME_ZONE
        )
        if len(slots) < opcom.MIN_SLOTS:
            _LOGGER.debug("%s a returnat doar %d intervale", url, len(slots))
            return []
        self.last_error = None
        return slots

    # -- ciclul de actualizare ---------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.now()
        today, tomorrow = now.date(), now.date() + timedelta(days=1)

        # scapa de zilele trecute
        for old in [d for d in self._days if d < today]:
            self._days.pop(old, None)

        if len(self._days.get(today, [])) < opcom.MIN_SLOTS:
            slots = await self._fetch_day(today)
            if slots:
                self._days[today] = slots

        # ziua urmatoare: doar dupa-amiaza si cu pauza intre incercari
        if (
            len(self._days.get(tomorrow, [])) < opcom.MIN_SLOTS
            and now.hour >= TOMORROW_FROM_HOUR
            and (
                self._last_tomorrow_try is None
                or now - self._last_tomorrow_try >= TOMORROW_RETRY
            )
        ):
            self._last_tomorrow_try = now
            slots = await self._fetch_day(tomorrow)
            if slots:
                self._days[tomorrow] = slots

        if not self._days.get(today):
            raise UpdateFailed(
                self.last_error or "OPCOM nu a returnat datele pentru ziua curenta"
            )

        return opcom.build_payload(
            self._days.get(today, []), self._days.get(tomorrow, []), now
        )

    # -- ajutoare pentru entitati ------------------------------------------
    @property
    def settings(self) -> Settings:
        return self.hass.data[DOMAIN][self.config_entry.entry_id].settings

    def window(self) -> dict[str, Any] | None:
        """Fereastra optima pentru durata aleasa in UI."""
        if not self.data:
            return None
        return self.data.get(window_key(self.settings.window_hours))
