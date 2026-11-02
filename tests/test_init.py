"""Tests voor het laden, migreren en verwijderen van dashboards."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base.const import (
    CONF_DASHBOARD_ID,
    CONF_ENTITIES,
    CONF_PANEL_URL,
    CONF_TITLE,
    DOMAIN,
    LEGACY_DASHBOARD_ID,
    LEGACY_PANEL_URL,
    PANEL_ELEMENT,
    STATIC_URL,
)

from .helpers import ALLOWED, SECOND_ALLOWED, file_exists, read_file, write_file


async def test_setup_and_unload(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    panel_mocks: tuple[AsyncMock, MagicMock],
) -> None:
    """Het paneel wordt geregistreerd bij laden en weggehaald bij uitladen."""
    register, remove = panel_mocks

    assert setup_entry.state is ConfigEntryState.LOADED
    assert setup_entry.runtime_data.allowed == frozenset(ALLOWED)
    assert setup_entry.runtime_data.panel_url == LEGACY_PANEL_URL
    hass.http.async_register_static_paths.assert_awaited_once()

    register.assert_awaited_once()
    kwargs = register.await_args.kwargs
    assert kwargs["frontend_url_path"] == LEGACY_PANEL_URL
    assert kwargs["webcomponent_name"] == PANEL_ELEMENT
    assert kwargs["sidebar_title"] == "Dashboard"
    assert kwargs["require_admin"] is False
    assert kwargs["config"] == {"entry_id": setup_entry.entry_id}
    assert kwargs["module_url"].startswith(f"{STATIC_URL}/panel.js?v=")

    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_entry.state is ConfigEntryState.NOT_LOADED
    remove.assert_called_once_with(hass, LEGACY_PANEL_URL)


async def test_two_dashboards_have_own_panels(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    second_entry: MockConfigEntry,
    panel_mocks: tuple[AsyncMock, MagicMock],
) -> None:
    """Elk dashboard krijgt een eigen paneel en een eigen lijst."""
    register, remove = panel_mocks

    assert register.await_count == 2
    urls = [call.kwargs["frontend_url_path"] for call in register.await_args_list]
    assert urls == [LEGACY_PANEL_URL, "dashboard-technisch"]
    configs = [call.kwargs["config"] for call in register.await_args_list]
    assert configs == [
        {"entry_id": setup_entry.entry_id},
        {"entry_id": second_entry.entry_id},
    ]
    titles = [call.kwargs["sidebar_title"] for call in register.await_args_list]
    assert titles == ["Dashboard", "Technisch"]

    assert setup_entry.runtime_data.allowed == frozenset(ALLOWED)
    assert second_entry.runtime_data.allowed == frozenset(SECOND_ALLOWED)
    hass.http.async_register_static_paths.assert_awaited_once()

    assert await hass.config_entries.async_unload(second_entry.entry_id)
    await hass.async_block_till_done()

    remove.assert_called_once_with(hass, "dashboard-technisch")
    assert setup_entry.state is ConfigEntryState.LOADED


async def test_options_change_reloads(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    panel_mocks: tuple[AsyncMock, MagicMock],
) -> None:
    """Nieuwe opties laden de instelling opnieuw, met de nieuwe lijst en titel."""
    register, _ = panel_mocks

    hass.config_entries.async_update_entry(
        setup_entry,
        options={CONF_TITLE: "Nieuw", CONF_ENTITIES: ["light.keuken"]},
    )
    await hass.async_block_till_done()

    assert register.await_count == 2
    assert register.await_args.kwargs["sidebar_title"] == "Nieuw"
    assert register.await_args.kwargs["frontend_url_path"] == LEGACY_PANEL_URL
    assert setup_entry.runtime_data.allowed == frozenset({"light.keuken"})


async def test_migrate_from_single_dashboard(
    hass: HomeAssistant,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_path: Path,
) -> None:
    """Een instelling uit 0.1.x blijft werken: zelfde bestand en zelfde paneeladres."""
    register, _ = panel_mocks
    old = MockConfigEntry(
        domain=DOMAIN,
        title="Oud",
        version=1,
        data={},
        options={CONF_TITLE: "Oud", CONF_ENTITIES: ["light.keuken"]},
    )
    old.add_to_hass(hass)
    await write_file(hass, html_path, "<html>oud</html>")

    assert await hass.config_entries.async_setup(old.entry_id)
    await hass.async_block_till_done()

    assert old.version == 2
    assert old.state is ConfigEntryState.LOADED
    assert old.data == {
        CONF_DASHBOARD_ID: LEGACY_DASHBOARD_ID,
        CONF_PANEL_URL: LEGACY_PANEL_URL,
    }
    assert old.runtime_data.html_path == html_path
    assert await read_file(hass, html_path) == "<html>oud</html>"
    assert register.await_args.kwargs["frontend_url_path"] == LEGACY_PANEL_URL


async def test_remove_entry_deletes_upload(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    """Bij verwijderen wordt het bestand van dit dashboard opgeruimd."""
    await write_file(hass, html_path, "<html></html>")
    assert await file_exists(hass, html_path)

    await hass.config_entries.async_remove(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert not await file_exists(hass, html_path)


async def test_remove_one_dashboard_keeps_the_other(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    second_entry: MockConfigEntry,
    html_path: Path,
) -> None:
    """Het bestand van het andere dashboard blijft staan."""
    other = html_path.parent / "technisch.html"
    await write_file(hass, html_path, "<html>een</html>")
    await write_file(hass, other, "<html>twee</html>")

    await hass.config_entries.async_remove(second_entry.entry_id)
    await hass.async_block_till_done()

    assert not await file_exists(hass, other)
    assert await file_exists(hass, html_path)
    assert setup_entry.state is ConfigEntryState.LOADED


async def test_remove_entry_without_upload(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    """Verwijderen zonder geupload bestand geeft geen fout."""
    assert not await file_exists(hass, html_path)

    await hass.config_entries.async_remove(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
