"""Tests voor de info-opdracht."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base import api
from custom_components.html_dashboard_base.const import ALLOWED_DOMAINS, DOMAIN


@pytest.fixture
async def client(
    hass: HomeAssistant,
    hass_ws_client,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_path,
    mock_entry: MockConfigEntry,
):
    """Een ingelogde websocket-client, met de integratie geladen."""
    ws = await hass_ws_client(hass)
    hass.config.components.update(("frontend", "panel_custom", "file_upload"))
    hass.http.async_register_static_paths = AsyncMock()
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return ws


async def test_info_handler(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """De opdracht geeft de versie en alle domeinen die bediend mogen worden."""
    connection = MagicMock()
    api.ws_info(hass, connection, {"id": 1, "type": f"{DOMAIN}/info"})
    await hass.async_block_till_done(wait_background_tasks=True)

    result = connection.send_result.call_args.args[1]
    assert result["call_domains"] == sorted(ALLOWED_DOMAINS)
    assert isinstance(result["version"], str)
    assert result["version"]


async def test_info_via_websocket(hass: HomeAssistant, client) -> None:
    """Dezelfde opdracht via een echte verbinding, en gevoelige domeinen ontbreken."""
    await client.send_json({"id": 1, "type": f"{DOMAIN}/info"})
    msg = await client.receive_json()

    assert msg["success"]
    domains = msg["result"]["call_domains"]
    assert "light" in domains
    assert "lock" not in domains
    assert "alarm_control_panel" not in domains
