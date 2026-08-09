"""Config and options flows for Dispatcharr."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    DispatcharrAuthError,
    DispatcharrClient,
    DispatcharrConnectionError,
    DispatcharrError,
)
from .const import (
    CONF_API_KEY,
    CONF_OUTPUT_FORMAT,
    CONF_OUTPUT_PROFILE,
    CONF_PLAYBACK_URL,
    CONF_PROXY_STATS,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


def _schema(defaults: dict[str, Any], *, include_credentials: bool = True) -> vol.Schema:
    values: dict[Any, Any] = {}
    if include_credentials:
        values[vol.Required(CONF_URL, default=defaults.get(CONF_URL, ""))] = str
        values[vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, ""))] = str
        values[
            vol.Optional(
                CONF_PLAYBACK_URL,
                default=defaults.get(CONF_PLAYBACK_URL, defaults.get(CONF_URL, "")),
            )
        ] = str
        values[vol.Optional(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True))] = bool
    else:
        values[
            vol.Optional(
                CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )
        ] = NumberSelector(
            NumberSelectorConfig(min=MIN_SCAN_INTERVAL, max=3600, step=30, mode="box")
        )
        values[vol.Optional(CONF_OUTPUT_PROFILE, default=defaults.get(CONF_OUTPUT_PROFILE, ""))] = (
            str
        )
        values[vol.Optional(CONF_OUTPUT_FORMAT, default=defaults.get(CONF_OUTPUT_FORMAT, ""))] = (
            SelectSelector(
                SelectSelectorConfig(
                    options=["", "fmp4", "mpegts"], mode=SelectSelectorMode.DROPDOWN
                )
            )
        )
        values[vol.Optional(CONF_PROXY_STATS, default=defaults.get(CONF_PROXY_STATS, False))] = bool
    return vol.Schema(values)


async def _validate(hass, data: dict[str, Any]) -> None:
    client = DispatcharrClient(
        async_get_clientsession(hass),
        data[CONF_URL],
        data[CONF_API_KEY],
        data.get(CONF_VERIFY_SSL, True),
    )
    await client.validate()


class DispatcharrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_URL] = user_input[CONF_URL].rstrip("/")
            user_input[CONF_PLAYBACK_URL] = (
                user_input.get(CONF_PLAYBACK_URL) or user_input[CONF_URL]
            ).rstrip("/")
            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()
            try:
                await _validate(self.hass, user_input)
            except DispatcharrAuthError:
                errors["base"] = "invalid_auth"
            except DispatcharrConnectionError:
                errors["base"] = "cannot_connect"
            except DispatcharrError:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Dispatcharr", data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_reauth(self, entry_data):
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        defaults = dict(self._reauth_entry.data)
        if user_input is not None:
            updated = {**defaults, **user_input}
            try:
                await _validate(self.hass, updated)
            except DispatcharrAuthError:
                errors["base"] = "invalid_auth"
            except DispatcharrConnectionError, DispatcharrError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(self._reauth_entry, data=updated)
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=_schema(defaults), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DispatcharrOptionsFlow(config_entry)


class DispatcharrOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            data = dict(user_input)
            if data.get(CONF_OUTPUT_PROFILE) in ("", None):
                data[CONF_OUTPUT_PROFILE] = None
            else:
                data[CONF_OUTPUT_PROFILE] = int(data[CONF_OUTPUT_PROFILE])
            return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="init", data_schema=_schema(dict(self.entry.options), include_credentials=False)
        )
