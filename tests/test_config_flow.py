"""Focused tests for Dispatcharr configuration and options flows."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.dispatcharr.api import (
    DispatcharrAuthError,
    DispatcharrConnectionError,
    DispatcharrError,
)
from custom_components.dispatcharr.config_flow import (
    DispatcharrConfigFlow,
    DispatcharrOptionsFlow,
)


class FakeFlow:
    """Minimal ConfigFlow surface for testing the user step."""

    hass = object()
    async_set_unique_id = AsyncMock()
    _abort_if_unique_id_configured = Mock()
    async_create_entry = Mock(side_effect=lambda **kwargs: {"type": "create_entry", **kwargs})
    async_show_form = Mock(side_effect=lambda **kwargs: {"type": "form", **kwargs})


@pytest.fixture
def flow():
    value = FakeFlow()
    value.async_set_unique_id.reset_mock()
    value._abort_if_unique_id_configured.reset_mock()
    value.async_create_entry.reset_mock()
    value.async_show_form.reset_mock()
    return value


@pytest.mark.asyncio
async def test_user_step_normalizes_urls_and_defaults_playback(flow):
    user_input = {
        "url": "https://example.invalid/",
        "api_key": "not-a-real-key",
        "playback_url": "",
        "verify_ssl": True,
    }
    with patch("custom_components.dispatcharr.config_flow._validate", AsyncMock()) as validate:
        result = await DispatcharrConfigFlow.async_step_user(flow, user_input)

    assert result["type"] == "create_entry"
    assert result["data"]["url"] == "https://example.invalid"
    assert result["data"]["playback_url"] == "https://example.invalid"
    flow.async_set_unique_id.assert_awaited_once_with("https://example.invalid")
    validate.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (DispatcharrAuthError("rejected"), "invalid_auth"),
        (DispatcharrConnectionError("offline"), "cannot_connect"),
    ],
)
async def test_user_step_maps_expected_errors(flow, error, expected):
    user_input = {
        "url": "https://example.invalid",
        "api_key": "not-a-real-key",
        "playback_url": "https://media.example.invalid",
        "verify_ssl": True,
    }
    with patch("custom_components.dispatcharr.config_flow._validate", AsyncMock(side_effect=error)):
        result = await DispatcharrConfigFlow.async_step_user(flow, user_input)

    assert result["type"] == "form"
    assert result["errors"] == {"base": expected}


class FakeReauthFlow:
    hass = object()
    _reauth_entry = SimpleNamespace(
        data={
            "url": "https://example.invalid",
            "api_key": "old-key",
            "verify_ssl": True,
        }
    )
    async_show_form = Mock(side_effect=lambda **kwargs: {"type": "form", **kwargs})
    async_update_reload_and_abort = Mock()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [DispatcharrConnectionError("offline"), DispatcharrError("bad response")]
)
async def test_reauth_maps_connection_and_api_errors(error):
    flow = FakeReauthFlow()
    with patch("custom_components.dispatcharr.config_flow._validate", AsyncMock(side_effect=error)):
        result = await DispatcharrConfigFlow.async_step_reauth_confirm(
            flow, {"api_key": "replacement-key"}
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


class FakeOptionsFlow:
    entry = SimpleNamespace(options={})
    async_create_entry = Mock(side_effect=lambda **kwargs: {"type": "create_entry", **kwargs})
    async_show_form = Mock(side_effect=lambda **kwargs: {"type": "form", **kwargs})


@pytest.mark.asyncio
@pytest.mark.parametrize(("raw", "expected"), [("12", 12), ("", None), (None, None)])
async def test_options_convert_output_profile(raw, expected):
    flow = FakeOptionsFlow()
    result = await DispatcharrOptionsFlow.async_step_init(
        flow,
        {
            "scan_interval": 300,
            "output_profile": raw,
            "output_format": "fmp4",
            "proxy_stats": False,
        },
    )
    assert result["data"]["output_profile"] == expected
