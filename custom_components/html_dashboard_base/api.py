"""Websocket-koppeling met rechtencontrole: elk dashboard ziet alleen zijn eigen lijst."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import (
    ALLOWED_DOMAINS,
    BLOCKED_TARGET_KEYS,
    CONF_TITLE,
    DEFAULT_TITLE,
    DOMAIN,
)
from .series import (
    FORECAST_TYPES,
    MAX_HOURS,
    MAX_SERIES,
    downsample,
    forecast_points,
)
from .util import placeholder_html


def _entry(hass: HomeAssistant, entry_id: str | None):
    """De geladen instelling met dit id, of None."""
    if entry_id is None:
        return None
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is not None
        and entry.domain == DOMAIN
        and entry.state is ConfigEntryState.LOADED
    ):
        return entry
    return None


def _entry_id(hass: HomeAssistant, msg: dict[str, Any]) -> str | None:
    """Het dashboard waar een opdracht bij hoort.

    Het paneel geeft dat altijd mee. Een oud paneelbestand dat nog in de cache van een
    app of browser staat, doet dat niet. Daarvoor geldt: bestaat er precies één
    dashboard, dan is dat het dashboard. Bij meer dan één kan het niet geraden worden.
    """
    entry_id = msg.get("entry_id")
    if entry_id is not None:
        return entry_id
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    return loaded[0].entry_id if len(loaded) == 1 else None


def _allowed(hass: HomeAssistant, entry_id: str | None) -> frozenset[str]:
    entry = _entry(hass, entry_id)
    return entry.runtime_data.allowed if entry else frozenset()


def _snapshot(state: State) -> dict[str, Any]:
    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }


def _read_html(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


async def _fetch_history(  # pragma: no cover
    hass: HomeAssistant,
    entity_ids: list[str],
    start: datetime,
    end: datetime,
    no_attributes: bool,
) -> dict[str, list[State]]:
    """Standen uit de recorder. Een eigen functie, zodat tests hem kunnen vervangen."""
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.history import get_significant_states

    return await get_instance(hass).async_add_executor_job(
        partial(
            get_significant_states,
            hass,
            start,
            end,
            entity_ids=entity_ids,
            include_start_time_state=True,
            significant_changes_only=True,
            minimal_response=False,
            no_attributes=no_attributes,
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "html_dashboard_base/registry",
        vol.Optional("entry_id"): str,
    }
)
@callback
def ws_registry(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Naam, gebied en type van de toegestane entiteiten van dit dashboard."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    result = []
    for entity_id in sorted(_allowed(hass, _entry_id(hass, msg))):
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "html_dashboard_base/states",
        vol.Optional("entry_id"): str,
    }
)
@callback
def ws_states(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Huidige standen van de toegestane entiteiten van dit dashboard."""
    allowed = _allowed(hass, _entry_id(hass, msg))
    states = (hass.states.get(e) for e in sorted(allowed))
    connection.send_result(msg["id"], [_snapshot(s) for s in states if s])


@websocket_api.websocket_command(
    {
        vol.Required("type"): "html_dashboard_base/subscribe",
        vol.Optional("entry_id"): str,
    }
)
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Wijzigingen van de toegestane entiteiten van dit dashboard doorsturen."""
    entry_id = _entry_id(hass, msg)

    @callback
    def _is_allowed(data: Any) -> bool:
        return data["entity_id"] in _allowed(hass, entry_id)

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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "html_dashboard_base/get_html",
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_html(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Het geüploade bestand van dit dashboard ophalen, of een uitleg als er geen is."""
    entry = _entry(hass, _entry_id(hass, msg))
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Dashboard Base is niet geladen")
        return
    html = await hass.async_add_executor_job(_read_html, entry.runtime_data.html_path)
    if html is None:
        title = entry.options.get(CONF_TITLE, DEFAULT_TITLE)
        html = placeholder_html(title, hass.config.language)
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
        vol.Required("type"): "html_dashboard_base/history",
        vol.Optional("entry_id"): str,
        vol.Required("series"): vol.All(
            [{vol.Required("entity_id"): str, vol.Optional("attribute"): str}],
            vol.Length(min=1, max=MAX_SERIES),
        ),
        vol.Optional("hours", default=24): vol.All(
            int, vol.Range(min=1, max=MAX_HOURS)
        ),
    }
)
@websocket_api.async_response
async def ws_history(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """De geschiedenis van toegestane entiteiten, uitgedund tot een rij punten. Leest alleen."""
    series = msg["series"]
    allowed = _allowed(hass, _entry_id(hass, msg))
    if any(item["entity_id"] not in allowed for item in series):
        connection.send_error(msg["id"], "not_allowed", "Niet toegestaan")
        return
    if "recorder" not in hass.config.components:
        connection.send_error(
            msg["id"], "no_recorder", "De geschiedenis is niet beschikbaar"
        )
        return
    end = dt_util.utcnow()
    start = end - timedelta(hours=msg["hours"])
    states = await _fetch_history(
        hass,
        sorted({item["entity_id"] for item in series}),
        start,
        end,
        not any("attribute" in item for item in series),
    )
    connection.send_result(
        msg["id"],
        [
            {
                "entity_id": item["entity_id"],
                "attribute": item.get("attribute"),
                "points": downsample(
                    states.get(item["entity_id"], []), item.get("attribute"), start, end
                ),
            }
            for item in series
        ],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "html_dashboard_base/forecast",
        vol.Optional("entry_id"): str,
        vol.Required("entity_id"): str,
        vol.Optional("forecast_type"): vol.In(FORECAST_TYPES),
        vol.Optional("hours", default=24): vol.All(
            int, vol.Range(min=1, max=MAX_HOURS)
        ),
    }
)
@websocket_api.async_response
async def ws_forecast(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """De verwachting van een toegestane weerentiteit. Leest alleen."""
    entity_id = msg["entity_id"]
    allowed = _allowed(hass, _entry_id(hass, msg))
    if entity_id not in allowed or entity_id.split(".", 1)[0] != "weather":
        connection.send_error(msg["id"], "not_allowed", "Niet toegestaan")
        return
    types = (msg["forecast_type"],) if "forecast_type" in msg else FORECAST_TYPES
    for forecast_type in types:
        try:
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": entity_id, "type": forecast_type},
                blocking=True,
                return_response=True,
                context=connection.context(msg),
            )
        except HomeAssistantError:
            continue
        items = ((response or {}).get(entity_id) or {}).get("forecast") or []
        points = forecast_points(items, forecast_type, msg["hours"], dt_util.utcnow())
        if points:
            connection.send_result(
                msg["id"], {"type": forecast_type, "points": points}
            )
            return
    connection.send_error(msg["id"], "no_forecast", "Geen verwachting beschikbaar")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "html_dashboard_base/call",
        vol.Optional("entry_id"): str,
        vol.Required("domain"): cv.string,
        vol.Required("service"): cv.string,
        vol.Optional("data", default=dict): dict,
    }
)
@websocket_api.async_response
async def ws_call(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Service aanroepen, alleen voor de toegestane entiteiten van dit dashboard."""
    domain, service, data = msg["domain"], msg["service"], dict(msg["data"])
    allowed = _allowed(hass, _entry_id(hass, msg))
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
        ws_history,
        ws_forecast,
        ws_call,
    ):
        websocket_api.async_register_command(hass, command)
