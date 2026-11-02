"""Websocket-koppeling met rechtencontrole: alleen toegestane entiteiten."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.loader import async_get_integration

from .const import ALLOWED_DOMAINS, BLOCKED_TARGET_KEYS, DOMAIN

_PLACEHOLDER = (
    "<!doctype html><meta charset=utf-8>"
    "<body style='font-family:sans-serif;padding:2rem'>"
    "Nog geen dashboard geüpload. Ga naar Instellingen, Apparaten en "
    "diensten, Dashboard Base, Configureren."
)


def _entry(hass: HomeAssistant):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry
    return None


def _allowed(hass: HomeAssistant) -> frozenset[str]:
    entry = _entry(hass)
    return entry.runtime_data.allowed if entry else frozenset()


def _snapshot(state: State) -> dict[str, Any]:
    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }


def _read_html(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else _PLACEHOLDER


@websocket_api.websocket_command({vol.Required("type"): "html_dashboard_base/registry"})
@callback
def ws_registry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Naam, gebied en type van toegestane entiteiten."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    result = []
    for entity_id in sorted(_allowed(hass)):
        entry = ent_reg.async_get(entity_id)
        state = hass.states.get(entity_id)
        area_id = entry.area_id if entry else None
        if entry and not area_id and entry.device_id:
            device = dev_reg.async_get(entry.device_id)
            area_id = device.area_id if device else None
        area = area_reg.async_get_area(area_id) if area_id else None
        result.append(
            {
                "entity_id": entity_id,
                "domain": entity_id.split(".", 1)[0],
                "name": state.name if state else entity_id,
                "area": area.name if area else None,
                "device_class": state.attributes.get("device_class") if state else None,
                "available": state is not None and state.state != "unavailable",
            }
        )
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): "html_dashboard_base/states"})
@callback
def ws_states(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Huidige standen van toegestane entiteiten."""
    states = (hass.states.get(e) for e in sorted(_allowed(hass)))
    connection.send_result(msg["id"], [_snapshot(s) for s in states if s])


@websocket_api.websocket_command({vol.Required("type"): "html_dashboard_base/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Wijzigingen van toegestane entiteiten doorsturen."""

    @callback
    def _is_allowed(data: Any) -> bool:
        return data["entity_id"] in _allowed(hass)

    @callback
    def _forward(event: Event) -> None:
        new_state = event.data["new_state"]
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "entity_id": event.data["entity_id"],
                    "state": _snapshot(new_state) if new_state else None,
                },
            )
        )

    connection.subscriptions[msg["id"]] = hass.bus.async_listen(
        EVENT_STATE_CHANGED, _forward, event_filter=_is_allowed
    )
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "html_dashboard_base/get_html"})
@websocket_api.async_response
async def ws_get_html(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Het geüploade dashboard ophalen."""
    entry = _entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Dashboard Base is niet geladen")
        return
    html = await hass.async_add_executor_job(_read_html, entry.runtime_data.html_path)
    connection.send_result(msg["id"], {"html": html})


@websocket_api.websocket_command({vol.Required("type"): "html_dashboard_base/info"})
@websocket_api.async_response
async def ws_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Versie en de domeinen die een dashboard mag bedienen. Leest alleen."""
    integration = await async_get_integration(hass, DOMAIN)
    connection.send_result(
        msg["id"],
        {
            "version": str(integration.version),
            "call_domains": sorted(ALLOWED_DOMAINS),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "html_dashboard_base/call",
        vol.Required("domain"): cv.string,
        vol.Required("service"): cv.string,
        vol.Optional("data", default=dict): dict,
    }
)
@websocket_api.async_response
async def ws_call(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Service aanroepen, alleen voor toegestane entiteiten."""
    domain, service, data = msg["domain"], msg["service"], dict(msg["data"])
    allowed = _allowed(hass)
    entity_ids = cv.ensure_list(data.get("entity_id"))
    if (
        domain not in ALLOWED_DOMAINS
        or BLOCKED_TARGET_KEYS & data.keys()
        or not entity_ids
        or any(
            not isinstance(e, str)
            or e not in allowed
            or e.split(".", 1)[0] != domain
            for e in entity_ids
        )
    ):
        connection.send_error(msg["id"], "not_allowed", "Niet toegestaan")
        return
    await hass.services.async_call(
        domain, service, data, blocking=True, context=connection.context(msg)
    )
    connection.send_result(msg["id"])


def async_register_api(hass: HomeAssistant) -> None:
    """Alle opdrachten registreren."""
    for command in (
        ws_registry,
        ws_states,
        ws_subscribe,
        ws_get_html,
        ws_info,
        ws_call,
    ):
        websocket_api.async_register_command(hass, command)
