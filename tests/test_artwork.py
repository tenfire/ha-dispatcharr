"""Tests for normalized channel artwork."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from PIL import Image

from custom_components.dispatcharr.artwork import DispatcharrArtworkView, _normalize_logo
from custom_components.dispatcharr.const import DOMAIN

ENTRY_ID = "entry-one"


def png(size, color=(255, 255, 255, 255)) -> bytes:
    image = Image.new("RGBA", size, color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_normalize_logo_preserves_aspect_ratio_and_adds_transparent_padding():
    result = Image.open(BytesIO(_normalize_logo(png((100, 20)))))

    assert result.size == (256, 256)
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 0
    bbox = result.getchannel("A").getbbox()
    assert bbox is not None
    assert bbox[2] - bbox[0] == 192
    assert bbox[3] - bbox[1] in (38, 39)


def test_normalize_logo_rejects_invalid_content():
    with pytest.raises(ValueError, match="Invalid channel logo"):
        _normalize_logo(b"not an image")


@pytest.mark.asyncio
async def test_artwork_view_authorizes_catalogue_id_and_caches_result():
    client = SimpleNamespace(bytes=AsyncMock(return_value=png((20, 100))))
    coordinator = SimpleNamespace(
        client=client,
        data={"channels": [{"effective_logo_id": 17}]},
    )
    hass = SimpleNamespace(
        data={DOMAIN: {ENTRY_ID: coordinator}},
        async_add_executor_job=AsyncMock(side_effect=lambda func, value: func(value)),
    )
    view = DispatcharrArtworkView(hass)

    first = await view.get(SimpleNamespace(), ENTRY_ID, "17")
    second = await view.get(SimpleNamespace(), ENTRY_ID, "17")

    assert first.content_type == "image/png"
    assert first.headers["Cache-Control"] == "private, max-age=86400"
    assert Image.open(BytesIO(first.body)).size == (256, 256)
    assert second.body == first.body
    client.bytes.assert_awaited_once()


@pytest.mark.asyncio
async def test_artwork_view_rejects_unknown_logo_id():
    coordinator = SimpleNamespace(
        client=SimpleNamespace(bytes=AsyncMock()),
        data={"channels": [{"effective_logo_id": 17}]},
    )
    hass = SimpleNamespace(data={DOMAIN: {ENTRY_ID: coordinator}})
    view = DispatcharrArtworkView(hass)

    with pytest.raises(web.HTTPNotFound):
        await view.get(SimpleNamespace(), ENTRY_ID, "18")
