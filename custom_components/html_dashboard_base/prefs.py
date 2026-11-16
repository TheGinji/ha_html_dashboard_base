"""Gedeelde voorkeuren: één klein JSON-object per dashboard, voor alle apparaten."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import MAX_PREFS_CHARS, PREFS_STORE_KEY, PREFS_STORE_VERSION


class PrefsTooBig(Exception):
    """De voorkeuren van een dashboard zouden samen te groot worden."""


def merge_prefs(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Voeg een wijziging samen met wat er staat: een waarde van None wist die sleutel.

    Geeft een nieuw object terug en laat `current` ongemoeid. Is het resultaat groter dan
    MAX_PREFS_CHARS (als compacte JSON), dan komt PrefsTooBig en blijft alles zoals het was.
    """
    merged = dict(current)
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    if len(json.dumps(merged, separators=(",", ":"), ensure_ascii=False)) > MAX_PREFS_CHARS:
        raise PrefsTooBig
    return merged


class PrefsStore:
    """De voorkeuren van alle dashboards, per instelling (entry_id), op schijf bewaard."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, dict[str, Any]]] = Store(
            hass, PREFS_STORE_VERSION, PREFS_STORE_KEY
        )
        self._data: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        """Lees wat eerder is bewaard. Onbruikbare gegevens tellen als leeg."""
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._data = {k: v for k, v in data.items() if isinstance(v, dict)}

    def get(self, entry_id: str) -> dict[str, Any]:
        """De voorkeuren van dit dashboard. Leeg als er niets is."""
        return dict(self._data.get(entry_id, {}))

    async def async_update(self, entry_id: str, patch: dict[str, Any]) -> None:
        """Voeg een wijziging samen en bewaar. Bij PrefsTooBig verandert er niets."""
        self._data[entry_id] = merge_prefs(self._data.get(entry_id, {}), patch)
        await self._store.async_save(self._snapshot())

    async def async_remove(self, entry_id: str) -> None:
        """Gooi de voorkeuren van een verwijderd dashboard weg."""
        if self._data.pop(entry_id, None) is not None:
            await self._store.async_save(self._snapshot())

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        # Een kopie, want het schrijven gebeurt buiten de event loop.
        return {k: dict(v) for k, v in self._data.items()}
