"""Integrarea OPCOM PZU — preturi la 15 minute pentru Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import CARD_FILENAME, CARD_REGISTERED, CARD_URL_BASE, DOMAIN
from .coordinator import OpcomCoordinator, RuntimeData, Settings

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


def _card_dir() -> Path | None:
    """Directorul care contine cardul.

    In mod normal e `www/` din integrare. Cautam si langa `__init__.py`, in caz
    ca fisierul a ajuns acolo la o instalare manuala.
    """
    here = Path(__file__).parent
    for candidate in (here / "www", here):
        if (candidate / CARD_FILENAME).is_file():
            return candidate
    return None


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serveste cardul propriu si il adauga la resursele de frontend.

    Asa nu trebuie sa instalezi separat un card din HACS si nici sa adaugi
    manual resursa in dashboard.

    Important: Home Assistant construieste o resursa statica doar pentru un
    DIRECTOR — pentru un fisier individual exista doar o cale secundara, care
    lipseste din versiunile mai vechi. De aceea inregistram folderul intreg.
    """
    if hass.data.get(CARD_REGISTERED):
        return

    url = f"{CARD_URL_BASE}/{CARD_FILENAME}"
    directory = _card_dir()
    if directory is None:
        _LOGGER.error(
            "Nu am gasit %s in %s. Cardul nu va fi disponibil — reinstaleaza "
            "integrarea din HACS sau copiaza fisierul manual.",
            CARD_FILENAME,
            Path(__file__).parent / "www",
        )
        return

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_BASE, str(directory), False)]
        )
    except ImportError:  # Home Assistant mai vechi de 2024.7
        hass.http.register_static_path(CARD_URL_BASE, str(directory), False)
    except RuntimeError as err:
        # calea era deja inregistrata (reincarcare a intrarii) — nu e o problema
        _LOGGER.debug("Calea statica %s era deja inregistrata: %s", CARD_URL_BASE, err)
    except Exception:  # noqa: BLE001
        _LOGGER.exception(
            "Nu am putut servi cardul din %s. Adauga manual resursa %s "
            "(tip: JavaScript Module) din Settings > Dashboards > Resources.",
            directory,
            url,
        )
        return

    version = "0"
    try:
        from homeassistant.loader import async_get_integration

        version = str((await async_get_integration(hass, DOMAIN)).version)
    except Exception:  # noqa: BLE001
        pass

    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, f"{url}?v={version}")
    except Exception:  # noqa: BLE001
        _LOGGER.exception(
            "Nu am putut inregistra cardul in frontend. Adauga manual resursa %s "
            "(tip: JavaScript Module) din Settings > Dashboards > Resources.",
            url,
        )
        return

    hass.data[CARD_REGISTERED] = True
    _LOGGER.info("Cardul OPCOM PZU este servit la %s (din %s)", url, directory)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Porneste o intrare de configurare."""
    await _async_register_card(hass)

    coordinator = OpcomCoordinator(hass, entry)
    runtime = RuntimeData(coordinator=coordinator, settings=Settings.from_options(dict(entry.options)))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # recalculeaza exact la granita fiecarui interval de 15 minute
    entry.async_on_unload(
        async_track_time_change(
            hass,
            lambda _now: hass.async_create_task(coordinator.async_refresh()),
            minute=[0, 15, 30, 45],
            second=5,
        )
    )

    # schimbarile de optiuni nu au nevoie de reincarcare, doar de re-randare
    async def _options_updated(hass: HomeAssistant, updated: ConfigEntry) -> None:
        runtime.settings = Settings.from_options(dict(updated.options))
        coordinator.async_update_listeners()

    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Opreste o intrare de configurare."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
