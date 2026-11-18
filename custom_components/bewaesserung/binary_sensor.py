"""Binärsensoren: Bewässerung läuft, Rasen aktiv, Zone läuft, Ventil."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
        async_add_entities([ZoneLaeuft(anlage, zone), VentilOffen(anlage, zone)])


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


class VentilOffen(ZonenEntity, BinarySensorEntity):
    """Was das Ventil selbst meldet – unabhängig von der Freigabe."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "ventil", "Ventil")

    @property
    def icon(self) -> str:
        return "mdi:valve-open" if self.is_on else "mdi:valve-closed"

    @property
    def available(self) -> bool:
        return self.anlage.ventil_offen(self.zone) is not None

    @property
    def is_on(self) -> bool | None:
        return self.anlage.ventil_offen(self.zone)
