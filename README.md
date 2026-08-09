# Dispatcharr for Home Assistant

A friendly, resource-efficient [HACS](https://hacs.xyz/) custom integration that exposes a [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) server as a Home Assistant media source.

## Features

- Browse channel-number-sorted **All channels**, alphabetically sorted **Groups**, and **Profiles** in Home Assistant's media browser, including normalized channel logos that fit both grid and list layouts.
- Search channels and resolve stable UUID-backed media items for existing media-player entities.
- Aggregate sensors for channels, groups, M3U accounts, EPG sources, failed EPG sources, and optional proxy activity.
- Global and per-source buttons that queue M3U and EPG refreshes.
- Advanced `dispatcharr.force_epg_refresh` action.
- UI configuration, options, reauthentication, and privacy-preserving diagnostics.

The integration intentionally avoids creating hundreds of per-channel entities.

## Install with HACS

1. Open HACS → **Integrations** → **Custom repositories**.
2. Add `https://github.com/tenfire/ha-dispatcharr` with category **Integration**.
3. Install **Dispatcharr** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Dispatcharr**.
5. Enter the Dispatcharr API URL and a dedicated API key. The optional playback URL defaults to the API URL.

Use a least-privilege API key where possible. It is stored in the Home Assistant config entry and redacted from diagnostics.

## Playing and casting

Open an existing media player's media browser, select **Dispatcharr**, then browse or search for a channel. Automations may also use its `media-source://dispatcharr/...` identifier. Browsing a channel's stable identifier directly returns that channel's plain name and logo, allowing compatible media-player integrations to enrich now-playing state without accessing Dispatcharr internals.

The target player—not Home Assistant—fetches the resolved stream URL. Consequently:

- the target must resolve and reach the playback hostname;
- its TLS stack must trust the certificate;
- Home Assistant's API-key header is not forwarded by Chromecast;
- MPEG-TS and source codecs may not work on every receiver.

For standard Chromecast, Nest Hub, and web receivers, the integration conservatively auto-selects `fmp4` when Dispatcharr exposes exactly one active AAC output profile. Dispatcharr then remuxes/transcodes the stream; Home Assistant only supplies the direct URL and does not proxy or transcode media itself. Explicit output-format/profile options override automatic selection. If no unique AAC profile exists, raw MPEG-TS passthrough remains the fallback and you should choose an appropriate Dispatcharr profile manually. Network reachability does not guarantee codec compatibility, so test the intended receiver.

## Entities and refresh operations

The integration creates one device with low-cardinality status sensors:

- **Channels**, **Groups**, **M3U accounts**, and **EPG sources** are catalogue counts.
- **Failed EPG sources** counts sources whose latest status is failed/error.
- **Active streams** is optional and appears only when proxy-stat polling is enabled.

Refresh buttons explicitly identify their scope. **Refresh all M3U accounts** and **Refresh all EPG sources** queue global updates; per-account/source buttons queue only the named item. HTTP 202 means **accepted/queued**, not completed. These controls do not delete sources or channel data.

Options configure polling, output profile, output format, and optional proxy-stat polling.

Advanced force import example:

```yaml
action: dispatcharr.force_epg_refresh
data:
  source_id: 1 # optional; omit for all sources
```

If multiple Dispatcharr entries exist, add `config_entry_id` to target one.

## Privacy and support

Diagnostics contain aggregate counts and coordinator health only. Credentials, configured URLs, channel/programme names, source details, logos, and stream URLs are excluded or redacted.

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md). This community project is not affiliated with Dispatcharr or Home Assistant.

## Development

```bash
uv sync --group dev
uv run ruff check custom_components/dispatcharr tests
uv run pytest -q
```

The client is original code using Dispatcharr's public HTTP API. No Dispatcharr implementation source is copied here.

## License

MIT — see [LICENSE](LICENSE).
