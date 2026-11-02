"""Hulpfuncties voor de opgeslagen dashboards."""

from __future__ import annotations

from datetime import datetime
import html
from pathlib import Path
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DATA_DIR

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

_PLACEHOLDER = {
    "nl": (
        "Dit dashboard heeft nog geen HTML-bestand.",
        "Upload je HTML-dashboard zo: ga naar Instellingen, Apparaten en diensten, "
        "Dashboard Base. Tik bij dit dashboard op het tandwiel (Configureren), kies "
        "Upload HTML-dashboard en tik op Verzend.",
        "Nog geen bestand? Een voorbeeld staat in de map templates (starter.html) "
        "op github.com/TheGinji/ha_html_dashboard_base.",
    ),
    "en": (
        "This dashboard has no HTML file yet.",
        "Upload your HTML dashboard like this: go to Settings, Devices & services, "
        "Dashboard Base. Tap the gear icon (Configure) on this dashboard, choose "
        "Upload HTML dashboard and submit.",
        "No file yet? An example is in the templates folder (starter.html) "
        "at github.com/TheGinji/ha_html_dashboard_base.",
    ),
}


def html_file(hass: HomeAssistant, dashboard_id: str) -> Path:
    """Pad van het opgeslagen bestand van een dashboard."""
    return Path(hass.config.path(DATA_DIR, f"{dashboard_id}.html"))


def page_title(text: str) -> str | None:
    """De titel van een pagina, of None als er geen is."""
    match = _TITLE.search(text)
    if match is None:
        return None
    title = " ".join(html.unescape(match.group(1)).split())
    return title[:80] or None


def describe_html(path: Path) -> dict[str, Any] | None:
    """Titel, grootte en datum van een opgeslagen bestand. Blokkerend."""
    if not path.is_file():
        return None
    stat = path.stat()
    try:
        title = page_title(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        title = None
    modified = dt_util.as_local(
        datetime.fromtimestamp(stat.st_mtime, tz=dt_util.UTC)
    ).strftime("%Y-%m-%d %H:%M")
    return {"title": title, "size": stat.st_size, "modified": modified}


def current_text(info: dict[str, Any] | None, name: str | None = None) -> str:
    """Korte, taalloze beschrijving van het huidige bestand: naam, grootte en datum.

    Is de bestandsnaam niet bekend, dan komt de titel van de pagina in de plaats.
    """
    if info is None:
        return "\u2013"
    label = name or info["title"] or "HTML"
    size = f"{info['size'] / 1024:.2f} KB"
    return f"{label} \u00b7 {size} \u00b7 {info['modified']}"


def placeholder_html(title: str, language: str) -> str:
    """De pagina die een dashboard zonder bestand toont: wat er mist en waar je uploadt."""
    heading, steps, hint = _PLACEHOLDER["nl" if language.startswith("nl") else "en"]
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<style>body{margin:0;padding:2rem;font:16px/1.5 system-ui,sans-serif;"
        "color:#1d201c;background:#f4f4f1}"
        "@media (prefers-color-scheme:dark){body{color:#ecece6;background:#141613}}"
        "h1{margin:0 0 1rem;font-size:1.3rem}p{max-width:36rem}</style></head><body>"
        f"<h1>{html.escape(title)}</h1><p>{heading}</p><p>{steps}</p><p>{hint}</p>"
        "</body></html>"
    )
