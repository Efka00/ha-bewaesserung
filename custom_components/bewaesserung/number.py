"""Zahlen je Zone: Laufzeit und Sollwert (nur mit Feuchtesensor)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .brain import Anlage, Zone
from .entity import ZonenEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    for zone in anlage.zonen.values():
        entities: list[NumberEntity] = [Laufzeit(anlage, zone)]
        if zone.sensor:
            entities.append(Sollwert(anlage, zone))
        async_add_entities(entities)


class _ZonenZahl(ZonenEntity, NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _key: str

    @property
    def native_value(self) -> float:
        return float(self.zone.s[self._key])

    async def async_set_native_value(self, value: float) -> None:
        await self.anlage.async_setze_wert(self.zone, self._key, float(value))


class Laufzeit(_ZonenZahl):
    _key = "laufzeit"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 1
    _attr_native_max_value = 180
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "laufzeit", "Laufzeit")


class Sollwert(_ZonenZahl):
    _key = "sollwert"
    _attr_icon = "mdi:water-percent"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "sollwert", "Sollwert")
