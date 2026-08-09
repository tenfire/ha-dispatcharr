"""Dispatcharr data coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DispatcharrAuthError, DispatcharrClient, DispatcharrError
from .const import CONF_PROXY_STATS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN


class DispatcharrCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DispatcharrClient) -> None:
        self.entry = entry
        self.client = client
        seconds = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=seconds),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            channels, groups, profiles, output_profiles, accounts, sources = await asyncio.gather(
                self.client.channels(),
                self.client.groups(),
                self.client.profiles(),
                self.client.output_profiles(),
                self.client.m3u_accounts(),
                self.client.epg_sources(),
            )
            programs = await self.client.current_programs(
                [str(c.get("uuid")) for c in channels if c.get("uuid")]
            )
            stats = (
                await self.client.proxy_stats()
                if self.entry.options.get(CONF_PROXY_STATS, False)
                else {}
            )
            return {
                "channels": channels,
                "groups": groups,
                "profiles": profiles,
                "output_profiles": output_profiles,
                "accounts": accounts,
                "sources": sources,
                "programs": programs,
                "stats": stats,
            }
        except DispatcharrAuthError as err:
            raise ConfigEntryAuthFailed from err
        except DispatcharrError as err:
            raise UpdateFailed(str(err)) from err
