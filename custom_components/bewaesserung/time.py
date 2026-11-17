"""Uhrzeit je Zone: Startzeit der Zeitsteuerung."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .brain import Anlage, Zone
from .entity import ZonenEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    for zone in anlage.zonen.values():
        async_add_entities([Startzeit(anlage, zone)])


class Startzeit(ZonenEntity, TimeEntity):
    _attr_icon = "mdi:clock-start"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "startzeit", "Startzeit")

    @property
    def native_value(self) -> time | None:
        try:
            return time.fromisoformat(str(self.zone.s["startzeit"]))
        except ValueError:
            return None

    async def async_set_value(self, value: time) -> None:
        await self.anlage.async_setze_wert(
            self.zone, "startzeit", value.strftime("%H:%M:%S"))
