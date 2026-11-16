"""Tests voor de gedeelde voorkeuren (sharedPrefs): samenvoegen, bewaren en de websocket-opdracht."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base import async_remove_entry
from custom_components.html_dashboard_base.const import (
    DATA_PREFS,
    DOMAIN,
    MAX_PREFS_CHARS,
)
from custom_components.html_dashboard_base.prefs import (
    PrefsStore,
    PrefsTooBig,
    merge_prefs,
)

TYPE = f"{DOMAIN}/shared_prefs"


@pytest.fixture
async def client(
    hass: HomeAssistant,
    hass_ws_client,
    panel_mocks: tuple[AsyncMock, MagicMock],
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


async def _send(client, msg_id: int, **fields):
    await client.send_json({"id": msg_id, "type": TYPE, **fields})
    return await client.receive_json()


# --- samenvoegen ---------------------------------------------------------------


def test_merge_adds_and_replaces() -> None:
    assert merge_prefs({"a": 1, "b": 2}, {"b": 3, "c": [1]}) == {"a": 1, "b": 3, "c": [1]}


def test_merge_none_deletes_a_key() -> None:
    assert merge_prefs({"a": 1, "b": 2}, {"a": None, "zzz": None}) == {"b": 2}


def test_merge_leaves_current_untouched() -> None:
    current = {"a": 1}
    merged = merge_prefs(current, {"a": 2})
    assert current == {"a": 1}
    assert merged == {"a": 2}


def test_merge_limit_counts_compact_json() -> None:
    """`{"k":"x"}` is 9 tekens: precies op de grens mag nog, één teken meer niet."""
    assert merge_prefs({}, {"k": "x" * (MAX_PREFS_CHARS - 8)})
    with pytest.raises(PrefsTooBig):
        merge_prefs({}, {"k": "x" * (MAX_PREFS_CHARS - 7)})


# --- opslag --------------------------------------------------------------------


async def test_store_starts_empty(hass: HomeAssistant) -> None:
    store = PrefsStore(hass)
    await store.async_load()
    assert store.get("e1") == {}


async def test_store_keeps_values_after_reloading(hass: HomeAssistant) -> None:
    """Wat een eerste opslag bewaart, ziet een nieuwe opslag weer (zoals na een herstart)."""
    first = PrefsStore(hass)
    await first.async_load()
    await first.async_update("e1", {"a": 1, "b": {"c": [1, 2]}})
    await first.async_update("e2", {"x": "y"})

    second = PrefsStore(hass)
    await second.async_load()

    assert second.get("e1") == {"a": 1, "b": {"c": [1, 2]}}
    assert second.get("e2") == {"x": "y"}


async def test_store_too_big_changes_nothing(hass: HomeAssistant) -> None:
    store = PrefsStore(hass)
    await store.async_load()
    await store.async_update("e1", {"a": 1})

    with pytest.raises(PrefsTooBig):
        await store.async_update("e1", {"b": "x" * (MAX_PREFS_CHARS + 1)})

    assert store.get("e1") == {"a": 1}


async def test_store_get_returns_a_copy(hass: HomeAssistant) -> None:
    store = PrefsStore(hass)
    await store.async_load()
    await store.async_update("e1", {"a": 1})

    store.get("e1")["a"] = 99

    assert store.get("e1") == {"a": 1}


async def test_store_remove(hass: HomeAssistant) -> None:
    store = PrefsStore(hass)
    await store.async_load()
    await store.async_update("e1", {"a": 1})
    await store.async_update("e2", {"b": 2})

    await store.async_remove("e1")
    await store.async_remove("onbekend")  # geen fout

    again = PrefsStore(hass)
    await again.async_load()
    assert again.get("e1") == {}
    assert again.get("e2") == {"b": 2}


# --- websocket -----------------------------------------------------------------


async def test_read_is_empty_at_first(client, mock_entry: MockConfigEntry) -> None:
    msg = await _send(client, 1, entry_id=mock_entry.entry_id)

    assert msg["success"]
    assert msg["result"] == {}


async def test_set_merge_and_delete(client, mock_entry: MockConfigEntry) -> None:
    eid = mock_entry.entry_id

    msg = await _send(client, 1, entry_id=eid, patch={"a": 1, "b": [1, 2]})
    assert msg["success"]
    assert msg["result"] == {"a": 1, "b": [1, 2]}

    msg = await _send(client, 2, entry_id=eid, patch={"a": None, "c": "x"})
    assert msg["result"] == {"b": [1, 2], "c": "x"}

    msg = await _send(client, 3, entry_id=eid)
    assert msg["result"] == {"b": [1, 2], "c": "x"}

    msg = await _send(client, 4, entry_id=eid, patch=None)
    assert msg["result"] == {"b": [1, 2], "c": "x"}


async def test_set_survives_reloading_the_dashboard(
    hass: HomeAssistant, client, mock_entry: MockConfigEntry
) -> None:
    """Het dashboard opnieuw laden (bijvoorbeeld na een wijziging van de lijst) wist niets."""
    await _send(client, 1, entry_id=mock_entry.entry_id, patch={"a": 1})

    assert await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()

    msg = await _send(client, 2, entry_id=mock_entry.entry_id)
    assert msg["result"] == {"a": 1}


async def test_set_is_written_to_storage(
    hass: HomeAssistant, client, mock_entry: MockConfigEntry
) -> None:
    await _send(client, 1, entry_id=mock_entry.entry_id, patch={"a": 1})

    fresh = PrefsStore(hass)
    await fresh.async_load()

    assert fresh.get(mock_entry.entry_id) == {"a": 1}


async def test_too_big_is_refused_and_keeps_what_was_there(
    client, mock_entry: MockConfigEntry
) -> None:
    eid = mock_entry.entry_id
    await _send(client, 1, entry_id=eid, patch={"a": 1})

    msg = await _send(client, 2, entry_id=eid, patch={"b": "x" * (MAX_PREFS_CHARS + 1)})

    assert not msg["success"]
    assert msg["error"]["code"] == "too_big"
    msg = await _send(client, 3, entry_id=eid)
    assert msg["result"] == {"a": 1}


async def test_unknown_dashboard(client) -> None:
    msg = await _send(client, 1, entry_id="bestaat-niet", patch={"a": 1})

    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_patch_must_be_an_object(client, mock_entry: MockConfigEntry) -> None:
    msg = await _send(client, 1, entry_id=mock_entry.entry_id, patch="tekst")

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"


async def test_without_entry_id_uses_the_only_dashboard(
    client, mock_entry: MockConfigEntry
) -> None:
    """Een oud paneelbestand stuurt geen id mee: met één dashboard werkt dat nog."""
    msg = await _send(client, 1, patch={"a": 1})
    assert msg["success"]

    msg = await _send(client, 2, entry_id=mock_entry.entry_id)
    assert msg["result"] == {"a": 1}


async def test_two_dashboards_do_not_share_preferences(
    hass: HomeAssistant,
    client,
    mock_entry: MockConfigEntry,
    second_mock_entry: MockConfigEntry,
) -> None:
    second_mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_mock_entry.entry_id)
    await hass.async_block_till_done()

    await _send(client, 1, entry_id=mock_entry.entry_id, patch={"a": 1})

    msg = await _send(client, 2, entry_id=second_mock_entry.entry_id)
    assert msg["result"] == {}
    msg = await _send(client, 3, entry_id=mock_entry.entry_id)
    assert msg["result"] == {"a": 1}


async def test_removing_a_dashboard_drops_its_preferences(
    hass: HomeAssistant,
    client,
    mock_entry: MockConfigEntry,
    second_mock_entry: MockConfigEntry,
) -> None:
    second_mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_mock_entry.entry_id)
    await hass.async_block_till_done()
    await _send(client, 1, entry_id=mock_entry.entry_id, patch={"a": 1})
    await _send(client, 2, entry_id=second_mock_entry.entry_id, patch={"b": 2})

    await hass.config_entries.async_remove(second_mock_entry.entry_id)
    await hass.async_block_till_done()

    store = hass.data[DATA_PREFS]
    assert store.get(second_mock_entry.entry_id) == {}
    assert store.get(mock_entry.entry_id) == {"a": 1}


async def test_removing_a_dashboard_before_the_store_exists(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Een instelling die nooit is gestart (de integratie is niet opgestart) is toch te verwijderen."""
    mock_entry.add_to_hass(hass)
    hass.data.pop(DATA_PREFS, None)

    await async_remove_entry(hass, mock_entry)
