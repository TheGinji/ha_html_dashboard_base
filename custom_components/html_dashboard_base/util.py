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


def current_text(info: dict[str, Any] | None) -> str:
    """Korte, taalloze beschrijving van het huidige bestand."""
    if info is None:
        return "\u2013"
    size = f"{info['size'] / 1024:.1f} KB"
    return f"{info['title'] or 'HTML'} \u00b7 {size} \u00b7 {info['modified']}"
