"""Gedeelde fixtures voor Dashboard Base."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base.const import (
    CONF_DASHBOARD_ID,
    CONF_ENTITIES,
    CONF_PANEL_URL,
    CONF_TITLE,
    DATA_DIR,
    DOMAIN,
    LEGACY_DASHBOARD_ID,
    LEGACY_PANEL_URL,
)
from custom_components.html_dashboard_base.util import html_file

from .helpers import ALLOWED, SECOND_ALLOWED

DEPENDENCIES = ("frontend", "http", "panel_custom", "websocket_api", "file_upload")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Laat Home Assistant de integratie in deze repo vinden."""


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Het eerste dashboard, met vier toegestane entiteiten."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Dashboard",
        version=2,
        data={
            CONF_DASHBOARD_ID: LEGACY_DASHBOARD_ID,
            CONF_PANEL_URL: LEGACY_PANEL_URL,
        },
        options={CONF_TITLE: "Dashboard", CONF_ENTITIES: list(ALLOWED)},
    )


@pytest.fixture
def second_mock_entry() -> MockConfigEntry:
    """Een tweede dashboard met een andere lijst."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Technisch",
        version=2,
        data={
            CONF_DASHBOARD_ID: "technisch",
            CONF_PANEL_URL: "dashboard-technisch",
        },
        options={CONF_TITLE: "Technisch", CONF_ENTITIES: list(SECOND_ALLOWED)},
    )


@pytest.fixture
def skip_dependencies(hass: HomeAssistant) -> None:
    """Markeer de afhankelijkheden als geladen, zodat ze niet echt starten."""
    hass.config.components.update(DEPENDENCIES)
    hass.http = MagicMock(async_register_static_paths=AsyncMock())


@pytest.fixture
def panel_mocks() -> Generator[tuple[AsyncMock, MagicMock]]:
    """Vervang het registreren en weghalen van het paneel door mocks.

    Er wordt bewust op de modules van Home Assistant zelf gepatcht. Het pad
    custom_components.html_dashboard_base.frontend wijst namelijk naar de map
    met het paneelbestand, niet naar de Home Assistant-module.
    """
    with (
        patch(
            "homeassistant.components.panel_custom.async_register_panel",
            new_callable=AsyncMock,
        ) as register,
        patch("homeassistant.components.frontend.async_remove_panel") as remove,
    ):
        yield register, remove


def _clean_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
async def html_dir(hass: HomeAssistant) -> AsyncGenerator[Path]:
    """De map met opgeslagen dashboards, voor en na de test leeg."""
    path = Path(hass.config.path(DATA_DIR))
    await hass.async_add_executor_job(_clean_dir, path)
    yield path
    await hass.async_add_executor_job(_clean_dir, path)


@pytest.fixture
async def html_path(hass: HomeAssistant, html_dir: Path) -> Path:
    """Pad van het bestand van het eerste dashboard."""
    return html_file(hass, LEGACY_DASHBOARD_ID)


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_path: Path,
    mock_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Het eerste dashboard, geladen."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry


@pytest.fixture
async def second_entry(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    second_mock_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Het tweede dashboard, geladen naast het eerste."""
    second_mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_mock_entry.entry_id)
    await hass.async_block_till_done()
    return second_mock_entry
