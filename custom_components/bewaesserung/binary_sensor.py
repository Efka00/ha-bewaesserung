"""Binärsensoren: Bewässerung läuft, Rasen aktiv, Zone läuft."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .brain import Anlage, Zone
from .entity import AnlageEntity, ZonenEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    async_add_entities([AnlageLaeuft(anlage), RasenAktiv(anlage)])
    for zone in anlage.zonen.values():
        async_add_entities([ZoneLaeuft(anlage, zone)])


class AnlageLaeuft(AnlageEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, anlage: Anlage) -> None:
        super().__init__(anlage, "laeuft", "Läuft")

    @property
    def is_on(self) -> bool:
        return any(z.freigabe for z in self.anlage.zonen.values())


class RasenAktiv(AnlageEntity, BinarySensorEntity):
    _attr_icon = "mdi:grass"

    def __init__(self, anlage: Anlage) -> None:
        super().__init__(anlage, "rasen_aktiv", "Rasen aktiv")

    @property
    def is_on(self) -> bool:
        return self.anlage.rasen_aktiv


class ZoneLaeuft(ZonenEntity, BinarySensorEntity):
    """Freigabe des Brain: die Zone darf und soll laufen."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "laeuft", "Läuft")

    @property
    def is_on(self) -> bool:
        return self.zone.freigabe
