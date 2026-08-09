"""Dispatcharr integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DispatcharrClient
from .artwork import DispatcharrArtworkView
from .const import (
    CONF_API_KEY,
    CONF_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
    SERVICE_FORCE_EPG_REFRESH,
)
from .coordinator import DispatcharrCoordinator

_DATA_ARTWORK_VIEW = f"{DOMAIN}_artwork_view"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if _DATA_ARTWORK_VIEW not in hass.data:
        hass.http.register_view(DispatcharrArtworkView(hass))
        hass.data[_DATA_ARTWORK_VIEW] = True
    client = DispatcharrClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_VERIFY_SSL, True),
    )
    coordinator = DispatcharrCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))

    if not hass.services.has_service(DOMAIN, SERVICE_FORCE_EPG_REFRESH):

        async def force_refresh(call: ServiceCall) -> None:
            target = call.data.get("config_entry_id")
            coordinators = hass.data.get(DOMAIN, {}).values()
            for item in coordinators:
                if target is None or item.entry.entry_id == target:
                    await item.client.refresh_epg(call.data.get("source_id"), force=True)

        hass.services.async_register(
            DOMAIN,
            SERVICE_FORCE_EPG_REFRESH,
            force_refresh,
            schema=vol.Schema(
                {vol.Optional("config_entry_id"): str, vol.Optional("source_id"): int}
            ),
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_FORCE_EPG_REFRESH)
            hass.data.pop(DOMAIN)
    return unloaded


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
