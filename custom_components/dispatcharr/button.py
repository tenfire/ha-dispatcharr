"""Dispatcharr refresh buttons."""

import time

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RefreshButton(c, "m3u", None, "refresh_m3u"),
        RefreshButton(c, "epg", None, "refresh_epg"),
    ]
    entities += [
        RefreshButton(c, "m3u", x.get("id"), "refresh_m3u_account", x.get("name"))
        for x in c.data.get("accounts", [])
        if x.get("id") is not None
    ]
    entities += [
        RefreshButton(c, "epg", x.get("id"), "refresh_epg_source", x.get("name"))
        for x in c.data.get("sources", [])
        if x.get("id") is not None and str(x.get("source_type", "")).lower() != "dummy"
    ]
    add_entities(entities)


class RefreshButton(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, c, kind, item_id, key, label=None):
        super().__init__(c)
        self.kind = kind
        self.item_id = item_id
        self._last = 0.0
        self.entity_description = ButtonEntityDescription(key=key, translation_key=key)
        self._attr_name = label
        self._attr_unique_id = f"{c.entry.entry_id}_{kind}_{item_id or 'all'}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, c.entry.entry_id)},
            "name": "Dispatcharr",
            "manufacturer": "Dispatcharr",
        }

    async def async_press(self):
        now = time.monotonic()
        if now - self._last < 10:
            return
        self._last = now
        if self.kind == "m3u":
            await self.coordinator.client.refresh_m3u(self.item_id)
        else:
            await self.coordinator.client.refresh_epg(self.item_id)
        await self.coordinator.async_request_refresh()
