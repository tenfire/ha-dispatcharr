"""Exercise the integration through Home Assistant's config-entry lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.http import HomeAssistantHTTP
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dispatcharr.const import DOMAIN, SERVICE_FORCE_EPG_REFRESH


@pytest.mark.asyncio
async def test_setup_service_and_unload(hass: HomeAssistant, enable_custom_integrations):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Example server",
        unique_id="https://example.invalid",
        data={
            "url": "https://example.invalid",
            "api_key": "not-a-real-key",
            "playback_url": "https://media.example.invalid",
            "verify_ssl": True,
        },
        options={"proxy_stats": False},
    )
    entry.add_to_hass(hass)

    catalogue = {
        "channels": [],
        "groups": [],
        "profiles": [],
        "accounts": [],
        "sources": [],
        "programs": {},
        "stats": {},
    }
    hass.data.pop(f"{DOMAIN}_artwork_view", None)
    register_view = Mock()
    with (
        patch.object(HomeAssistantHTTP, "register_view", register_view),
        patch(
            "custom_components.dispatcharr.coordinator.DispatcharrCoordinator._async_update_data",
            AsyncMock(return_value=catalogue),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(),
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            AsyncMock(return_value=True),
        ) as unload,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.entry_id in hass.data[DOMAIN]
        assert hass.services.has_service(DOMAIN, SERVICE_FORCE_EPG_REFRESH)
        forward.assert_awaited_once()
        register_view.assert_called_once()

        refresh_epg = AsyncMock()
        with patch(
            "custom_components.dispatcharr.api.DispatcharrClient.refresh_epg",
            refresh_epg,
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_FORCE_EPG_REFRESH,
                {"config_entry_id": entry.entry_id, "source_id": 7},
                blocking=True,
            )
        refresh_epg.assert_awaited_once_with(7, force=True)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        unload.assert_awaited_once()

    assert DOMAIN not in hass.data
    assert not hass.services.has_service(DOMAIN, SERVICE_FORCE_EPG_REFRESH)
