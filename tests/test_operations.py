"""Tests for coordinator aggregation, refresh controls, sensors, and diagnostics."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.dispatcharr.api import DispatcharrAuthError, DispatcharrError
from custom_components.dispatcharr.button import RefreshButton
from custom_components.dispatcharr.coordinator import DispatcharrCoordinator
from custom_components.dispatcharr.diagnostics import async_get_config_entry_diagnostics
from custom_components.dispatcharr.sensor import DESCRIPTIONS, DispatcharrSensor


class FakeClient:
    channels = AsyncMock(return_value=[{"uuid": "channel-one", "name": "Private name"}])
    groups = AsyncMock(return_value=[{"id": 1, "name": "Private group"}])
    profiles = AsyncMock(return_value=[{"id": 2, "name": "Private profile"}])
    output_profiles = AsyncMock(return_value=[{"id": 5, "name": "Private output profile"}])
    m3u_accounts = AsyncMock(return_value=[{"id": 3, "name": "Private source"}])
    epg_sources = AsyncMock(return_value=[{"id": 4, "status": "error"}])
    current_programs = AsyncMock(return_value={"channel-one": {"title": "Private show"}})
    proxy_stats = AsyncMock(return_value={"active_streams": 2})
    refresh_m3u = AsyncMock()
    refresh_epg = AsyncMock()


def coordinator(client=None, *, proxy_stats=True):
    value = object.__new__(DispatcharrCoordinator)
    value.client = client or FakeClient()
    value.entry = SimpleNamespace(
        entry_id="synthetic-entry",
        options={"proxy_stats": proxy_stats},
        data={
            "url": "https://private.example.invalid",
            "playback_url": "https://playback.example.invalid",
            "api_key": "not-a-real-secret",
        },
    )
    return value


@pytest.mark.asyncio
async def test_coordinator_aggregates_catalogue_and_optional_stats():
    value = coordinator()
    data = await value._async_update_data()
    assert set(data) == {
        "channels",
        "groups",
        "profiles",
        "output_profiles",
        "accounts",
        "sources",
        "programs",
        "stats",
    }
    assert data["stats"]["active_streams"] == 2
    value.client.current_programs.assert_awaited_with(["channel-one"])
    value.client.proxy_stats.assert_awaited_once()


@pytest.mark.asyncio
async def test_coordinator_skips_proxy_stats_when_disabled():
    client = FakeClient()
    client.proxy_stats = AsyncMock()
    value = coordinator(client, proxy_stats=False)
    data = await value._async_update_data()
    assert data["stats"] == {}
    client.proxy_stats.assert_not_awaited()


@pytest.mark.asyncio
async def test_coordinator_normalizes_dispatcharr_error():
    client = FakeClient()
    client.channels = AsyncMock(side_effect=DispatcharrError("synthetic failure"))
    with pytest.raises(UpdateFailed, match="synthetic failure"):
        await coordinator(client)._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_starts_reauthentication_for_auth_failure():
    client = FakeClient()
    client.channels = AsyncMock(side_effect=DispatcharrAuthError("rejected"))
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator(client)._async_update_data()


@pytest.mark.asyncio
async def test_refresh_button_routes_and_debounces():
    client = SimpleNamespace(refresh_m3u=AsyncMock(), refresh_epg=AsyncMock())
    value = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-entry"),
        client=client,
        async_request_refresh=AsyncMock(),
        async_add_listener=lambda callback, context=None: lambda: None,
        last_update_success=True,
    )
    button = RefreshButton(value, "epg", 7, "refresh_epg_source", "Synthetic source")
    assert button.name == "Refresh EPG source: Synthetic source"
    with patch("custom_components.dispatcharr.button.time.monotonic", side_effect=[20.0, 25.0]):
        await button.async_press()
        await button.async_press()
    client.refresh_epg.assert_awaited_once_with(7)
    value.async_request_refresh.assert_awaited_once()


def test_sensor_values_are_low_cardinality():
    value = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-entry"),
        data={
            "channels": [{}, {}],
            "sources": [{"status": "ok"}, {"status": "error"}],
            "stats": {"active_streams": 3},
        },
        async_add_listener=lambda callback, context=None: lambda: None,
        last_update_success=True,
    )
    descriptions = {description.key: description for description in DESCRIPTIONS}
    assert DispatcharrSensor(value, descriptions["channels"]).native_value == 2
    assert DispatcharrSensor(value, descriptions["failed_epg_sources"]).native_value == 1
    assert DispatcharrSensor(value, descriptions["active_streams"]).native_value == 3


def test_sensor_reads_live_count_from_combined_stats():
    value = SimpleNamespace(
        entry=SimpleNamespace(entry_id="synthetic-entry"),
        data={
            "channels": [],
            "sources": [],
            "stats": {"live": {"channels": [], "count": 1}},
        },
        async_add_listener=lambda callback, context=None: lambda: None,
        last_update_success=True,
    )
    descriptions = {description.key: description for description in DESCRIPTIONS}
    assert DispatcharrSensor(value, descriptions["active_streams"]).native_value == 1


@pytest.mark.asyncio
async def test_diagnostics_only_return_redacted_aggregates():
    value = coordinator()
    value.data = {
        "channels": [{"name": "Private channel"}],
        "groups": [{"name": "Private group"}],
        "profiles": [{}],
        "accounts": [{"name": "Private account"}],
        "sources": [{"name": "Private source", "status": "failed"}],
    }
    value.last_update_success = True
    entry = value.entry
    hass = SimpleNamespace(data={"dispatcharr": {entry.entry_id: value}})
    result = await async_get_config_entry_diagnostics(hass, entry)
    rendered = repr(result)
    assert result["counts"] == {
        "channels": 1,
        "groups": 1,
        "profiles": 1,
        "m3u_accounts": 1,
        "epg_sources": 1,
        "failed_epg_sources": 1,
    }
    assert "not-a-real-secret" not in rendered
    assert "private.example.invalid" not in rendered
    assert "Private channel" not in rendered
    assert result["entry"]["data"]["api_key"] == "**REDACTED**"
