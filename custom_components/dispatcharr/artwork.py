"""Normalized channel artwork for Home Assistant's cover-style media grid."""

from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from PIL import Image, UnidentifiedImageError

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_MAX_SOURCE_BYTES = 2 * 1024 * 1024
_CANVAS_SIZE = 256
_LOGO_SIZE = 192
_CACHE_SIZE = 128


def _normalize_logo(source: bytes) -> bytes:
    """Fit source artwork into a padded square transparent PNG."""
    try:
        with Image.open(BytesIO(source)) as image:
            image.load()
            scale = min(_LOGO_SIZE / image.width, _LOGO_SIZE / image.height)
            size = (
                max(1, round(image.width * scale)),
                max(1, round(image.height * scale)),
            )
            image = image.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (_CANVAS_SIZE, _CANVAS_SIZE), (0, 0, 0, 0))
            canvas.alpha_composite(
                image,
                ((_CANVAS_SIZE - image.width) // 2, (_CANVAS_SIZE - image.height) // 2),
            )
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as err:
        raise ValueError("Invalid channel logo") from err

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


class DispatcharrArtworkView(HomeAssistantView):
    """Serve bounded, normalized Dispatcharr channel logos."""

    url = "/api/dispatcharr/{entry_id}/artwork/{logo_id}"
    name = "api:dispatcharr:artwork"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()

    async def get(self, request: web.Request, entry_id: str, logo_id: str) -> web.Response:
        """Return a square padded PNG for a catalogue logo."""
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is None:
            raise web.HTTPNotFound

        valid_logo_ids = {
            str(channel.get("effective_logo_id") or channel.get("logo_id"))
            for channel in coordinator.data.get("channels", [])
            if channel.get("effective_logo_id") is not None or channel.get("logo_id") is not None
        }
        if logo_id not in valid_logo_ids:
            raise web.HTTPNotFound

        key = (entry_id, logo_id)
        if normalized := self._cache.get(key):
            self._cache.move_to_end(key)
        else:
            source = await coordinator.client.bytes(
                f"/api/channels/logos/{logo_id}/cache/",
                max_bytes=_MAX_SOURCE_BYTES,
            )
            normalized = await self.hass.async_add_executor_job(_normalize_logo, source)
            self._cache[key] = normalized
            while len(self._cache) > _CACHE_SIZE:
                self._cache.popitem(last=False)

        return web.Response(
            body=normalized,
            content_type="image/png",
            headers={"Cache-Control": "private, max-age=86400"},
        )
