"""Tests voor de hulpfuncties."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from homeassistant.core import HomeAssistant

from custom_components.html_dashboard_base.util import (
    current_text,
    describe_html,
    html_file,
    page_title,
    placeholder_html,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<html><title>Mijn paneel</title></html>", "Mijn paneel"),
        ("<TITLE lang=nl>  Twee\n regels </TITLE>", "Twee regels"),
        ("<title>Koffie &amp; thee</title>", "Koffie & thee"),
        ("<html></html>", None),
        ("<title>   </title>", None),
        ("<title>" + "x" * 200 + "</title>", "x" * 80),
    ],
    ids=["gewoon", "hoofdletters_en_regels", "entiteit", "geen_titel", "leeg", "te_lang"],
)
def test_page_title(text: str, expected: str | None) -> None:
    assert page_title(text) == expected


def test_describe_html(tmp_path: Path) -> None:
    path = tmp_path / "a.html"
    path.write_text("<title>Mijn paneel</title>", encoding="utf-8")

    info = describe_html(path)

    assert info is not None
    assert info["title"] == "Mijn paneel"
    assert info["size"] == path.stat().st_size
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", info["modified"])


def test_describe_html_missing(tmp_path: Path) -> None:
    assert describe_html(tmp_path / "bestaat-niet.html") is None


def test_describe_html_not_utf8(tmp_path: Path) -> None:
    path = tmp_path / "a.html"
    path.write_bytes(b"\xff\xfe\xfd")

    info = describe_html(path)

    assert info is not None
    assert info["title"] is None


def test_current_text() -> None:
    info = {"title": "Mijn paneel", "size": 2048, "modified": "2026-11-02 21:03"}
    assert current_text(info) == "Mijn paneel \u00b7 2.00 KB \u00b7 2026-11-02 21:03"
    assert (
        current_text(info, "starter.html")
        == "starter.html \u00b7 2.00 KB \u00b7 2026-11-02 21:03"
    )
    assert current_text({**info, "title": None}).startswith("HTML \u00b7 ")
    assert current_text(None) == "\u2013"
    assert current_text(None, "starter.html") == "\u2013"


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("nl", "nog geen HTML-bestand"),
        ("nl-NL", "nog geen HTML-bestand"),
        ("en", "no HTML file yet"),
        ("de", "no HTML file yet"),
    ],
)
def test_placeholder_language(language: str, expected: str) -> None:
    assert expected in placeholder_html("Thuis", language)


def test_placeholder_escapes_the_title() -> None:
    page = placeholder_html("Mijn <paneel>", "nl")

    assert "Mijn &lt;paneel&gt;" in page
    assert "<paneel>" not in page


def test_placeholder_explains_where_to_upload() -> None:
    page = placeholder_html("Thuis", "nl")

    assert "<h1>Thuis</h1>" in page
    assert "Upload HTML-dashboard" in page
    assert "tandwiel" in page
    assert "starter.html" in page


async def test_html_file(hass: HomeAssistant) -> None:
    path = html_file(hass, "abc")

    assert path.name == "abc.html"
    assert path.parent.name == "html_dashboard_base"
