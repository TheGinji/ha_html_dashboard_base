"""Tests voor de leesfuncties history en forecast."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import Context, HomeAssistant, State, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.html_dashboard_base import api
from custom_components.html_dashboard_base.const import (
    CONF_DASHBOARD_ID,
    CONF_ENTITIES,
    CONF_PANEL_URL,
    CONF_TITLE,
    DOMAIN,
)
from custom_components.html_dashboard_base.series import MAX_POINTS

FETCH = "custom_components.html_dashboard_base.api._fetch_history"
WEATHER_ENTITIES = ["weather.thuis", "sensor.binnen", "climate.aquarea", "light.keuken"]


def make_connection() -> MagicMock:
    connection = MagicMock()
    connection.subscriptions = {}
    connection.context.return_value = Context(user_id="user-1")
    return connection


def msg(command: str, entry: MockConfigEntry | str, **extra: Any) -> dict[str, Any]:
    entry_id = entry if isinstance(entry, str) else entry.entry_id
    return {"id": 1, "type": f"{DOMAIN}/{command}", "entry_id": entry_id, **extra}


def new_weather_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Weer",
        version=2,
        data={CONF_DASHBOARD_ID: "weer", CONF_PANEL_URL: "dashboard-weer"},
        options={CONF_TITLE: "Weer", CONF_ENTITIES: list(WEATHER_ENTITIES)},
    )


@pytest.fixture
async def weather_entry(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> MockConfigEntry:
    """Een dashboard met een weerentiteit, een sensor en een thermostaat."""
    entry = new_weather_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def recorder_present(hass: HomeAssistant) -> None:
    hass.config.components.add("recorder")


def reading(entity_id: str, value: Any, moment: datetime, attributes=None) -> State:
    return State(
        entity_id,
        str(value),
        attributes or {},
        last_changed=moment,
        last_updated=moment,
    )


async def test_history_returns_downsampled_points(
    hass: HomeAssistant, weather_entry: MockConfigEntry, recorder_present: None
) -> None:
    """De recorder levert standen, het dashboard krijgt een korte rij punten."""
    now = dt_util.utcnow()
    states = {
        "sensor.binnen": [
            reading("sensor.binnen", 20, now - timedelta(hours=30)),
            reading("sensor.binnen", 22, now - timedelta(hours=1)),
        ]
    }
    fetch = AsyncMock(return_value=states)
    connection = make_connection()

    with patch(FETCH, fetch):
        api.ws_history(
            hass,
            connection,
            msg("history", weather_entry, series=[{"entity_id": "sensor.binnen"}], hours=24),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    result = connection.send_result.call_args.args[1]
    assert len(result) == 1
    assert result[0]["entity_id"] == "sensor.binnen"
    assert result[0]["attribute"] is None
    points = result[0]["points"]
    assert len(points) == MAX_POINTS
    assert points[0][1] == 20.0
    assert points[-1][1] == 22.0
    fetch.assert_awaited_once()
    _, entity_ids, start, end, no_attributes = fetch.await_args.args
    assert entity_ids == ["sensor.binnen"]
    assert end - start == timedelta(hours=24)
    assert no_attributes is True


async def test_history_of_attributes_asks_for_them(
    hass: HomeAssistant, weather_entry: MockConfigEntry, recorder_present: None
) -> None:
    """Twee lijnen van een thermostaat: gemeten en gewenst, uit dezelfde standen."""
    now = dt_util.utcnow()
    states = {
        "climate.aquarea": [
            reading(
                "climate.aquarea",
                "heat",
                now - timedelta(hours=2),
                {"current_temperature": 20.5, "temperature": 21},
            )
        ]
    }
    fetch = AsyncMock(return_value=states)
    connection = make_connection()

    with patch(FETCH, fetch):
        api.ws_history(
            hass,
            connection,
            msg(
                "history",
                weather_entry,
                series=[
                    {"entity_id": "climate.aquarea", "attribute": "current_temperature"},
                    {"entity_id": "climate.aquarea", "attribute": "temperature"},
                ],
                hours=6,
            ),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    result = connection.send_result.call_args.args[1]
    assert [item["attribute"] for item in result] == ["current_temperature", "temperature"]
    assert result[0]["points"][-1][1] == 20.5
    assert result[1]["points"][-1][1] == 21.0
    _, entity_ids, _, _, no_attributes = fetch.await_args.args
    assert entity_ids == ["climate.aquarea"]
    assert no_attributes is False


async def test_history_without_recorded_data_gives_empty_points(
    hass: HomeAssistant, weather_entry: MockConfigEntry, recorder_present: None
) -> None:
    """Een entiteit die niet wordt vastgelegd geeft een lege lijn, geen fout."""
    connection = make_connection()

    with patch(FETCH, AsyncMock(return_value={})):
        api.ws_history(
            hass,
            connection,
            msg("history", weather_entry, series=[{"entity_id": "sensor.binnen"}], hours=24),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert connection.send_result.call_args.args[1] == [
        {"entity_id": "sensor.binnen", "attribute": None, "points": []}
    ]


async def test_history_refuses_entities_outside_the_list(
    hass: HomeAssistant, weather_entry: MockConfigEntry, recorder_present: None
) -> None:
    fetch = AsyncMock(return_value={})
    connection = make_connection()

    with patch(FETCH, fetch):
        api.ws_history(
            hass,
            connection,
            msg(
                "history",
                weather_entry,
                series=[{"entity_id": "sensor.binnen"}, {"entity_id": "sensor.geheim"}],
                hours=24,
            ),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert connection.send_error.call_args.args[1] == "not_allowed"
    fetch.assert_not_called()


async def test_history_for_an_unknown_dashboard_is_refused(
    hass: HomeAssistant, weather_entry: MockConfigEntry, recorder_present: None
) -> None:
    fetch = AsyncMock(return_value={})
    connection = make_connection()

    with patch(FETCH, fetch):
        api.ws_history(
            hass,
            connection,
            msg("history", "bestaat-niet", series=[{"entity_id": "sensor.binnen"}], hours=24),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert connection.send_error.call_args.args[1] == "not_allowed"
    fetch.assert_not_called()


async def test_history_without_recorder(
    hass: HomeAssistant, weather_entry: MockConfigEntry
) -> None:
    hass.config.components.discard("recorder")
    fetch = AsyncMock(return_value={})
    connection = make_connection()

    with patch(FETCH, fetch):
        api.ws_history(
            hass,
            connection,
            msg("history", weather_entry, series=[{"entity_id": "sensor.binnen"}], hours=24),
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    assert connection.send_error.call_args.args[1] == "no_recorder"
    fetch.assert_not_called()


async def test_fetch_history_calls_the_recorder(hass: HomeAssistant) -> None:
    """De dunne laag om de recorder geeft de juiste opties door."""
    pytest.importorskip("homeassistant.components.recorder.history")
    instance = MagicMock()
    instance.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    get_states = MagicMock(return_value={"sensor.binnen": []})
    start = dt_util.utcnow()
    end = start + timedelta(hours=1)

    with (
        patch("homeassistant.components.recorder.get_instance", return_value=instance),
        patch("homeassistant.components.recorder.history.get_significant_states", get_states),
    ):
        result = await api._fetch_history(hass, ["sensor.binnen"], start, end, True)

    assert result == {"sensor.binnen": []}
    get_states.assert_called_once_with(
        hass,
        start,
        end,
        entity_ids=["sensor.binnen"],
        include_start_time_state=True,
        significant_changes_only=True,
        minimal_response=False,
        no_attributes=True,
    )


def register_forecasts(hass: HomeAssistant, answers: dict[str, list]) -> list[str]:
    """Registreer een nagebootste weer.get_forecasts. Geeft de gevraagde types terug."""
    asked: list[str] = []

    async def handler(call):
        forecast_type = call.data["type"]
        asked.append(forecast_type)
        if forecast_type not in answers:
            raise ServiceValidationError("Dit type wordt niet ondersteund")
        return {call.data["entity_id"]: {"forecast": answers[forecast_type]}}

    hass.services.async_register(
        "weather", "get_forecasts", handler, supports_response=SupportsResponse.ONLY
    )
    return asked


def hourly_items(first: int, last: int) -> list[dict[str, Any]]:
    """Uurwaarden een half uur voor het hele uur, zodat de grenzen niet op de milliseconde vallen."""
    now = dt_util.utcnow()
    return [
        {
            "datetime": (now + timedelta(hours=hour - 0.5)).isoformat(),
            "temperature": float(hour),
        }
        for hour in range(first, last + 1)
    ]


def daily_items(days: int) -> list[dict[str, Any]]:
    now = dt_util.utcnow()
    return [
        {
            "datetime": (now + timedelta(days=day)).isoformat(),
            "temperature": 10.0 + day,
            "templow": 2.0 + day,
        }
        for day in range(days)
    ]


async def run_forecast(hass, entry, **extra) -> MagicMock:
    connection = make_connection()
    api.ws_forecast(
        hass,
        connection,
        msg("forecast", entry, entity_id="weather.thuis", hours=24, **extra),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    return connection


async def test_hourly_forecast_covers_the_next_24_hours(
    hass: HomeAssistant, weather_entry: MockConfigEntry
) -> None:
    asked = register_forecasts(hass, {"hourly": hourly_items(-3, 40)})

    connection = await run_forecast(hass, weather_entry)

    result = connection.send_result.call_args.args[1]
    assert result["type"] == "hourly"
    assert asked == ["hourly"]
    temperatures = [point[1] for point in result["points"]]
    assert temperatures[0] == 0.0
    assert temperatures[-1] == 24.0
    assert len(temperatures) == 25
    assert all(point[2] is None for point in result["points"])


async def test_forecast_falls_back_to_daily(
    hass: HomeAssistant, weather_entry: MockConfigEntry
) -> None:
    """Geeft de weerintegratie geen uren, dan komen de dagen met laagste temperatuur."""
    asked = register_forecasts(hass, {"daily": daily_items(5)})

    connection = await run_forecast(hass, weather_entry)

    result = connection.send_result.call_args.args[1]
    assert asked == ["hourly", "daily"]
    assert result["type"] == "daily"
    assert len(result["points"]) == 5
    assert result["points"][0][1:] == [10.0, 2.0]


async def test_forecast_skips_an_empty_answer(
    hass: HomeAssistant, weather_entry: MockConfigEntry
) -> None:
    asked = register_forecasts(hass, {"hourly": [], "daily": daily_items(3)})

    connection = await run_forecast(hass, weather_entry)

    assert asked == ["hourly", "daily"]
    assert connection.send_result.call_args.args[1]["type"] == "daily"


async def test_forecast_uses_the_requested_type_only(
    hass: HomeAssistant, weather_entry: MockConfigEntry
) -> None:
    asked = register_forecasts(
        hass, {"hourly": hourly_items(0, 5), "twice_daily": daily_items(4)}
    )

    connection = await run_forecast(hass, weather_entry, forecast_type="twice_daily")

    assert asked == ["twice_daily"]
    assert connection.send_result.call_args.args[1]["type"] == "twice_daily"


async def test_forecast_without_any_supported_type(
    hass: HomeAssistant, weather_entry: MockConfigEntry
) -> None:
    asked = register_forecasts(hass, {})

    connection = await run_forecast(hass, weather_entry)

    assert asked == ["hourly", "daily", "twice_daily"]
    assert connection.send_error.call_args.args[1] == "no_forecast"


async def test_forecast_without_a_weather_integration(
    hass: HomeAssistant, weather_entry: MockConfigEntry
) -> None:
    """Zonder weer.get_forecasts blijft het bij een nette melding."""
    connection = await run_forecast(hass, weather_entry)

    assert connection.send_error.call_args.args[1] == "no_forecast"


@pytest.mark.parametrize("entity_id", ["weather.geheim", "sensor.binnen", "light.keuken"])
async def test_forecast_only_for_allowed_weather_entities(
    hass: HomeAssistant, weather_entry: MockConfigEntry, entity_id: str
) -> None:
    asked = register_forecasts(hass, {"hourly": hourly_items(0, 5)})
    connection = make_connection()

    api.ws_forecast(
        hass, connection, msg("forecast", weather_entry, entity_id=entity_id, hours=24)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert connection.send_error.call_args.args[1] == "not_allowed"
    assert asked == []


@pytest.fixture
async def client(
    hass: HomeAssistant,
    hass_ws_client,
    panel_mocks,
    html_path,
    mock_entry: MockConfigEntry,
):
    """Een ingelogde websocket-client, met het eerste dashboard geladen."""
    ws = await hass_ws_client(hass)
    hass.config.components.update(("frontend", "panel_custom", "file_upload"))
    hass.http.async_register_static_paths = AsyncMock()
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    return ws


async def test_history_over_websocket_uses_24_hours_by_default(
    hass: HomeAssistant, client, mock_entry: MockConfigEntry, recorder_present: None
) -> None:
    fetch = AsyncMock(return_value={})

    with patch(FETCH, fetch):
        await client.send_json(
            {
                "id": 1,
                "type": f"{DOMAIN}/history",
                "entry_id": mock_entry.entry_id,
                "series": [{"entity_id": "sensor.buiten"}],
            }
        )
        reply = await client.receive_json()

    assert reply["success"]
    assert reply["result"] == [
        {"entity_id": "sensor.buiten", "attribute": None, "points": []}
    ]
    _, _, start, end, _ = fetch.await_args.args
    assert end - start == timedelta(hours=24)


@pytest.mark.parametrize(
    "extra",
    [
        {"series": []},
        {"series": [{"entity_id": f"sensor.s{n}"} for n in range(9)]},
        {"series": [{"entity_id": "sensor.buiten", "extra": 1}]},
        {"series": [{"attribute": "temperature"}]},
        {"series": [{"entity_id": "sensor.buiten"}], "hours": 0},
        {"series": [{"entity_id": "sensor.buiten"}], "hours": 169},
        {"series": [{"entity_id": "sensor.buiten"}], "hours": "veel"},
        {},
    ],
    ids=[
        "leeg",
        "te_veel",
        "extra_veld",
        "zonder_entiteit",
        "nul_uur",
        "te_lang",
        "geen_getal",
        "zonder_reeks",
    ],
)
async def test_history_rejects_invalid_requests(
    hass: HomeAssistant, client, mock_entry: MockConfigEntry, extra: dict[str, Any]
) -> None:
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/history", "entry_id": mock_entry.entry_id, **extra}
    )
    reply = await client.receive_json()

    assert not reply["success"]
    assert reply["error"]["code"] == "invalid_format"


async def test_forecast_over_websocket(
    hass: HomeAssistant, client
) -> None:
    entry = new_weather_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    register_forecasts(hass, {"hourly": hourly_items(0, 30)})

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/forecast",
            "entry_id": entry.entry_id,
            "entity_id": "weather.thuis",
        }
    )
    reply = await client.receive_json()

    assert reply["success"]
    assert reply["result"]["type"] == "hourly"
    assert 24 <= len(reply["result"]["points"]) <= 26


async def test_forecast_rejects_an_unknown_type(
    hass: HomeAssistant, client, mock_entry: MockConfigEntry
) -> None:
    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/forecast",
            "entry_id": mock_entry.entry_id,
            "entity_id": "weather.thuis",
            "forecast_type": "wekelijks",
        }
    )
    reply = await client.receive_json()

    assert not reply["success"]
    assert reply["error"]["code"] == "invalid_format"
