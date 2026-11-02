"""Hulpfuncties en vaste waarden voor de tests."""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant

ALLOWED = ["light.keuken", "switch.tuin", "sensor.buiten", "scene.weg"]
SECOND_ALLOWED = ["light.tuinhuis", "sensor.techniek"]


async def write_file(hass: HomeAssistant, path: Path, data: bytes | str) -> None:
    """Schrijf een bestand zonder de event loop te blokkeren."""
    raw = data if isinstance(data, bytes) else data.encode("utf-8")

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    await hass.async_add_executor_job(_write)


async def read_file(hass: HomeAssistant, path: Path) -> str:
    """Lees een tekstbestand zonder de event loop te blokkeren."""
    return await hass.async_add_executor_job(path.read_text, "utf-8")


async def file_exists(hass: HomeAssistant, path: Path) -> bool:
    """Bestaat het bestand?"""
    return await hass.async_add_executor_job(path.is_file)


async def list_files(hass: HomeAssistant, folder: Path) -> list[str]:
    """De bestanden in een map, gesorteerd. Een ontbrekende map is leeg."""

    def _list() -> list[str]:
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    return await hass.async_add_executor_job(_list)
