"""Tests for the original Dispatcharr HTTP client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from custom_components.dispatcharr.api import (
    DispatcharrAuthError,
    DispatcharrClient,
    DispatcharrError,
)


@dataclass
class FakeResponse:
    status: int
    payload: Any = None
    body: str = ""

    async def json(self, content_type=None):
        return self.payload

    async def text(self):
        return self.body


class StubClient(DispatcharrClient):
    def __init__(self, responses):
        self.base_url = "https://example.invalid"
        self.api_key = "not-a-real-key"
        self.verify_ssl = True
        self.responses = iter(responses)
        self.paths = []

    async def request(self, method, path, *, json=None):
        self.paths.append((method, path, json))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_stream_url_without_options():
    assert (
        DispatcharrClient.stream_url("https://example.invalid/", "channel-id")
        == "https://example.invalid/proxy/ts/stream/channel-id"
    )


def test_stream_url_encodes_options():
    url = DispatcharrClient.stream_url(
        "https://example.invalid/",
        "channel-id",
        output_profile=12,
        output_format="fmp4",
    )
    assert url == (
        "https://example.invalid/proxy/ts/stream/channel-id?output_profile=12&output_format=fmp4"
    )


@pytest.mark.asyncio
async def test_pagination_follows_next_page():
    client = StubClient(
        [
            {"results": [{"id": 1}], "next": "https://example.invalid/api/items/?page=2"},
            {"results": [{"id": 2}], "next": None},
        ]
    )
    assert await client.paginated("/api/items/") == [{"id": 1}, {"id": 2}]
    assert client.paths[1][1] == "/api/items/?page=2"


@pytest.mark.asyncio
async def test_output_profiles_use_public_api_route():
    client = StubClient([[{"id": 12}]])

    assert await client.output_profiles() == [{"id": 12}]
    assert client.paths == [("GET", "/api/core/outputprofiles/", None)]


@pytest.mark.asyncio
async def test_invalid_paginated_shape_is_rejected():
    client = StubClient(["not-json-object"])
    with pytest.raises(DispatcharrError):
        await client.paginated("/api/items/")


@pytest.mark.asyncio
async def test_auth_errors_are_distinct():
    client = StubClient([])
    with pytest.raises(DispatcharrAuthError):
        await client._check(FakeResponse(401))


@pytest.mark.asyncio
async def test_accepted_empty_response_is_successful():
    client = StubClient([])
    assert await client._check(FakeResponse(202)) is None


@pytest.mark.asyncio
async def test_refresh_payload_and_routes():
    client = StubClient([{}, {}])
    await client.refresh_m3u(5)
    await client.refresh_epg(7, force=True)
    assert client.paths == [
        ("POST", "/api/m3u/refresh/5/", None),
        ("POST", "/api/epg/import/", {"id": 7, "force": True}),
    ]
