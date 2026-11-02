"""Dashboard Base: eigen HTML-dashboards als paneel in Home Assistant."""

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
    CONF_DASHBOARD_ID,
    CONF_ENTITIES,
    CONF_PANEL_URL,
    CONF_TITLE,
    DEFAULT_ICON,
    DEFAULT_TITLE,
    DOMAIN,
    LEGACY_DASHBOARD_ID,
    LEGACY_PANEL_URL,
    PANEL_ELEMENT,
    STATIC_URL,
)
from .util import html_file

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class DashboardBaseData:
    """Runtime-gegevens van één dashboard."""

    allowed: frozenset[str]
    html_path: Path
    panel_url: str


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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Een instelling uit versie 0.1.x (één dashboard) omzetten naar meerdere dashboards."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_DASHBOARD_ID: LEGACY_DASHBOARD_ID,
                CONF_PANEL_URL: LEGACY_PANEL_URL,
            },
            version=2,
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: DashboardBaseConfigEntry
) -> bool:
    """Het paneel van dit dashboard registreren."""
    entry.runtime_data = DashboardBaseData(
        allowed=frozenset(entry.options.get(CONF_ENTITIES, [])),
        html_path=html_file(hass, entry.data[CONF_DASHBOARD_ID]),
        panel_url=entry.data[CONF_PANEL_URL],
    )
    integration = await async_get_integration(hass, DOMAIN)
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_ELEMENT,
        frontend_url_path=entry.runtime_data.panel_url,
        module_url=f"{STATIC_URL}/panel.js?v={integration.version}",
        sidebar_title=entry.options.get(CONF_TITLE, DEFAULT_TITLE),
        sidebar_icon=DEFAULT_ICON,
        require_admin=False,
        config={"entry_id": entry.entry_id},
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DashboardBaseConfigEntry
) -> bool:
    """Het paneel van dit dashboard weghalen."""
    frontend.async_remove_panel(hass, entry.runtime_data.panel_url)
    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: DashboardBaseConfigEntry
) -> None:
    """Het geüploade bestand van dit dashboard opruimen bij verwijderen."""
    path = html_file(hass, entry.data.get(CONF_DASHBOARD_ID, LEGACY_DASHBOARD_ID))
    await hass.async_add_executor_job(path.unlink, True)


async def _async_reload(hass: HomeAssistant, entry: DashboardBaseConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
