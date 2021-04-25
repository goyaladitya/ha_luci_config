import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import ToggleEntity # pylint: disable=import-error
from homeassistant.const import ( # pylint: disable=import-error
    CONF_HOST,
)
from homeassistant.helpers.entity import Entity # pylint: disable=import-error
from homeassistant.helpers.dispatcher import ( # pylint: disable=import-error
    async_dispatcher_connect,
)

from .const import (
    DOMAIN,
    SIGNAL_STATE_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches dynamically."""

    entities= []
    rpc = hass.data[DOMAIN][config_entry.data.get(CONF_HOST)]
    for key in rpc.cfg:
        entities.append(LuciConfigSwitch(rpc, key))
    for key in rpc.vpn:
        entities.append(LuciVPNSwitch(rpc, key))
    
    async_add_entities(entities, True)

class LuciEntity(Entity):
    """ Base class for all entities. """

    def __init__(self, rpc, name):
        """Initialize the entity."""

        _LOGGER.debug("New entity: %s", name)

        self._rpc = rpc
        self.cfgname = name
        self._is_on = False

        self.host = self._rpc.host

    async def async_added_to_hass(self):
        """Register update dispatcher."""
        async_dispatcher_connect(
            self.hass, SIGNAL_STATE_UPDATED, self.async_schedule_update_ha_state
        )

    @property
    def unique_id(self):
        return f"{self.host}_{self.cfgname}"

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on
    
class LuciConfigSwitch(LuciEntity, ToggleEntity):
    """Representation of a Luci switch."""

    def __init__(self, rpc, name):
        super().__init__(rpc, name)
        self._cfg = self._rpc.cfg[self.cfgname]

    @property
    def name(self):
        return self._cfg.desc if self._cfg else ""

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:script-text"

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
        "file": self._cfg.file
        }

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        #await self.instrument.turn_on()
        _LOGGER.debug("LuciConfig: %s turned on", self._cfg.name)

        for key in self._cfg.values:
            params = key.split(".")
            params.append(self._cfg.values[key])
            self._rpc.rpc_call("set", *params)
        self._rpc.rpc_call("apply")

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off. NOOP"""

    def update(self):
        """Update vesync device."""
        self._is_on = False
        for key in self._cfg.test_key:
            if (self._cfg.values[key] is None):
                _LOGGER.error("LuciConfig: test key '%s' is not in uci values", key)
                return
            params = key.split(".")
            try:
                cfg_value = self._rpc.rpc_call('get', *params)
            except:
                return
            if (cfg_value is None):
                _LOGGER.error("LuciConfig: cannot get current value for %s", key)
                return
            else:
                _LOGGER.debug("Luci get %s returned: %s", key, cfg_value) 
                if (cfg_value != self._cfg.values[key]):
                    return
        self._is_on = True

class LuciVPNSwitch(LuciEntity, ToggleEntity):
    """Representation of a Luci switch."""

    def __init__(self, rpc, name):
        super().__init__(rpc, name)
        self._vpn = self._rpc.vpn[self.cfgname]

    @property
    def name(self):
        return "%s VPN" % (self.cfgname)

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:vpn"

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        #await self.instrument.turn_on()
        _LOGGER.debug("Luci: %s turned on", self._vpn.name)

        self._rpc.rpc_call("set", "openvpn", self._vpn.name, "enabled", "1")
        self._rpc.rpc_call("commit", "openvpn")

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        #await self.instrument.turn_off()
        _LOGGER.debug("Luci: %s turned off", self._vpn.name)

        self._rpc.rpc_call("set", "openvpn", self._vpn.name, "enabled", "0")
        self._rpc.rpc_call("commit", "openvpn")

        self.schedule_update_ha_state()

    def update(self):
        """Update vesync device."""
        self._is_on = False
        try:
            cfg_value = self._rpc.rpc_call('get', "openvpn", self._vpn.name, "enabled")
        except:
            return
        if (cfg_value is not None):
            _LOGGER.debug("LuciOpenVPN get %s returned: %s", self._vpn.name, cfg_value) 
            self._is_on = (cfg_value == "1")
        