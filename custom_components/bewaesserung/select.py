"""Auswahl je Zone: Modus (Aus / Zeit / Feuchtigkeit)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .brain import Anlage, Zone
from .const import MODUS_AUS, MODUS_FEUCHTE, MODUS_ZEIT
from .entity import ZonenEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    for zone in anlage.zonen.values():
        async_add_entities([Modus(anlage, zone)])


class Modus(ZonenEntity, SelectEntity):
    """Ohne Feuchtesensor gibt es nur Aus und Zeit."""

    _attr_icon = "mdi:cog-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "modus", "Modus")
        self._attr_options = (
            [MODUS_AUS, MODUS_ZEIT, MODUS_FEUCHTE] if zone.sensor
            else [MODUS_AUS, MODUS_ZEIT]
        )

    @property
    def current_option(self) -> str:
        return self.zone.modus

    async def async_select_option(self, option: str) -> None:
        await self.anlage.async_setze_wert(self.zone, "modus", option)
