"""Bewässerung – Steuerung einer Gartenbewässerung mit mehreren Zonen."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .brain import Anlage
from .const import DOMAIN

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
    # Anlagen-Gerät vorab anlegen: die Zonen-Geräte verweisen per
    # via_device_id darauf.
    dev_reg = dr.async_get(hass)
    geraet = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Bewässerung",
        manufacturer="ha-bewaesserung",
        model="Anlage",
    )
    anlage.geraet_id = geraet.id
    # Geräte gelöschter Zonen entfernen (ihre Entities gehen mit).
    gueltig = {entry.entry_id, *anlage.zonen}
    for alt in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        kennungen = {k for d, k in alt.identifiers if d == DOMAIN}
        if kennungen and not kennungen & gueltig:
            dev_reg.async_remove_device(alt.id)
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
