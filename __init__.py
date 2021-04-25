"""Support for OpenWRT (luci) routers."""
import asyncio
import logging
import glob
from datetime import timedelta

from openwrt_luci_rpc.openwrt_luci_rpc import OpenWrtLuciRPC # pylint: disable=import-error
from openwrt_luci_rpc.utilities import normalise_keys # pylint: disable=import-error
from openwrt_luci_rpc.constants import Constants # pylint: disable=import-error
from openwrt_luci_rpc.exceptions import LuciConfigError, InvalidLuciTokenError # pylint: disable=import-error

import voluptuous as vol # pylint: disable=import-error

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ( # pylint: disable=import-error
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)
import homeassistant.helpers.config_validation as cv # pylint: disable=import-error

from homeassistant.helpers.dispatcher import ( # pylint: disable=import-error
    async_dispatcher_send,
)

from .const import (
    DOMAIN,
    SIGNAL_STATE_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]
UPDATE_UNLISTENER = None

async def async_setup(hass: HomeAssistant, config: dict):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    global UPDATE_UNLISTENER
    if UPDATE_UNLISTENER:
        UPDATE_UNLISTENER()

    if not config_entry.unique_id:
        hass.config_entries.async_update_entry(config_entry, unique_id=config_entry.title)

    config = {}
    for key, value in config_entry.data.items():
        config[key] = value
    for key, value in config_entry.options.items():
        config[key] = value
    if config_entry.options:
        hass.config_entries.async_update_entry(config_entry, data=config, options={})

    config_glob = hass.config.path("%s/*.uci" % (DOMAIN))
    _LOGGER.info("Initializing Luci config platform: %s", config_glob)

    UPDATE_UNLISTENER = config_entry.add_update_listener(_update_listener)

    _rpc = await hass.async_add_executor_job(LuciRPC, config)
    if not _rpc.success_init:
        return False

    hass.data[DOMAIN][config.get(CONF_HOST)] = _rpc

    uci_files = glob.glob(config_glob)
    _LOGGER.debug("Luci: %d uci files", len(uci_files))
    
    for sw_file in uci_files:
        _LOGGER.debug("Luci: uci %s", sw_file)
        with open(sw_file) as uci:
            sw_values = dict()
            sw_test_key = ""
            for line in uci:
                kv = line.split("=")
                if len(kv) != 2:
                    _LOGGER.error("LuciConfig: file: %s - invalid line: %s", sw_file, line)
                    continue
                # _LOGGER.debug("LuciConfig: key: %s; val: %s", kv[0], kv[1])    

                if kv[0] == "#sw_name":
                    sw_name = kv[1].strip()
                elif kv[0] == "#sw_desc":
                    sw_desc = kv[1].strip()
                elif kv[0] == "#sw_test":
                    sw_test_key = kv[1].strip()
                else:
                    sw_values[kv[0]] = kv[1].strip().replace("'", "")

        _LOGGER.debug("LuciConfig: name: %s; desc: %s; test: %s;", sw_name, sw_desc, sw_test_key)
        if sw_name and sw_desc and sw_test_key:
            if sw_name in _rpc.cfg:
                pass
            else:
                _rpc.cfg[sw_name] = LuciConfig(sw_name, sw_desc, sw_test_key, sw_values, sw_file)


    openvpn_result = await hass.async_add_executor_job(_rpc.rpc_call, 'get_all', 'openvpn')
    _LOGGER.debug("Luci get_all openvpn returned: %s", openvpn_result)    

    for vpn_entry in openvpn_result:
        _LOGGER.debug("Luci: vpn %s", vpn_entry)
        if openvpn_result[vpn_entry][".name"] in _rpc.vpn:
            vpn = _rpc.vpn[openvpn_result[vpn_entry][".name"]]
        else:
            _LOGGER.info("Luci: vpn %s found", vpn_entry)
            vpn =_rpc.vpn[openvpn_result[vpn_entry][".name"]] = LuciVPN()

        vpn.name = openvpn_result[vpn_entry][".name"]
        if "enabled" not in openvpn_result[vpn_entry]:
            vpn.enabled = False
        else:
            vpn.enabled = openvpn_result[vpn_entry]["enabled"] == "1"

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    async_dispatcher_send(hass, SIGNAL_STATE_UPDATED)
    
    return True

async def _update_listener(hass, config_entry):
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry):
    _LOGGER.info("Unloading luci_config")

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data.pop(DOMAIN)

    return unload_ok

class LuciConfig():

    def __init__(self, name, desc, test_key, values, file):
        self.name = name
        self.desc = desc
        self.test_key = test_key.split(",")
        self.values = values
        self.file = file

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, LuciConfig):
            return (self.name == other.name)
        else:
            return False

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __hash__(self):
        return hash(self.__repr__())

class LuciVPN():

    def __init__(self):
        self.name = ""
        self.enabled = False

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, LuciVPN):
            return (self.name == other.name)
        else:
            return False

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __hash__(self):
        return hash(self.__repr__())

class LuciRPC():
    def __init__(self, config):
        """Initialize the router."""
        self._rpc = OpenWrtLuciRPC(
            config.get(CONF_HOST),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            config.get(CONF_SSL),
            config.get(CONF_VERIFY_SSL),
        )
        self.host = config.get(CONF_HOST)
        self.success_init = self._rpc.token is not None
        if not self.success_init:
            _LOGGER.error("Cannot connect to luci")    
            return

        self.cfg = {}
        self.vpn = {}

    def rpc_call(self, method, *args,  **kwargs):
        rpc_uci_call = Constants.LUCI_RPC_UCI_PATH.format(
            self._rpc.host_api_url), method, *args
        try:
            rpc_result = self._rpc._call_json_rpc(*rpc_uci_call)
        except InvalidLuciTokenError:
            _LOGGER.info("Refreshing login token")
            self._rpc._refresh_token()
            return self.rpc_call(method, args)

        return rpc_result

