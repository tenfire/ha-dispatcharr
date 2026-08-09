"""Behavior tests for the Dispatcharr media source."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from homeassistant.components.media_player.browse_media import SearchMediaQuery
from homeassistant.components.media_source import MediaSourceItem

from custom_components.dispatcharr.const import CONF_OUTPUT_FORMAT, DOMAIN
from custom_components.dispatcharr.media_source import DispatcharrMediaSource

ENTRY_ID = "synthetic-entry"
CHANNEL_ID = "channel-alpha"


class FakeConfigEntries:
    """Minimal config-entry registry needed by the media source."""

    def __init__(self, entry):
        self.entry = entry

    def async_entries(self, domain):
        assert domain == DOMAIN
        return [self.entry]


@pytest.fixture
def media_source():
    entry = SimpleNamespace(
        entry_id=ENTRY_ID,
        data={
            "url": "https://example.invalid",
            "playback_url": "https://media.example.invalid",
        },
        options={"output_profile": 4, "output_format": "fmp4"},
        title="Example server",
    )
    coordinator = SimpleNamespace(
        entry=entry,
        data={
            "channels": [
                {
                    "uuid": CHANNEL_ID,
                    "name": "Synthetic News",
                    "effective_channel_number": 20.0,
                    "channel_group_id": 8,
                    "profile_id": 4,
                    "effective_logo_id": 17,
                },
                {
                    "uuid": "channel-beta",
                    "name": "Example Sports",
                    "effective_channel_number": 3.0,
                    "channel_group_id": 9,
                    "profile_id": 5,
                },
            ],
            "groups": [
                {"id": 8, "name": "Example group"},
                {"id": 9, "name": "alpha group"},
                {"id": 99, "name": "Empty group"},
            ],
            "profiles": [
                {"id": 4, "name": "Example profile"},
                {"id": 99, "name": "Unused profile"},
            ],
            "programs": {CHANNEL_ID: {"title": "Synthetic bulletin"}},
            "output_profiles": [
                {
                    "id": 12,
                    "name": "Synthetic AAC",
                    "is_active": True,
                    "parameters": {"audio_codec": "aac", "video_codec": "copy"},
                }
            ],
        },
    )
    hass = SimpleNamespace(
        config_entries=FakeConfigEntries(entry),
        data={DOMAIN: {ENTRY_ID: coordinator}},
    )
    return DispatcharrMediaSource(hass), hass


def item(hass, identifier=""):
    return MediaSourceItem(hass, DOMAIN, identifier, None)


@pytest.mark.asyncio
async def test_root_and_all_channel_browsing(media_source):
    source, hass = media_source
    root = await source.async_browse_media(item(hass))
    assert [child.title for child in root.children] == ["Example server"]

    server = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}"))
    assert [child.title for child in server.children] == ["All channels", "Groups", "Profiles"]

    all_channels = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/all"))
    assert [child.title for child in all_channels.children] == [
        "Example Sports",
        "Synthetic News — Synthetic bulletin",
    ]
    news = all_channels.children[1]
    assert news.identifier == f"entry/{ENTRY_ID}/channel/{CHANNEL_ID}"
    assert news.can_play is True
    assert news.media_class == "video"
    assert news.media_content_type == "video/mp4"
    assert news.thumbnail == f"/api/dispatcharr/{ENTRY_ID}/artwork/17"
    assert all(child.media_content_type.startswith("video/") for child in all_channels.children)


@pytest.mark.asyncio
async def test_direct_channel_browse_returns_plain_name_and_artwork(media_source):
    """A playable channel identifier is also a public metadata lookup."""
    source, hass = media_source

    channel = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/channel/{CHANNEL_ID}"))

    assert channel.title == "Synthetic News"
    assert channel.identifier == f"entry/{ENTRY_ID}/channel/{CHANNEL_ID}"
    assert channel.can_play is True
    assert channel.can_expand is False
    assert channel.thumbnail == f"/api/dispatcharr/{ENTRY_ID}/artwork/17"


@pytest.mark.asyncio
async def test_direct_channel_browse_rejects_unknown_uuid(media_source):
    """Direct metadata lookup cannot synthesize nonexistent channels."""
    source, hass = media_source

    with pytest.raises(ValueError, match="Unknown Dispatcharr channel"):
        await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/channel/not-present"))


@pytest.mark.asyncio
async def test_default_browse_mime_is_mpeg_ts(media_source):
    source, hass = media_source
    hass.data[DOMAIN][ENTRY_ID].entry.options.pop(CONF_OUTPUT_FORMAT)
    hass.data[DOMAIN][ENTRY_ID].data["output_profiles"] = []

    all_channels = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/all"))

    assert {child.media_content_type for child in all_channels.children} == {"video/mp2t"}


@pytest.mark.asyncio
async def test_group_and_profile_filtering(media_source):
    source, hass = media_source
    group = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/group/8"))
    profile = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/profile/4"))
    assert [child.title for child in group.children] == ["Synthetic News — Synthetic bulletin"]
    assert [child.title for child in profile.children] == ["Synthetic News — Synthetic bulletin"]

    groups = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/groups"))
    profiles = await source.async_browse_media(item(hass, f"entry/{ENTRY_ID}/profiles"))
    assert [child.title for child in groups.children] == ["alpha group", "Example group"]
    assert [child.title for child in profiles.children] == ["Example profile"]


@pytest.mark.asyncio
async def test_search_is_case_insensitive(media_source):
    source, hass = media_source
    result = await source.async_search_media(item(hass), SearchMediaQuery(search_query="news"))
    assert [media.title for media in result.result] == ["Synthetic News — Synthetic bulletin"]


@pytest.mark.asyncio
async def test_resolve_uses_playback_url_and_safe_options(media_source):
    source, hass = media_source
    result = await source.async_resolve_media(item(hass, f"entry/{ENTRY_ID}/channel/{CHANNEL_ID}"))
    assert result.url == (
        f"https://media.example.invalid/proxy/ts/stream/{CHANNEL_ID}"
        "?output_profile=4&output_format=fmp4"
    )
    assert result.mime_type == "video/mp4"


@pytest.mark.asyncio
async def test_resolve_automatically_uses_unique_active_aac_profile(media_source):
    source, hass = media_source
    hass.data[DOMAIN][ENTRY_ID].entry.options = {}

    result = await source.async_resolve_media(item(hass, f"entry/{ENTRY_ID}/channel/{CHANNEL_ID}"))

    assert result.url.endswith("?output_profile=12&output_format=fmp4")
    assert result.mime_type == "video/mp4"


@pytest.mark.asyncio
async def test_resolve_does_not_guess_between_multiple_aac_profiles(media_source):
    source, hass = media_source
    coordinator = hass.data[DOMAIN][ENTRY_ID]
    coordinator.entry.options = {}
    coordinator.data["output_profiles"].append({"id": 13, "is_active": True, "command": "-c:a aac"})

    result = await source.async_resolve_media(item(hass, f"entry/{ENTRY_ID}/channel/{CHANNEL_ID}"))

    assert "output_profile" not in result.url
    assert "output_format" not in result.url
    assert result.mime_type == "video/mp2t"


@pytest.mark.asyncio
async def test_resolve_rejects_unknown_channel(media_source):
    source, hass = media_source
    with pytest.raises(ValueError, match="Unknown Dispatcharr channel"):
        await source.async_resolve_media(item(hass, f"entry/{ENTRY_ID}/channel/not-present"))
