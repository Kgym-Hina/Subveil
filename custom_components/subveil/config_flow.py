"""Config flow for Subveil."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AUTO_SEARCH,
    CONF_LANGUAGES,
    CONF_MEDIA_PLAYER,
    CONF_OS_API_KEY,
    CONF_OS_PASSWORD,
    CONF_OS_USERNAME,
    DEFAULT_LANGUAGES,
    DEFAULT_PORT,
    DOMAIN,
)
from .tv_client import TvClient


def _schema(include_tv: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if include_tv:
        fields[vol.Required(CONF_HOST)] = str
        fields[vol.Required(CONF_PORT, default=DEFAULT_PORT)] = vol.Coerce(int)
    fields.update(
        {
            vol.Required(CONF_MEDIA_PLAYER): EntitySelector(
                EntitySelectorConfig(domain="media_player")
            ),
            vol.Optional(CONF_OS_API_KEY): str,
            vol.Optional(CONF_OS_USERNAME): str,
            vol.Optional(CONF_OS_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_LANGUAGES, default=DEFAULT_LANGUAGES): str,
            vol.Required(CONF_AUTO_SEARCH, default=True): bool,
        }
    )
    return vol.Schema(fields)


class SubveilConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Subveil."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            user_input[CONF_HOST] = host
            await self.async_set_unique_id(f"{host}:{user_input[CONF_PORT]}")
            self._abort_if_unique_id_configured()
            client = TvClient(async_get_clientsession(self.hass), host, user_input[CONF_PORT])
            try:
                await client.status()
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"Subveil ({host})", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_schema(True), user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SubveilOptionsFlow()


class SubveilOptionsFlow(OptionsFlow):
    """Edit media player, OpenSubtitles account and language options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_schema(False), current),
        )
