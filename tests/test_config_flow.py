"""Tests voor de config flow en de opties."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.html_dashboard_base.const import (
    CONF_ENTITIES,
    CONF_HTML,
    CONF_TITLE,
    DOMAIN,
)

from .helpers import file_exists, read_file, write_file

FILE_ID = "11111111-1111-1111-1111-111111111111"
UPLOAD_TARGET = (
    "custom_components.html_dashboard_base.config_flow.process_uploaded_file"
)
MAX_TARGET = "custom_components.html_dashboard_base.config_flow.MAX_HTML_BYTES"


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
    html_path: Path,
) -> None:
    """Een instelling zonder bestand: de entry wordt aangemaakt."""
    flow_id = await start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_TITLE: "Thuis", CONF_ENTITIES: ["light.keuken"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Thuis"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_TITLE: "Thuis",
        CONF_ENTITIES: ["light.keuken"],
    }
    assert not await file_exists(hass, html_path)


async def test_user_flow_with_upload(
    hass: HomeAssistant,
    tmp_path: Path,
    skip_dependencies: None,
    panel_mocks: tuple[AsyncMock, MagicMock],
    html_path: Path,
) -> None:
    """Een geuploade pagina wordt opgeslagen."""
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
    assert await read_file(hass, html_path) == "<html><body>hoi</body></html>"


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
    html_path: Path,
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
    assert not await file_exists(hass, html_path)


async def test_single_instance(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Een tweede instelling kan niet."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_updates(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Titel en entiteiten zijn aan te passen."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

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
