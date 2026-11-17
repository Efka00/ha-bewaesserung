"""Bewässerung – Steuerung einer Gartenbewässerung mit mehreren Zonen."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .brain import Anlage

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

type BewaesserungConfigEntry = ConfigEntry[Anlage]


async def async_setup_entry(hass: HomeAssistant,
                            entry: BewaesserungConfigEntry) -> bool:
    """Anlage einrichten."""
    anlage = Anlage(hass, entry)
    await anlage.async_laden()
    entry.runtime_data = anlage
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    anlage.async_start()
    # Optionen geändert oder Zone hinzugefügt/bearbeitet/gelöscht -> neu laden.
    entry.async_on_unload(entry.add_update_listener(_neu_laden))
    return True


async def async_unload_entry(hass: HomeAssistant,
                             entry: BewaesserungConfigEntry) -> bool:
    """Anlage entladen. Laufende Zonen laufen weiter; ihr Zustand ist
    gespeichert und wird nach dem Laden übernommen."""
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _neu_laden(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
