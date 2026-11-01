"""Tests voor de websocket-koppeling: de handlers rechtstreeks aangeroepen."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from custom_components.html_dashboard_base import api
from custom_components.html_dashboard_base.const import DOMAIN

from .helpers import ALLOWED, write_file


def make_connection() -> MagicMock:
    connection = MagicMock()
    connection.subscriptions = {}
    connection.context.return_value = Context(user_id="user-1")
    return connection


def msg(command: str, **extra: Any) -> dict[str, Any]:
    return {"id": 1, "type": f"{DOMAIN}/{command}", **extra}


async def test_registry(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Naam, gebied en type van toegestane entiteiten, ook zonder registratie of stand."""
    area_reg = ar.async_get(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    beneden = area_reg.async_create("Beneden")
    buiten = area_reg.async_create("Buiten")

    ent_reg.async_get_or_create(
        "light", "test", "keuken", suggested_object_id="keuken"
    )
    ent_reg.async_update_entity("light.keuken", area_id=beneden.id)

    device = dev_reg.async_get_or_create(
        config_entry_id=setup_entry.entry_id, identifiers={("test", "tuin")}
    )
    dev_reg.async_update_device(device.id, area_id=buiten.id)
    ent_reg.async_get_or_create(
        "switch",
        "test",
        "tuin",
        suggested_object_id="tuin",
        config_entry=setup_entry,
        device_id=device.id,
    )

    hass.states.async_set(
        "light.keuken", "on", {"friendly_name": "Keuken", "device_class": "lamp"}
    )
    hass.states.async_set("switch.tuin", "unavailable", {"friendly_name": "Tuin"})
    hass.states.async_set("sensor.buiten", "12", {"friendly_name": "Buiten"})
    hass.states.async_set("light.geheim", "on")

    connection = make_connection()
    api.ws_registry(hass, connection, msg("registry"))

    connection.send_result.assert_called_once()
    rows = {row["entity_id"]: row for row in connection.send_result.call_args.args[1]}
    assert set(rows) == set(ALLOWED)
    assert rows["light.keuken"] == {
        "entity_id": "light.keuken",
        "domain": "light",
        "name": "Keuken",
        "area": "Beneden",
        "device_class": "lamp",
        "available": True,
    }
    assert rows["switch.tuin"]["area"] == "Buiten"
    assert rows["switch.tuin"]["available"] is False
    assert rows["sensor.buiten"]["area"] is None
    assert rows["scene.weg"] == {
        "entity_id": "scene.weg",
        "domain": "scene",
        "name": "scene.weg",
        "area": None,
        "device_class": None,
        "available": False,
    }


async def test_states_only_allowed(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Alleen standen van toegestane entiteiten komen mee."""
    hass.states.async_set("light.keuken", "on", {"friendly_name": "Keuken"})
    hass.states.async_set("light.geheim", "on")

    connection = make_connection()
    api.ws_states(hass, connection, msg("states"))

    result = connection.send_result.call_args.args[1]
    assert [row["entity_id"] for row in result] == ["light.keuken"]
    assert result[0]["state"] == "on"
    assert result[0]["attributes"] == {"friendly_name": "Keuken"}


async def test_subscribe_forwards_allowed_changes(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Wijzigingen van toegestane entiteiten gaan door, andere niet."""
    hass.states.async_set("light.keuken", "on")
    connection = make_connection()
    api.ws_subscribe(hass, connection, msg("subscribe"))
    connection.send_result.assert_called_once_with(1)

    hass.states.async_set("light.keuken", "off")
    hass.states.async_set("light.geheim", "off")
    hass.states.async_remove("light.keuken")
    await hass.async_block_till_done()

    events = [call.args[0]["event"] for call in connection.send_message.call_args_list]
    assert [event["entity_id"] for event in events] == ["light.keuken", "light.keuken"]
    assert events[0]["state"]["state"] == "off"
    assert events[1]["state"] is None

    connection.subscriptions[1]()
    hass.states.async_set("light.keuken", "on")
    await hass.async_block_till_done()
    assert connection.send_message.call_count == 2


async def test_get_html_placeholder(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Zonder upload komt er een korte melding."""
    connection = make_connection()
    api.ws_get_html(hass, connection, msg("get_html"))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Nog geen dashboard" in connection.send_result.call_args.args[1]["html"]


async def test_get_html_uploaded(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    """Een geuploade pagina komt onveranderd terug."""
    await write_file(hass, html_path, "<html>mijn dashboard</html>")

    connection = make_connection()
    api.ws_get_html(hass, connection, msg("get_html"))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert connection.send_result.call_args.args[1] == {
        "html": "<html>mijn dashboard</html>"
    }


async def test_get_html_not_loaded(hass: HomeAssistant) -> None:
    """Zonder geladen instelling geeft de koppeling een fout."""
    connection = make_connection()
    api.ws_get_html(hass, connection, msg("get_html"))
    await hass.async_block_till_done(wait_background_tasks=True)

    connection.send_error.assert_called_once()
    assert connection.send_error.call_args.args[1] == "not_loaded"


async def test_call_allowed(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Een toegestane aanroep gaat door met alle gegevens en onder de gebruiker."""
    calls = async_mock_service(hass, "light", "turn_on")

    connection = make_connection()
    api.ws_call(
        hass,
        connection,
        msg(
            "call",
            domain="light",
            service="turn_on",
            data={"entity_id": "light.keuken", "brightness": 100},
        ),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    connection.send_result.assert_called_once_with(1)
    assert len(calls) == 1
    assert calls[0].data["brightness"] == 100
    assert calls[0].context.user_id == "user-1"


async def test_call_allowed_list(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Een lijst met toegestane entiteiten mag ook."""
    calls = async_mock_service(hass, "switch", "turn_off")

    connection = make_connection()
    api.ws_call(
        hass,
        connection,
        msg(
            "call",
            domain="switch",
            service="turn_off",
            data={"entity_id": ["switch.tuin"]},
        ),
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    connection.send_result.assert_called_once_with(1)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("domain", "service", "data"),
    [
        ("lock", "unlock", {"entity_id": "lock.voordeur"}),
        ("light", "turn_on", {"entity_id": "light.geheim"}),
        ("light", "turn_on", {}),
        ("light", "turn_on", {"entity_id": "light.keuken", "area_id": "beneden"}),
        ("light", "turn_on", {"entity_id": "light.keuken", "device_id": "abc"}),
        ("light", "turn_on", {"entity_id": "light.keuken", "floor_id": "x"}),
        ("light", "turn_on", {"entity_id": "light.keuken", "label_id": "x"}),
        ("light", "turn_on", {"entity_id": "light.keuken,switch.tuin"}),
        ("light", "turn_on", {"entity_id": 5}),
        ("switch", "turn_on", {"entity_id": "light.keuken"}),
        ("light", "turn_on", {"entity_id": ["light.keuken", "light.geheim"]}),
    ],
    ids=[
        "domein_niet_toegestaan",
        "entiteit_niet_toegestaan",
        "geen_entity_id",
        "area_id",
        "device_id",
        "floor_id",
        "label_id",
        "kommalijst",
        "geen_tekst",
        "ander_domein",
        "een_van_twee_niet_toegestaan",
    ],
)
async def test_call_blocked(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    domain: str,
    service: str,
    data: dict[str, Any],
) -> None:
    """Alles buiten de regels wordt geweigerd en roept niets aan."""
    calls = async_mock_service(hass, domain, service)

    connection = make_connection()
    api.ws_call(
        hass, connection, msg("call", domain=domain, service=service, data=data)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    connection.send_error.assert_called_once()
    assert connection.send_error.call_args.args[1] == "not_allowed"
    connection.send_result.assert_not_called()
    assert calls == []
