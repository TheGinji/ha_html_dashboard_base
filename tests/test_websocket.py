"""Tests via een echte websocket-verbinding."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base.const import DOMAIN


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


async def test_states(hass: HomeAssistant, client) -> None:
    """De opdracht is geregistreerd en geeft alleen toegestane standen."""
    hass.states.async_set("light.keuken", "on", {"friendly_name": "Keuken"})
    hass.states.async_set("light.geheim", "on")

    await client.send_json({"id": 1, "type": f"{DOMAIN}/states"})
    msg = await client.receive_json()

    assert msg["success"]
    assert [row["entity_id"] for row in msg["result"]] == ["light.keuken"]


async def test_registry(hass: HomeAssistant, client) -> None:
    await client.send_json({"id": 1, "type": f"{DOMAIN}/registry"})
    msg = await client.receive_json()

    assert msg["success"]
    assert len(msg["result"]) == 4


async def test_get_html(hass: HomeAssistant, client) -> None:
    await client.send_json({"id": 1, "type": f"{DOMAIN}/get_html"})
    msg = await client.receive_json()

    assert msg["success"]
    assert "Nog geen dashboard" in msg["result"]["html"]


async def test_call_allowed(hass: HomeAssistant, client) -> None:
    calls = async_mock_service(hass, "light", "turn_on")

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/call",
            "domain": "light",
            "service": "turn_on",
            "data": {"entity_id": "light.keuken"},
        }
    )
    msg = await client.receive_json()
    await hass.async_block_till_done()

    assert msg["success"]
    assert len(calls) == 1
    assert calls[0].context.user_id is not None


async def test_call_blocked(hass: HomeAssistant, client) -> None:
    calls = async_mock_service(hass, "light", "turn_on")

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/call",
            "domain": "light",
            "service": "turn_on",
            "data": {"entity_id": "light.geheim"},
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_allowed"
    assert calls == []


async def test_call_invalid_format(hass: HomeAssistant, client) -> None:
    """Een opdracht zonder verplichte velden wordt door het schema geweigerd."""
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/call", "service": "turn_on"}
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


async def test_subscribe(hass: HomeAssistant, client) -> None:
    """Een wijziging van een toegestane entiteit komt als event binnen."""
    hass.states.async_set("light.keuken", "on")

    await client.send_json({"id": 1, "type": f"{DOMAIN}/subscribe"})
    msg = await client.receive_json()
    assert msg["success"]

    hass.states.async_set("light.geheim", "off")
    hass.states.async_set("light.keuken", "off")

    msg = await client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["entity_id"] == "light.keuken"
    assert msg["event"]["state"]["state"] == "off"
