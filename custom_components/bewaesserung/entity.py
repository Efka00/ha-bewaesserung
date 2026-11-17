"""Gemeinsame Basis der Entities: Anlagen-Gerät und Zonen-Geräte."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .brain import Anlage, Zone
from .const import DOMAIN


class AnlageEntity(Entity):
    """Entity am Gerät „Bewässerung“."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, anlage: Anlage, key: str, name: str) -> None:
        self.anlage = anlage
        entry_id = anlage.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Bewässerung",
            manufacturer="ha-bewaesserung",
            model="Anlage",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.anlage.async_add_listener(self.async_write_ha_state))


class ZonenEntity(AnlageEntity):
    """Entity am Gerät einer Zone."""

    def __init__(self, anlage: Anlage, zone: Zone, key: str, name: str) -> None:
        super().__init__(anlage, key, name)
        self.zone = zone
        self._attr_unique_id = f"{zone.id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone.id)},
            name=zone.titel,
            manufacturer="ha-bewaesserung",
            model="Zone",
            via_device=(DOMAIN, anlage.entry.entry_id),
        )
