"""Dispatcharr sensors."""

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class Description(SensorEntityDescription):
    data_key: str | None = None


DESCRIPTIONS = (
    Description(
        key="channels",
        translation_key="channels",
        data_key="channels",
        icon="mdi:television-play",
    ),
    Description(
        key="groups",
        translation_key="groups",
        data_key="groups",
        icon="mdi:folder-multiple",
    ),
    Description(
        key="m3u_accounts",
        translation_key="m3u_accounts",
        data_key="accounts",
        icon="mdi:playlist-play",
    ),
    Description(
        key="epg_sources",
        translation_key="epg_sources",
        data_key="sources",
        icon="mdi:calendar-text",
    ),
    Description(
        key="failed_epg_sources",
        translation_key="failed_epg_sources",
        icon="mdi:alert-circle-outline",
    ),
    Description(
        key="active_streams",
        translation_key="active_streams",
        icon="mdi:broadcast",
    ),
)


async def async_setup_entry(hass, entry, add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    add_entities(
        DispatcharrSensor(c, d)
        for d in DESCRIPTIONS
        if d.key != "active_streams" or entry.options.get("proxy_stats")
    )


class DispatcharrSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, c, d):
        super().__init__(c)
        self.entity_description = d
        self._attr_unique_id = f"{c.entry.entry_id}_{d.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, c.entry.entry_id)},
            "name": "Dispatcharr",
            "manufacturer": "Dispatcharr",
        }

    @property
    def native_value(self):
        d = self.coordinator.data or {}
        if self.entity_description.data_key:
            return len(d.get(self.entity_description.data_key, []))
        if self.entity_description.key == "failed_epg_sources":
            return sum(
                1
                for x in d.get("sources", [])
                if str(x.get("status", "")).lower() in {"failed", "error"}
            )
        stats = d.get("stats", {}) or {}
        live = stats.get("live")
        if isinstance(live, dict):
            return live.get("count", 0)
        return stats.get("active_streams", stats.get("streams", 0))

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != "active_streams":
            return None
        data = self.coordinator.data or {}
        stats = data.get("stats", {}) or {}
        live = stats.get("live") if isinstance(stats.get("live"), dict) else {}
        streams = [
            {
                "channel": channel.get("channel_name") or channel.get("stream_name"),
                "clients": channel.get("client_count", 0),
                "bitrate": channel.get("avg_bitrate"),
                "bitrate_kbps": channel.get("avg_bitrate_kbps"),
                "resolution": channel.get("resolution"),
                "video_codec": channel.get("video_codec"),
                "audio_codec": channel.get("audio_codec"),
                "fps": channel.get("source_fps"),
                "uptime": channel.get("uptime"),
                "stream_type": channel.get("stream_type"),
            }
            for channel in live.get("channels") or []
        ]
        return {
            "streams": streams,
            "total_clients": sum(stream["clients"] or 0 for stream in streams),
            "total_bitrate_kbps": round(
                sum(stream["bitrate_kbps"] or 0 for stream in streams), 1
            ),
        }
