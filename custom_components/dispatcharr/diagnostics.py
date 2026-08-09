"""Privacy-preserving diagnostics for Dispatcharr."""

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

TO_REDACT = {
    "api_key",
    "token",
    "key",
    "url",
    "playback_url",
    "logo",
    "logo_url",
    "stream_url",
    "next",
    "previous",
}


async def async_get_config_entry_diagnostics(hass, entry):
    """Return counts and health metadata, never channel or programme details."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data
    sources = data.get("sources", [])
    return async_redact_data(
        {
            "entry": {"data": dict(entry.data), "options": dict(entry.options)},
            "last_update_success": coordinator.last_update_success,
            "counts": {
                "channels": len(data.get("channels", [])),
                "groups": len(data.get("groups", [])),
                "profiles": len(data.get("profiles", [])),
                "m3u_accounts": len(data.get("accounts", [])),
                "epg_sources": len(sources),
                "failed_epg_sources": sum(
                    1
                    for source in sources
                    if str(source.get("status", "")).lower() in {"failed", "error"}
                ),
            },
            "proxy_stats_enabled": bool(entry.options.get("proxy_stats", False)),
        },
        TO_REDACT,
    )
