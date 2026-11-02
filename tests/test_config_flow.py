"""Tests voor de config flow en de opties."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.html_dashboard_base.const import (
    CONF_DASHBOARD_ID,
    CONF_ENTITIES,
    CONF_HTML,
    CONF_PANEL_URL,
    CONF_REMOVE_HTML,
    CONF_TITLE,
    DOMAIN,
    MAX_DASHBOARDS,
)
from custom_components.html_dashboard_base.util import html_file

from .helpers import file_exists, list_files, read_file, write_file

FILE_ID = "11111111-1111-1111-1111-111111111111"
UPLOAD_TARGET = (
    "custom_components.html_dashboard_base.config_flow.process_uploaded_file"
)
MAX_TARGET = "custom_components.html_dashboard_base.config_flow.MAX_HTML_BYTES"
HEX_ID = re.compile(r"^[0-9a-f]{32}$")


@contextmanager
def _uploaded(path: Path) -> Iterator[Path]:
    yield path


def patch_upload(path: Path):
    """Laat het uploaden van een bestand naar dit pad wijzen."""
    return patch(UPLOAD_TARGET, return_value=_uploaded(path))


async def start_user_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def test_user_flow_without_upload(
    hass: HomeAssistant,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_dir: Path,
) -> None:
    """Een dashboard zonder bestand: de instelling wordt aangemaakt."""
    flow_id = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_TITLE: "Thuis", CONF_ENTITIES: ["light.keuken"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thuis"
    assert HEX_ID.match(result["data"][CONF_DASHBOARD_ID])
    assert result["data"][CONF_PANEL_URL] == "dashboard-thuis"
    assert result["options"] == {
        CONF_TITLE: "Thuis",
        CONF_ENTITIES: ["light.keuken"],
    }
    assert await list_files(hass, html_dir) == []


async def test_user_flow_with_upload(
    hass: HomeAssistant,
    tmp_path: Path,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_dir: Path,
) -> None:
    """Een geuploade pagina wordt onder het id van dit dashboard opgeslagen."""
    upload = tmp_path / "upload.html"
    await write_file(hass, upload, "<html><body>hoi</body></html>")
    flow_id = await start_user_flow(hass)

    with patch_upload(upload):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_TITLE: "Thuis", CONF_HTML: FILE_ID}
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_TITLE: "Thuis", CONF_ENTITIES: []}
    dashboard_id = result["data"][CONF_DASHBOARD_ID]
    assert await list_files(hass, html_dir) == [f"{dashboard_id}.html"]
    saved = html_file(hass, dashboard_id)
    assert await read_file(hass, saved) == "<html><body>hoi</body></html>"


@pytest.mark.parametrize(
    ("payload", "max_bytes", "error"),
    [
        (b"<html>" + b"x" * 50, 10, "html_too_large"),
        (b"\xff\xfe\xfd", 1000, "html_invalid"),
        (b"geen markup", 1000, "html_invalid"),
    ],
    ids=["te_groot", "geen_utf8", "geen_html"],
)
async def test_user_flow_upload_errors(
    hass: HomeAssistant,
    tmp_path: Path,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_dir: Path,
    payload: bytes,
    max_bytes: int,
    error: str,
) -> None:
    """Een ongeldig bestand geeft een fout en wordt niet opgeslagen."""
    upload = tmp_path / "upload.html"
    await write_file(hass, upload, payload)
    flow_id = await start_user_flow(hass)

    with patch_upload(upload), patch(MAX_TARGET, max_bytes):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_TITLE: "Thuis", CONF_HTML: FILE_ID}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}
    assert await list_files(hass, html_dir) == []
    assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Thuis", "dashboard-thuis"),
        ("Technische ruimte", "dashboard-technische-ruimte"),
    ],
)
async def test_panel_url_from_title(
    hass: HomeAssistant,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_dir: Path,
    title: str,
    expected: str,
) -> None:
    flow_id = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_TITLE: title}
    )

    assert result["data"][CONF_PANEL_URL] == expected


async def test_second_dashboard_gets_unique_panel_url(
    hass: HomeAssistant,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_dir: Path,
) -> None:
    """Twee dashboards met dezelfde naam krijgen verschillende adressen."""
    urls = []
    for _ in range(2):
        flow_id = await start_user_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_TITLE: "Thuis"}
        )
        await hass.async_block_till_done()
        urls.append(result["data"][CONF_PANEL_URL])

    assert urls == ["dashboard-thuis", "dashboard-thuis-2"]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_max_dashboards(
    hass: HomeAssistant, skip_dependencies: None
) -> None:
    """Bij het maximum aantal dashboards stopt het formulier met een melding."""
    for number in range(MAX_DASHBOARDS):
        MockConfigEntry(
            domain=DOMAIN,
            version=2,
            data={
                CONF_DASHBOARD_ID: f"d{number}",
                CONF_PANEL_URL: f"dashboard-{number}",
            },
            options={CONF_TITLE: f"D{number}"},
        ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "max_dashboards"


async def test_options_flow_shows_current_file(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    """In de opties staat welk bestand er nu geladen is."""
    await write_file(hass, html_path, "<title>Mijn paneel</title>")

    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "Mijn paneel" in result["description_placeholders"]["current"]


async def test_options_flow_without_file(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    assert result["description_placeholders"] == {"current": "\u2013"}


async def test_options_flow_updates(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Titel en entiteiten zijn aan te passen."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_TITLE: "Nieuw", CONF_ENTITIES: ["light.keuken", "scene.weg"]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_entry.options == {
        CONF_TITLE: "Nieuw",
        CONF_ENTITIES: ["light.keuken", "scene.weg"],
    }
    assert setup_entry.runtime_data.allowed == frozenset(
        {"light.keuken", "scene.weg"}
    )


async def test_options_flow_replaces_upload(
    hass: HomeAssistant,
    tmp_path: Path,
    setup_entry: MockConfigEntry,
    html_path: Path,
) -> None:
    """Een nieuw bestand vervangt het huidige dashboard."""
    await write_file(hass, html_path, "<html>oud</html>")
    upload = tmp_path / "upload.html"
    await write_file(hass, upload, "<html>nieuw</html>")

    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    with patch_upload(upload):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_TITLE: "Dashboard", CONF_HTML: FILE_ID},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert await read_file(hass, html_path) == "<html>nieuw</html>"


async def test_options_flow_removes_file(
    hass: HomeAssistant, setup_entry: MockConfigEntry, html_path: Path
) -> None:
    """Met het vakje Verwijderen wordt het opgeslagen bestand gewist."""
    await write_file(hass, html_path, "<html>oud</html>")

    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_TITLE: "Dashboard", CONF_REMOVE_HTML: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not await file_exists(hass, html_path)


async def test_options_flow_new_file_wins_over_remove(
    hass: HomeAssistant,
    tmp_path: Path,
    setup_entry: MockConfigEntry,
    html_path: Path,
) -> None:
    """Kies je tegelijk een nieuw bestand en Verwijderen, dan blijft het nieuwe."""
    await write_file(hass, html_path, "<html>oud</html>")
    upload = tmp_path / "upload.html"
    await write_file(hass, upload, "<html>nieuw</html>")

    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    with patch_upload(upload):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_TITLE: "Dashboard", CONF_HTML: FILE_ID, CONF_REMOVE_HTML: True},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert await read_file(hass, html_path) == "<html>nieuw</html>"


async def test_options_flow_upload_error(
    hass: HomeAssistant,
    tmp_path: Path,
    setup_entry: MockConfigEntry,
    html_path: Path,
) -> None:
    """Een ongeldig bestand in de opties geeft een fout en laat het oude staan."""
    await write_file(hass, html_path, "<html>oud</html>")
    upload = tmp_path / "upload.html"
    await write_file(hass, upload, b"geen markup")

    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    with patch_upload(upload):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_TITLE: "Dashboard", CONF_HTML: FILE_ID},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "html_invalid"}
    assert await read_file(hass, html_path) == "<html>oud</html>"
