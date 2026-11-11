"""Tests voor het uitdunnen van geschiedenis en verwachting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from homeassistant.core import State

from custom_components.html_dashboard_base.series import (
    MAX_FORECAST_POINTS,
    MAX_POINTS,
    downsample,
    forecast_points,
    to_number,
    to_timestamp,
)

START = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=4)


def state(value, minutes, attributes=None):
    moment = START + timedelta(minutes=minutes)
    return State(
        "sensor.test",
        str(value),
        attributes or {},
        last_changed=moment,
        last_updated=moment,
    )


def values(points):
    return [point[1] for point in points]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("21.5", 21.5),
        (3, 3.0),
        ("unavailable", None),
        ("unknown", None),
        ("tekst", None),
        (None, None),
        (True, None),
        ("nan", None),
        ("inf", None),
    ],
)
def test_to_number(raw, expected):
    assert to_number(raw) == expected


def test_to_timestamp():
    moment = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    assert to_timestamp("2026-11-03T12:00:00+00:00") == moment.timestamp()
    assert to_timestamp(moment) == moment.timestamp()
    assert to_timestamp("geen datum") is None
    assert to_timestamp(None) is None
    assert to_timestamp(5) is None


def test_constant_value_fills_every_block():
    points = downsample([state(20, 0)], None, START, END, max_points=4)

    assert values(points) == [20.0, 20.0, 20.0, 20.0]
    assert [point[0] for point in points] == [
        int((START + timedelta(hours=h)).timestamp() * 1000) for h in (1, 2, 3, 4)
    ]


def test_step_change_is_averaged_in_its_block():
    points = downsample([state(10, 0), state(20, 120)], None, START, END, max_points=4)

    assert values(points) == [10.0, 10.0, 15.0, 20.0]


def test_unavailable_breaks_the_line():
    states = [state(10, 0), state("unavailable", 60), state(30, 180)]

    points = downsample(states, None, START, END, max_points=4)

    assert values(points) == [10.0, 10.0, None, 30.0]


def test_state_from_before_the_start_is_carried_forward():
    points = downsample([state(5, -30)], None, START, END, max_points=4)

    assert values(points) == [5.0, 5.0, 5.0, 5.0]


def test_change_exactly_at_the_end_counts_in_the_last_block():
    points = downsample([state(10, 0), state(30, 240)], None, START, END, max_points=4)

    assert values(points) == [10.0, 10.0, 10.0, 20.0]


def test_unsorted_input_is_sorted():
    points = downsample([state(20, 120), state(10, 0)], None, START, END, max_points=4)

    assert values(points) == [10.0, 10.0, 15.0, 20.0]


def test_attribute_series_uses_the_attribute_not_the_state():
    states = [
        state("heat", 0, {"current_temperature": 20.5}),
        state("heat", 120, {"current_temperature": 21.5}),
        state("heat", 180, {}),
    ]

    points = downsample(states, "current_temperature", START, END, max_points=4)

    assert values(points) == [20.5, 20.5, 21.0, 21.5]


def test_without_usable_values_the_result_is_empty():
    assert downsample([state("unavailable", 0), state("unknown", 30)], None, START, END) == []
    assert downsample([], None, START, END) == []


def test_default_number_of_points():
    points = downsample([state(1, 0)], None, START, START + timedelta(hours=24))

    assert len(points) == MAX_POINTS


def test_values_are_rounded_to_two_decimals():
    points = downsample([state(20.12345, 0)], None, START, END, max_points=4)

    assert values(points)[0] == 20.12


def hour_items(first, last):
    return [
        {
            "datetime": (START + timedelta(hours=hour)).isoformat(),
            "temperature": float(hour),
        }
        for hour in range(first, last + 1)
    ]


def test_hourly_forecast_keeps_the_coming_hours():
    points = forecast_points(hour_items(-3, 30), "hourly", 24, START)

    hours = [point[1] for point in points]
    assert hours[0] == -1.0
    assert hours[-1] == 24.0
    assert len(points) == 26
    assert all(point[2] is None for point in points)


def test_daily_forecast_keeps_every_day_and_the_low_temperature():
    items = [
        {
            "datetime": (START + timedelta(days=day)).isoformat(),
            "temperature": 10.0 + day,
            "templow": 2.0 + day,
        }
        for day in range(7)
    ]

    points = forecast_points(items, "daily", 24, START)

    assert len(points) == 7
    assert points[0][1:] == [10.0, 2.0]
    assert points[6][1:] == [16.0, 8.0]


def test_forecast_is_sorted_and_skips_unusable_items():
    items = list(reversed(hour_items(0, 3))) + [
        {"datetime": START.isoformat()},
        {"datetime": "geen datum", "temperature": 5.0},
        {"datetime": START.isoformat(), "temperature": "tekst"},
    ]

    points = forecast_points(items, "hourly", 24, START)

    assert [point[1] for point in points] == [0.0, 1.0, 2.0, 3.0]


def test_forecast_accepts_datetime_objects_and_rounds():
    items = [{"datetime": START + timedelta(hours=1), "temperature": 7.26}]

    points = forecast_points(items, "hourly", 24, START)

    assert points == [[int((START + timedelta(hours=1)).timestamp() * 1000), 7.3, None]]


def test_forecast_is_capped():
    items = [
        {"datetime": (START + timedelta(days=day)).isoformat(), "temperature": 1.0}
        for day in range(MAX_FORECAST_POINTS + 12)
    ]

    assert len(forecast_points(items, "daily", 24, START)) == MAX_FORECAST_POINTS
