"""Tests voor het laden en verwijderen van de integratie."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base.const import (
    CONF_ENTITIES,
    CONF_TITLE,
    PANEL_ELEMENT,
    PANEL_URL,
    STATIC_URL,
)

from .helpers import ALLOWED, file_exists, write_file


async def test_setup_and_unload(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    panel_mocks: tuple[AsyncMock, MagicMock],
) -> None:
    """Het paneel wordt geregistreerd bij laden en weggehaald bij uitladen."""
    register, remove = panel_mocks

    assert setup_entry.state is ConfigEntryState.LOADED
    assert setup_entry.runtime_data.allowed == frozenset(ALLOWED)
    hass.http.async_register_static_paths.assert_awaited_once()

    register.assert_awaited_once()
    kwargs = register.await_args.kwargs
    assert kwargs["frontend_url_path"] == PANEL_URL
    assert kwargs["webcomponent_name"] == PANEL_ELEMENT
    assert kwargs["sidebar_title"] == "Dashboard"
    assert kwargs["require_admin"] is False
    assert kwargs["module_url"].startswith(f"{STATIC_URL}/panel.js?v=")

    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert setup_entry.state is ConfigEntryState.NOT_LOADED
    remove.assert_called_once_with(hass, PANEL_URL)


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
    assert setup_entry.runtime_data.allowed == frozenset({"light.keuken"})


async def test_remove_entry_deletes_upload(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    """Bij verwijderen wordt het geuploade bestand opgeruimd."""
    await write_file(hass, html_path, "<html></html>")
    assert await file_exists(hass, html_path)

    await hass.config_entries.async_remove(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert not await file_exists(hass, html_path)


async def test_remove_entry_without_upload(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    """Verwijderen zonder geupload bestand geeft geen fout."""
    assert not await file_exists(hass, html_path)

    await hass.config_entries.async_remove(setup_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries("html_dashboard_base")
