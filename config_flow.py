"""Config flow for LuciConfig."""
import asyncio
import logging

from openwrt_luci_rpc.openwrt_luci_rpc import OpenWrtLuciRPC # pylint: disable=import-error
from openwrt_luci_rpc.exceptions import LuciConfigError, InvalidLuciTokenError # pylint: disable=import-error

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import callback
from homeassistant.const import ( # pylint: disable=import-error
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)

from .const import (
    DOMAIN,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_UPDATE_INTERVAL,
    CONN_TIMEOUT,
)
_LOGGER = logging.getLogger(__name__)

RESULT_CONN_ERROR = "cannot_connect"
RESULT_LOG_MESSAGE = {RESULT_CONN_ERROR: "Connection error"}


def _try_connect(host, username, password, ssl, verify_ssl):
    """Check if we can connect."""
    try:
        rpc = OpenWrtLuciRPC(host, username, password, ssl, verify_ssl)
        success_init = rpc.token is not None
        if not success_init:
            _LOGGER.error("Cannot connect to luci")    
            return False
    except (LuciConfigError, InvalidLuciTokenError) as e:
        _LOGGER.error(str(e))
        return False
    return True

@config_entries.HANDLERS.register(DOMAIN)
class LuciConfigFlowHandler(config_entries.ConfigFlow):
    """Config flow for LuciConfig component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """LuciConfig options callback."""
        return LuciConfigOptionsFlowHandler(config_entry)

    def __init__(self):
        """Init LuciConfigFlowHandler."""
        self._errors = {}
        self._host = None
        self._username = None
        self._password = None
        self._ssl = DEFAULT_SSL
        self._verify_ssl = DEFAULT_VERIFY_SSL
        self._update_interval = DEFAULT_UPDATE_INTERVAL

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        self._is_import = True
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        self._errors = {}

        data_schema = {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
        }

        if user_input is not None:
            self._host = str(user_input[CONF_HOST])
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._ssl = user_input[CONF_SSL]
            self._verify_ssl = user_input[CONF_VERIFY_SSL]
            self._update_interval = user_input[CONF_SCAN_INTERVAL]

            try:
                await asyncio.wait_for(
                    self.hass.async_add_executor_job(_try_connect, self._host, self._username, self._password, self._ssl, self._verify_ssl),
                    timeout=CONN_TIMEOUT,
                )

                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_HOST: self._host,
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_SSL: self._ssl,
                        CONF_VERIFY_SSL: self._verify_ssl,
                        CONF_SCAN_INTERVAL: self._update_interval
                    },
                )

            except (asyncio.TimeoutError, CannotConnect):
                result = RESULT_CONN_ERROR

            if self._is_import:
                _LOGGER.error(
                    "Error importing from configuration.yaml: %s",
                    RESULT_LOG_MESSAGE.get(result, "Generic Error"),
                )
                return self.async_abort(reason=result)

            self._errors["base"] = result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )


class LuciConfigOptionsFlowHandler(config_entries.OptionsFlow):
    """Option flow for LuciConfig component."""

    def __init__(self, config_entry):
        """Init LuciConfigOptionsFlowHandler."""
        self._errors = {}
        self._host = config_entry.data[CONF_HOST] if CONF_HOST in config_entry.data else None
        self._username = config_entry.data[CONF_USERNAME] if CONF_USERNAME in config_entry.data else None
        self._password = config_entry.data[CONF_PASSWORD] if CONF_PASSWORD in config_entry.data else None
        self._ssl = config_entry.data[CONF_SSL] if CONF_SSL in config_entry.data else DEFAULT_SSL
        self._verify_ssl = config_entry.data[CONF_VERIFY_SSL] if CONF_VERIFY_SSL in config_entry.data else DEFAULT_VERIFY_SSL
        self._update_interval = config_entry.data[CONF_SCAN_INTERVAL] if CONF_SCAN_INTERVAL in config_entry.data else DEFAULT_UPDATE_INTERVAL

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        self._errors = {}

        if user_input is not None:
            self._host = str(user_input[CONF_HOST])
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._ssl = user_input[CONF_SSL]
            self._verify_ssl = user_input[CONF_VERIFY_SSL]
            self._update_interval = user_input[CONF_SCAN_INTERVAL]

        data_schema = {
            vol.Required(CONF_HOST, default=self._host): str,
            vol.Required(CONF_USERNAME, default=self._username): str,
            vol.Required(CONF_PASSWORD, default=self._password): str,
            vol.Optional(CONF_SSL, default=self._ssl): bool,
            vol.Optional(CONF_VERIFY_SSL, default=self._verify_ssl): bool,
            vol.Optional(CONF_SCAN_INTERVAL, default=self._update_interval): int,
        }

        if user_input is not None:
            try:
                await asyncio.wait_for(
                    self.hass.async_add_executor_job(_try_connect, self._host, self._username, self._password, self._ssl, self._verify_ssl),
                    timeout=CONN_TIMEOUT,
                )

                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_HOST: self._host,
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_SSL: self._ssl,
                        CONF_VERIFY_SSL: self._verify_ssl,
                        CONF_SCAN_INTERVAL: self._update_interval
                    },
                )

            except (asyncio.TimeoutError, CannotConnect):
                _LOGGER.error("cannot connect")
                result = RESULT_CONN_ERROR

            self._errors["base"] = result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we can not connect."""
