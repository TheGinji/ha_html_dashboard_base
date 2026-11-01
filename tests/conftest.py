"""Gedeelde fixtures voor Dashboard Base."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import suppress
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base.const import (
    CONF_ENTITIES,
    CONF_TITLE,
    DATA_DIR,
    DOMAIN,
    HTML_FILE,
)

from .helpers import ALLOWED

DEPENDENCIES = ("frontend", "http", "panel_custom", "websocket_api", "file_upload")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Laat Home Assistant de integratie in deze repo vinden."""


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Een instelling met vier toegestane entiteiten."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Dashboard",
        data={},
        options={CONF_TITLE: "Dashboard", CONF_ENTITIES: list(ALLOWED)},
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


def _clean(path: Path) -> None:
    path.unlink(missing_ok=True)
    with suppress(OSError):
        path.parent.rmdir()


@pytest.fixture
async def html_path(hass: HomeAssistant) -> AsyncGenerator[Path]:
    """Pad van het geuploade dashboard, voor en na de test opgeruimd."""
    path = Path(hass.config.path(DATA_DIR, HTML_FILE))
    await hass.async_add_executor_job(_clean, path)
    yield path
    await hass.async_add_executor_job(_clean, path)


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_path: Path,
    mock_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Een geladen instelling."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_entry
