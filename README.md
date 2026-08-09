# Dispatcharr for Home Assistant

A friendly, resource-efficient [HACS](https://hacs.xyz/) custom integration that exposes a [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) server as a Home Assistant media source.

## Features

- Browse **All channels**, channel **Groups**, and **Profiles** in Home Assistant's media browser.
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

Open an existing media player's media browser, select **Dispatcharr**, then browse or search for a channel. Automations may also use its `media-source://dispatcharr/...` identifier.

The target player—not Home Assistant—fetches the resolved stream URL. Consequently:

- the target must resolve and reach the playback hostname;
- its TLS stack must trust the certificate;
- Home Assistant's API-key header is not forwarded by Chromecast;
- MPEG-TS and source codecs may not work on every receiver.

Choose a compatible Dispatcharr output profile/format when needed. Network reachability does not guarantee codec compatibility, so test the intended receiver.

## Options and refresh operations

Options configure polling, channel/output profiles, output format, and optional proxy-stat polling. Refresh buttons queue work; HTTP 202 means **accepted/queued**, not completed.

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
