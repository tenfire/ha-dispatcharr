"""Constants for Dispatcharr."""

from datetime import timedelta

DOMAIN = "dispatcharr"
PLATFORMS = ["sensor", "button"]
CONF_API_KEY = "api_key"
CONF_PLAYBACK_URL = "playback_url"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_OUTPUT_PROFILE = "output_profile"
CONF_OUTPUT_FORMAT = "output_format"
CONF_PROXY_STATS = "proxy_stats"
DEFAULT_SCAN_INTERVAL = 300
DEFAULT_OUTPUT_FORMAT = ""
MIN_SCAN_INTERVAL = 60
UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
SERVICE_FORCE_EPG_REFRESH = "force_epg_refresh"
