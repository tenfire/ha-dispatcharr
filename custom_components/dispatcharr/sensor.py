"""Dispatcharr sensors."""

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class Description(SensorEntityDescription):
    data_key: str | None = None


DESCRIPTIONS = (
    Description(key="channels", translation_key="channels", data_key="channels"),
    Description(key="groups", translation_key="groups", data_key="groups"),
    Description(key="m3u_accounts", translation_key="m3u_accounts", data_key="accounts"),
    Description(key="epg_sources", translation_key="epg_sources", data_key="sources"),
    Description(key="failed_epg_sources", translation_key="failed_epg_sources"),
    Description(key="active_streams", translation_key="active_streams"),
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
        d = self.coordinator.data
        if self.entity_description.data_key:
            return len(d.get(self.entity_description.data_key, []))
        if self.entity_description.key == "failed_epg_sources":
            return sum(
                1
                for x in d.get("sources", [])
                if str(x.get("status", "")).lower() in {"failed", "error"}
            )
        stats = d.get("stats", {})
        return stats.get("active_streams", stats.get("streams", 0))
