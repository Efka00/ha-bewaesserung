"""Bewässerung – Steuerung einer Gartenbewässerung mit mehreren Zonen."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # noqa: F401

# Plattformen kommen mit dem Brain-Port dazu.
PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Anlage einrichten."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Optionen geändert oder Zone hinzugefügt/bearbeitet/gelöscht -> neu laden.
    entry.async_on_unload(entry.add_update_listener(_neu_laden))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Anlage entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _neu_laden(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
