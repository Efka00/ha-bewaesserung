"""Schalter: Automatik (Anlage) und Handstart (je Zone)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .brain import Anlage, Zone
from .entity import AnlageEntity, ZonenEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback
                            ) -> None:
    anlage: Anlage = entry.runtime_data
    async_add_entities([AutomatikSchalter(anlage)])
    for zone in anlage.zonen.values():
        async_add_entities([HandstartSchalter(anlage, zone)],
                           config_subentry_id=zone.id)


class AutomatikSchalter(AnlageEntity, SwitchEntity):
    """Automatik an/aus – zugleich die Saisonabschaltung (früher Master)."""

    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, anlage: Anlage) -> None:
        super().__init__(anlage, "automatik", "Automatik")

    @property
    def is_on(self) -> bool:
        return self.anlage.master

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.anlage.async_setze_master(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.anlage.async_setze_master(False)


class HandstartSchalter(ZonenEntity, SwitchEntity):
    """Handstart: an = Startwunsch, aus = Stoppwunsch.

    Spiegelt den Laufzustand – das Brain schaltet ihn beim Start an und
    am Ende wieder aus.
    """

    _attr_icon = "mdi:sprinkler"

    def __init__(self, anlage: Anlage, zone: Zone) -> None:
        super().__init__(anlage, zone, "handstart", "Handstart")

    @property
    def is_on(self) -> bool:
        return self.zone.handstart

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.anlage.async_setze_handstart(self.zone, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.anlage.async_setze_handstart(self.zone, False)
