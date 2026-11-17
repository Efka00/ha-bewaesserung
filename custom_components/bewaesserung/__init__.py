"""Bewässerung – Steuerung einer Gartenbewässerung mit mehreren Zonen."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .brain import Anlage
from .const import CONF_ZONEN, DOMAIN, SUBENTRY_ZONE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

type BewaesserungConfigEntry = ConfigEntry[Anlage]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Version 1 -> 2: Zonen von Subentries in die Optionen umziehen.

    Die Subentry-ID bleibt die Zonen-ID. Damit bleiben unique_ids,
    Entity-IDs, Verlauf und der gespeicherte Zustand erhalten. Geräte und
    Entities werden vorher auf die Anlage umgehängt – sonst würde HA sie
    beim Entfernen der Subentries löschen.
    """
    if entry.version > 2:
        return False
    if entry.version == 1:
        dev_reg = dr.async_get(hass)
        ent_reg = er.async_get(hass)
        zonen = dict(entry.options.get(CONF_ZONEN, {}))
        sub_ids = []
        for sid, sub in entry.subentries.items():
            if sub.subentry_type != SUBENTRY_ZONE:
                continue
            zonen[sid] = dict(sub.data)
            sub_ids.append(sid)
            for geraet in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
                if geraet.config_subentry_id == sid:
                    dev_reg.async_update_device(geraet.id,
                                                new_config_subentry_id=None)
            for eintrag in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
                if eintrag.config_subentry_id == sid:
                    ent_reg.async_update_entity(eintrag.entity_id,
                                                config_subentry_id=None)
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_ZONEN: zonen}, version=2)
        for sid in sub_ids:
            hass.config_entries.async_remove_subentry(entry, sid)
        _LOGGER.info("%d Zonen von Subentries in die Optionen übernommen",
                     len(sub_ids))
    return True


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
