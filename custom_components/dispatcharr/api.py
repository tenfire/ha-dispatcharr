"""Async client for the public Dispatcharr HTTP API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout


class DispatcharrError(Exception):
    """Base API error."""


class DispatcharrAuthError(DispatcharrError):
    """Authentication or authorization failed."""


class DispatcharrConnectionError(DispatcharrError):
    """Dispatcharr could not be reached."""


@dataclass(slots=True)
class DispatcharrClient:
    """Small, original HTTP client; no Dispatcharr source code is embedded."""

    session: ClientSession
    base_url: str
    api_key: str
    verify_ssl: bool = True

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    async def _check(self, response: ClientResponse) -> Any:
        if response.status in (401, 403):
            raise DispatcharrAuthError(f"Dispatcharr rejected the request ({response.status})")
        if response.status >= 400:
            text = (await response.text())[:200]
            raise DispatcharrError(f"Dispatcharr returned {response.status}: {text}")
        if response.status in (202, 204):
            return None
        return await response.json(content_type=None)

    async def request(self, method: str, path: str, *, json: Any = None) -> Any:
        try:
            async with self.session.request(
                method,
                f"{self.base_url}{path}",
                headers={"X-API-Key": self.api_key, "Accept": "application/json"},
                json=json,
                ssl=self.verify_ssl,
                timeout=ClientTimeout(total=30),
            ) as response:
                return await self._check(response)
        except DispatcharrError:
            raise
        except (ClientError, TimeoutError) as err:
            raise DispatcharrConnectionError(str(err)) from err

    async def paginated(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_path: str | None = path
        while next_path:
            data = await self.request("GET", next_path)
            if isinstance(data, list):
                items.extend(data)
                break
            if not isinstance(data, dict):
                raise DispatcharrError("Unexpected paginated response")
            rows = data.get("results", data.get("data", []))
            if isinstance(rows, list):
                items.extend(row for row in rows if isinstance(row, dict))
            next_url = data.get("next")
            if not next_url:
                break
            next_path = next_url.removeprefix(self.base_url)
        return items

    async def validate(self) -> None:
        await self.paginated("/api/channels/channels/?page_size=1")

    async def channels(self) -> list[dict[str, Any]]:
        return await self.paginated("/api/channels/channels/")

    async def groups(self) -> list[dict[str, Any]]:
        return await self.paginated("/api/channels/groups/")

    async def profiles(self) -> list[dict[str, Any]]:
        return await self.paginated("/api/channels/profiles/")

    async def output_profiles(self) -> list[dict[str, Any]]:
        """Return Dispatcharr stream output profiles."""
        return await self.paginated("/api/core/outputprofiles/")

    async def m3u_accounts(self) -> list[dict[str, Any]]:
        return await self.paginated("/api/m3u/accounts/")

    async def epg_sources(self) -> list[dict[str, Any]]:
        return await self.paginated("/api/epg/sources/")

    async def current_programs(self, uuids: list[str]) -> dict[str, Any]:
        if not uuids:
            return {}
        data = await self.request(
            "POST", "/api/epg/current-programs/", json={"channel_uuids": uuids}
        )
        return data if isinstance(data, dict) else {}

    async def proxy_stats(self) -> dict[str, Any]:
        data = await self.request("GET", "/proxy/stats/")
        return data if isinstance(data, dict) else {}

    async def refresh_m3u(self, account_id: int | None = None) -> None:
        path = f"/api/m3u/refresh/{account_id}/" if account_id is not None else "/api/m3u/refresh/"
        await self.request("POST", path)

    async def refresh_epg(self, source_id: int | None = None, *, force: bool = False) -> None:
        await self.request("POST", "/api/epg/import/", json={"id": source_id, "force": force})

    @staticmethod
    def stream_url(
        base_url: str,
        channel_uuid: str,
        *,
        output_profile: int | None = None,
        output_format: str = "",
    ) -> str:
        query: dict[str, str | int] = {}
        if output_profile is not None:
            query["output_profile"] = output_profile
        if output_format:
            query["output_format"] = output_format
        suffix = f"?{urlencode(query)}" if query else ""
        return f"{base_url.rstrip('/')}/proxy/ts/stream/{channel_uuid}{suffix}"
