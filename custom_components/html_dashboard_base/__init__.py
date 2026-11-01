"""Dashboard Base: een eigen HTML-dashboard als paneel in Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import async_register_api
from .const import (
    CONF_ENTITIES,
    CONF_TITLE,
    DATA_DIR,
    DEFAULT_ICON,
    DEFAULT_TITLE,
    DOMAIN,
    HTML_FILE,
    PANEL_ELEMENT,
    PANEL_URL,
    STATIC_URL,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class DashboardBaseData:
    """Runtime-gegevens van de instelling."""

    allowed: frozenset[str]
    html_path: Path


type DashboardBaseConfigEntry = ConfigEntry[DashboardBaseData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Eenmalig: statische bestanden en koppeling registreren."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                STATIC_URL, str(Path(__file__).parent / "frontend"), False
            )
        ]
    )
    async_register_api(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: DashboardBaseConfigEntry
) -> bool:
    """Paneel registreren."""
    entry.runtime_data = DashboardBaseData(
        allowed=frozenset(entry.options.get(CONF_ENTITIES, [])),
        html_path=Path(hass.config.path(DATA_DIR, HTML_FILE)),
    )
    integration = await async_get_integration(hass, DOMAIN)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_ELEMENT,
        frontend_url_path=PANEL_URL,
        module_url=f"{STATIC_URL}/panel.js?v={integration.version}",
        sidebar_title=entry.options.get(CONF_TITLE, DEFAULT_TITLE),
        sidebar_icon=DEFAULT_ICON,
        require_admin=False,
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DashboardBaseConfigEntry
) -> bool:
    """Paneel weghalen."""
    frontend.async_remove_panel(hass, PANEL_URL)
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: DashboardBaseConfigEntry
) -> None:
    """Geüpload dashboard opruimen bij verwijderen."""
    path = Path(hass.config.path(DATA_DIR, HTML_FILE))
    await hass.async_add_executor_job(path.unlink, True)


async def _async_reload(hass: HomeAssistant, entry: DashboardBaseConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
