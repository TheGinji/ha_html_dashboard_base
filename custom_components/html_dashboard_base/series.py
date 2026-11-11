"""Geschiedenis en verwachting voor grafieken, uitgedund tot een klein aantal punten."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
import math
from typing import Any

from homeassistant.core import State
from homeassistant.util import dt as dt_util

MAX_POINTS = 144
MAX_SERIES = 8
MAX_HOURS = 168
MAX_FORECAST_POINTS = 48
FORECAST_TYPES = ("hourly", "daily", "twice_daily")


def to_number(value: Any) -> float | None:
    """Een getal, of None bij unavailable, unknown, tekst of een onbruikbare waarde."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def to_timestamp(value: Any) -> float | None:
    """Een tijdstip in seconden, uit een datetime of een tekst, of None."""
    if isinstance(value, str):
        value = dt_util.parse_datetime(value)
    if isinstance(value, datetime):
        return dt_util.as_utc(value).timestamp()
    return None


def downsample(
    states: Sequence[State],
    attribute: str | None,
    start: datetime,
    end: datetime,
    max_points: int = MAX_POINTS,
) -> list[list[float | None]]:
    """Maak van de standen een rij [tijd in ms, waarde] met vaste tussenpozen.

    Per blok telt het gemiddelde van de waarde aan het begin van het blok en van de
    wijzigingen in dat blok. Een blok zonder bruikbare waarde (unavailable of onbekend)
    krijgt None, zodat de lijn daar onderbroken wordt. Er wordt niets verzonnen: zonder
    enige bruikbare waarde komt er een lege lijst terug.
    """
    observations = sorted(
        (
            (
                state.last_updated.timestamp(),
                to_number(state.attributes.get(attribute) if attribute else state.state),
            )
            for state in states
        ),
        key=lambda item: item[0],
    )
    if all(value is None for _, value in observations):
        return []
    start_ts, end_ts = start.timestamp(), end.timestamp()
    width = (end_ts - start_ts) / max_points
    index, carried = 0, None
    while index < len(observations) and observations[index][0] <= start_ts:
        carried = observations[index][1]
        index += 1
    points: list[list[float | None]] = []
    for block in range(max_points):
        block_end = start_ts + (block + 1) * width
        values = [carried]
        while index < len(observations) and (
            observations[index][0] < block_end or block == max_points - 1
        ):
            carried = observations[index][1]
            values.append(carried)
            index += 1
        numbers = [value for value in values if value is not None]
        points.append(
            [
                int(block_end * 1000),
                round(sum(numbers) / len(numbers), 2) if numbers else None,
            ]
        )
    return points


def forecast_points(
    items: Sequence[dict[str, Any]], forecast_type: str, hours: int, now: datetime
) -> list[list[float | None]]:
    """Maak van een verwachting een rij [tijd in ms, temperatuur, laagste temperatuur].

    Per uur gaat het om de komende uren, inclusief het uur waar je nu in zit. Per dag of
    per halve dag blijven alle dagen staan. De laagste temperatuur is er alleen bij een
    verwachting per dag of halve dag.
    """
    points: list[list[float | None]] = []
    for item in items:
        timestamp = to_timestamp(item.get("datetime"))
        temperature = to_number(item.get("temperature"))
        if timestamp is None or temperature is None:
            continue
        low = to_number(item.get("templow"))
        points.append(
            [
                int(timestamp * 1000),
                round(temperature, 1),
                round(low, 1) if low is not None else None,
            ]
        )
    points.sort(key=lambda point: point[0])
    if forecast_type == "hourly":
        first = (now.timestamp() - 3600) * 1000
        last = (now.timestamp() + hours * 3600) * 1000
        points = [point for point in points if first <= point[0] <= last]
    return points[:MAX_FORECAST_POINTS]
