"""Sensoren: Status der Anlage; Status, Grund, Zeiten und Läufe je Zone."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
    async_add_entities([AnlageStatus(anlage)])
    for zone in anlage.zonen.values():
        async_add_entities([
            ZoneStatus(anlage, zone),
            ZoneGrund(anlage, zone),
            LetzteBewaesserung(anlage, zone),
            Ende(anlage, zone),
            LaeufeHeute(anlage, zone),
        ])


class AnlageStatus(AnlageEntity, SensorEntity):
    _attr_icon = "mdi:brain"

    def __init__(self, anlage: Anlage) -> None:
        super().__init__(anlage, "status", "Status")

    @property
    def native_value(self) -> str:
        return self.anlage.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "aktive_zonen": self.anlage.aktive,
            "laeufe_heute": self.anlage.laeufe_heute,
            "rasen_aktiv": self.anlage.rasen_aktiv,
            "nachholen": len(self.anlage.nachholen),
            "sperre": self.anlage.sperre,
        }


class ZoneStatus(ZonenEntity, SensorEntity):
    _attr_icon = "mdi:list-status"

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "status", "Status")

    @property
    def native_value(self) -> str:
        return self.zone.zustand

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"grund": self.zone.grund,
                "sensorfehler": self.zone.sensorfehler}


class ZoneGrund(ZonenEntity, SensorEntity):
    _attr_icon = "mdi:information-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "grund", "Grund")

    @property
    def native_value(self) -> str:
        return self.zone.grund


class LetzteBewaesserung(ZonenEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:history"

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "letzte_bewaesserung",
                         "Letzte Bewässerung")

    @property
    def native_value(self) -> datetime | None:
        return self.zone.letzte


class Ende(ZonenEntity, SensorEntity):
    """Geplantes Laufzeitende – leer, wenn die Zone nicht läuft."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-sand"

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "ende", "Ende")

    @property
    def native_value(self) -> datetime | None:
        return self.zone.ende


class LaeufeHeute(ZonenEntity, SensorEntity):
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "laeufe_heute", "Läufe heute")

    @property
    def native_value(self) -> int:
        return int(self.zone.s["laeufe"])
