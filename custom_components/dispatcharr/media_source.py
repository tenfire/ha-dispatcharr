"""Dispatcharr media source."""

from __future__ import annotations

import json
import math
from urllib.parse import quote

from homeassistant.components.media_player.browse_media import SearchMedia, SearchMediaQuery
from homeassistant.components.media_player.const import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant

from .api import DispatcharrClient
from .const import CONF_OUTPUT_FORMAT, CONF_OUTPUT_PROFILE, CONF_PLAYBACK_URL, DOMAIN


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    return DispatcharrMediaSource(hass)


class DispatcharrMediaSource(MediaSource):
    """Browse and resolve channels from one or more Dispatcharr entries."""

    name = "Dispatcharr"

    def __init__(self, hass):
        super().__init__(DOMAIN)
        self.hass = hass

    def _coordinators(self):
        return [
            self.hass.data[DOMAIN][entry.entry_id]
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.entry_id in self.hass.data.get(DOMAIN, {})
        ]

    def _parse(self, identifier: str | None):
        ident = identifier or ""
        if not ident:
            return None, ""
        parts = ident.split("/", 2)
        if len(parts) < 2 or parts[0] != "entry":
            raise ValueError("Invalid Dispatcharr media identifier")
        coordinators = {value.entry.entry_id: value for value in self._coordinators()}
        coordinator = coordinators.get(parts[1])
        if coordinator is None:
            raise ValueError("Unknown Dispatcharr config entry")
        return coordinator, parts[2] if len(parts) == 3 else ""

    @staticmethod
    def _prefix(coordinator, identifier=""):
        root = f"entry/{coordinator.entry.entry_id}"
        return f"{root}/{identifier}" if identifier else root

    @staticmethod
    def _channel_id(channel):
        return str(channel.get("uuid") or "")

    @staticmethod
    def _name(row):
        return str(row.get("name") or row.get("channel_name") or "Channel")

    @classmethod
    def _name_key(cls, row):
        return cls._name(row).casefold()

    @classmethod
    def _channel_key(cls, channel):
        """Sort by effective Dispatcharr channel number, then stable text fields."""
        raw_number = channel.get("effective_channel_number")
        if raw_number is None:
            raw_number = channel.get("channel_number")
        try:
            number = float(raw_number)
            if not math.isfinite(number):
                raise ValueError
        except TypeError, ValueError:
            number = math.inf
        return number, cls._name_key(channel), cls._channel_id(channel)

    @staticmethod
    def _logo_url(coordinator, channel):
        logo_id = channel.get("effective_logo_id") or channel.get("logo_id")
        if logo_id is None:
            return None
        return (
            f"/api/dispatcharr/{quote(coordinator.entry.entry_id, safe='')}/artwork/"
            f"{quote(str(logo_id), safe='')}"
        )

    @staticmethod
    def _automatic_output_profile(coordinator):
        """Choose only an unambiguous active AAC profile."""
        matches = []
        for profile in coordinator.data.get("output_profiles", []):
            if not profile.get("is_active", True) or profile.get("id") is None:
                continue
            details = json.dumps(
                {
                    "command": profile.get("command"),
                    "parameters": profile.get("parameters"),
                }
            ).casefold()
            if "aac" in details:
                matches.append(profile["id"])
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def _output_settings(cls, coordinator):
        options = coordinator.entry.options
        output_format = options.get(CONF_OUTPUT_FORMAT)
        output_profile = options.get(CONF_OUTPUT_PROFILE)
        if not output_format and output_profile is None:
            automatic_profile = cls._automatic_output_profile(coordinator)
            if automatic_profile is not None:
                return "fmp4", automatic_profile
        return output_format or "", output_profile

    @staticmethod
    def _program_title(programs, channel_uuid):
        program = programs.get(channel_uuid) if isinstance(programs, dict) else None
        if isinstance(program, list):
            program = program[0] if program else None
        if not isinstance(program, dict):
            return None
        nested = program.get("program") or program.get("current_program")
        if isinstance(nested, dict):
            program = nested
        title = program.get("title") or program.get("name")
        return str(title) if title else None

    def _leaf(self, coordinator, channel):
        uuid = self._channel_id(channel)
        logo = self._logo_url(coordinator, channel)
        channel_name = self._name(channel)
        program_title = self._program_title(coordinator.data.get("programs", {}), uuid)
        title = f"{channel_name} — {program_title}" if program_title else channel_name
        output_format, _ = self._output_settings(coordinator)
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=self._prefix(coordinator, f"channel/{uuid}"),
            media_class=MediaClass.VIDEO,
            # The frontend target picker matches MIME patterns such as
            # ``video/*``; the generic ``video`` category is filtered out.
            media_content_type="video/mp4" if output_format == "fmp4" else "video/mp2t",
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=logo if isinstance(logo, str) else None,
        )

    @staticmethod
    def _folder(coordinator, identifier, title):
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=DispatcharrMediaSource._prefix(coordinator, identifier),
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=title,
            can_play=False,
            can_expand=True,
        )

    @staticmethod
    def _linked(channel, kind, raw_id):
        """Return whether a channel belongs to a group or output profile."""
        candidates = {raw_id, int(raw_id) if str(raw_id).isdigit() else raw_id}
        values = channel.get("groups" if kind == "group" else "profiles", [])
        direct = channel.get("channel_group_id" if kind == "group" else "profile_id")
        return direct in candidates or any(
            (value.get("id") if isinstance(value, dict) else value) in candidates
            for value in values
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        coordinator, ident = self._parse(item.identifier)
        if coordinator is None:
            children = [
                self._folder(value, "", value.entry.title or "Dispatcharr")
                for value in self._coordinators()
            ]
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier="",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.VIDEO,
                title="Dispatcharr",
                can_play=False,
                can_expand=True,
                children=children,
            )

        data = coordinator.data
        if not ident:
            children = [
                self._folder(coordinator, "all", "All channels"),
                self._folder(coordinator, "groups", "Groups"),
                self._folder(coordinator, "profiles", "Profiles"),
            ]
            title = coordinator.entry.title or "Dispatcharr"
        elif ident == "all":
            children = [
                self._leaf(coordinator, channel)
                for channel in sorted(data["channels"], key=self._channel_key)
            ]
            title = "All channels"
        elif ident in ("groups", "profiles"):
            singular = ident.removesuffix("s")
            children = [
                self._folder(coordinator, f"{singular}/{row['id']}", self._name(row))
                for row in sorted(data[ident], key=self._name_key)
                if row.get("id") is not None
                and any(self._linked(channel, singular, row["id"]) for channel in data["channels"])
            ]
            title = ident.title()
        elif ident.startswith(("group/", "profile/")):
            kind, raw_id = ident.split("/", 1)
            if not raw_id:
                raise ValueError("Invalid Dispatcharr media identifier")
            children = [
                self._leaf(coordinator, channel)
                for channel in sorted(data["channels"], key=self._channel_key)
                if self._linked(channel, kind, raw_id)
            ]
            title = kind.title()
        elif ident.startswith(("channel/", "programme/")):
            kind, uuid = ident.split("/", 1)
            channel = next(
                (value for value in data["channels"] if self._channel_id(value) == uuid),
                None,
            )
            if channel is None:
                raise ValueError("Unknown Dispatcharr channel")
            if kind == "channel":
                leaf = self._leaf(coordinator, channel)
                leaf.title = self._name(channel)
                return leaf
            program_title = self._program_title(data.get("programs", {}), uuid)
            if program_title is None:
                raise ValueError("No current Dispatcharr programme")
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=self._prefix(coordinator, f"programme/{uuid}"),
                media_class=MediaClass.VIDEO,
                media_content_type=MediaType.VIDEO,
                title=program_title,
                can_play=False,
                can_expand=False,
            )
        else:
            raise ValueError("Unknown Dispatcharr media identifier")

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=self._prefix(coordinator, ident),
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=title,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        coordinator, ident = self._parse(item.identifier)
        if coordinator is None or not ident.startswith("channel/"):
            raise ValueError("Invalid Dispatcharr channel identifier")
        uuid = ident.removeprefix("channel/")
        if not any(self._channel_id(channel) == uuid for channel in coordinator.data["channels"]):
            raise ValueError("Unknown Dispatcharr channel")
        entry = coordinator.entry
        base = entry.data.get(CONF_PLAYBACK_URL, entry.data["url"])
        output, output_profile = self._output_settings(coordinator)
        url = DispatcharrClient.stream_url(
            base,
            uuid,
            output_profile=output_profile,
            output_format=output,
        )
        return PlayMedia(url=url, mime_type="video/mp4" if output == "fmp4" else "video/mp2t")

    async def async_search_media(
        self, item: MediaSourceItem, query: SearchMediaQuery
    ) -> SearchMedia:
        coordinator, _ = self._parse(item.identifier)
        values = [coordinator] if coordinator is not None else self._coordinators()
        term = query.search_query.casefold()
        results = [
            self._leaf(value, channel)
            for value in values
            for channel in value.data["channels"]
            if term in self._name(channel).casefold()
        ]
        return SearchMedia(result=results)
