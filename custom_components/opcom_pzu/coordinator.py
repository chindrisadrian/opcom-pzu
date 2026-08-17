"""Coordinator: fetches OPCOM prices and recalculates derived values."""

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

# prices for the next day usually appear between 13:00 and 14:00
TOMORROW_FROM_HOUR = 12
TOMORROW_RETRY = timedelta(minutes=10)
USER_AGENT = "HomeAssistant-OPCOM-PZU (+https://github.com/chindrisadrian/opcom-pzu)"


@dataclass
class Settings:
    """Adjustable UI settings, kept in memory and entry options."""

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
    """What the integration keeps at runtime for a config entry."""

    coordinator: OpcomCoordinator
    settings: Settings = field(default_factory=Settings)


class OpcomCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Downloads the CSV only once a day and recalculates the rest from memory."""

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

    # -- network --------------------------------------------------------------
    async def _fetch_day(self, day: date) -> list[dict[str, Any]]:
        """Downloads and parses a day. Empty list means 'not yet published'."""
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
            _LOGGER.debug("Could not fetch %s: %s", url, err)
            self.last_error = f"{type(err).__name__}: {err}"
            return []

        slots = await self.hass.async_add_executor_job(
            opcom.parse_csv, text, day, dt_util.DEFAULT_TIME_ZONE
        )
        if len(slots) < opcom.MIN_SLOTS:
            _LOGGER.debug("%s returned only %d intervals", url, len(slots))
            return []
        self.last_error = None
        return slots

    # -- update cycle ---------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.now()
        today, tomorrow = now.date(), now.date() + timedelta(days=1)

        # discard past days
        for old in [d for d in self._days if d < today]:
            self._days.pop(old, None)

        if len(self._days.get(today, [])) < opcom.MIN_SLOTS:
            slots = await self._fetch_day(today)
            if slots:
                self._days[today] = slots

        # next day: only in the afternoon and with pause between attempts
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
                self.last_error or "OPCOM did not return data for the current day"
            )

        return opcom.build_payload(
            self._days.get(today, []), self._days.get(tomorrow, []), now
        )

    # -- entity helpers -------------------------------------------------------
    @property
    def settings(self) -> Settings:
        return self.hass.data[DOMAIN][self.config_entry.entry_id].settings

    def window(self) -> dict[str, Any] | None:
        """Optimal window for the duration chosen in the UI."""
        if not self.data:
            return None
        return self.data.get(window_key(self.settings.window_hours))
