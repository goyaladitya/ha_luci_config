"""Support for OpenWRT (luci) routers."""
import logging
import glob
from datetime import timedelta

from openwrt_luci_rpc import OpenWrtRpc
from openwrt_luci_rpc.utilities import normalise_keys
from openwrt_luci_rpc.constants import Constants
from openwrt_luci_rpc.exceptions import LuciConfigError, InvalidLuciTokenError

import voluptuous as vol

from homeassistant.components.switch import (
    DOMAIN,
    PLATFORM_SCHEMA,
    SwitchDevice,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

MIN_UPDATE_INTERVAL = timedelta(minutes=1)
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=10)

SIGNAL_STATE_UPDATED = "{}.updated".format(DOMAIN)

DOMAIN = "luci_config"
DATA_KEY = DOMAIN

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [
        vol.Schema({
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
            ): vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)),
        })
    ])
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    _LOGGER.info("Initializing Luci config platform: %s", hass.config.path("*.uci"))

    if not config[DOMAIN]:
        return False

    for p_config in config[DOMAIN]:
        interval = p_config.get(CONF_SCAN_INTERVAL)
        data = hass.data[DATA_KEY + "_" + p_config.get(CONF_HOST)] = LuciRPC(p_config)

        uci_files = glob.glob(hass.config.path("*.uci"))
        _LOGGER.info("Luci: %d uci files", len(uci_files))
        
        for sw_file in uci_files:
            _LOGGER.info("Luci: uci %s", sw_file)
            with open(sw_file) as uci:
                sw_values = dict()
                sw_test_key = ""
                for line in uci:
                    kv = line.split("=")
                    if len(kv) != 2:
                        _LOGGER.error("LuciConfig: invalid line: %s", line)
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

            _LOGGER.debug("LuciConfig: name: %s; desc: %s; test: %s; value: %s", sw_name, sw_desc, sw_test_key, sw_values[sw_test_key])
            if sw_name and sw_desc and sw_test_key and sw_values[sw_test_key]:
                if sw_name in data.cfg:
                    cfg = data.cfg[sw_name]
                else:
                    cfg = data.cfg[sw_name] = LuciConfig(sw_name, sw_desc, sw_test_key, sw_values, sw_file)
                    hass.async_create_task(
                        discovery.async_load_platform(
                            hass,
                            "switch",
                            DOMAIN,
                            (p_config.get(CONF_HOST), sw_name, DATA_KEY + "_" + p_config.get(CONF_HOST),),
                            config,
                        )
                    )
               
        async_dispatcher_send(hass, SIGNAL_STATE_UPDATED)

        if not data.success_init:
            return False
    
    return True

class LuciConfig():

    def __init__(self, name, desc, test_key, values, file):
        self.name = name
        self.desc = desc
        self.test_key = test_key
        self.test_value = values[test_key]
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

class LuciRPC():
    def __init__(self, config):
        """Initialize the router."""
        self.routerRpc = OpenWrtRpc(
            config.get(CONF_HOST),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            config.get(CONF_SSL),
            config.get(CONF_VERIFY_SSL),
        )
        self.success_init = self.routerRpc.is_logged_in()
        if not self.success_init:
            _LOGGER.eroor("Cannot connect to luci")    
            return

        self.cfg = {}

    def rpc_call(self, method, *args, **kwargs):
        rpc_uci_call = Constants.LUCI_RPC_UCI_PATH.format(
            self.routerRpc.router.host_api_url), method, *args
        try:
            rpc_result = self.routerRpc.router._call_json_rpc(*rpc_uci_call)
        except InvalidLuciTokenError:
            _LOGGER.info("Refreshing login token")
            self.routerRpc.router._refresh_token()
            return rpc_call(method, args, kwargs)

        return rpc_result


class LuciConfigEntity(Entity):
    """Base class for all entities."""

    def __init__(self, host, name, datastr):
        """Initialize the entity."""
        self.host = host
        self.cfgname = name
        self.datastr = datastr

        self.data = None
        self.cfg = None

    async def async_added_to_hass(self):
        """Register update dispatcher."""
        self.data = self.hass.data[self.datastr]
        self.cfg = self.data.cfg[self.cfgname]

        async_dispatcher_connect(
            self.hass, SIGNAL_STATE_UPDATED, self.async_schedule_update_ha_state
        )

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:script-text"

    @property
    def unique_id(self):
        return f"{self.host}_{self.cfgname}"

    @property
    def name(self):
        return self.cfg.desc if self.cfg else ""

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return False

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
          "file": self.cfg.file
        }