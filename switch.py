import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import ToggleEntity # pylint: disable=import-error
from homeassistant.const import ( # pylint: disable=import-error
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_SCAN_INTERVAL,
)

from . import LuciConfigEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches dynamically."""

    entities= []
    rpc = hass.data[DOMAIN][config_entry.data.get(CONF_HOST)]
    for key in rpc.cfg:
        entities.append(LuciConfigSwitch(rpc, key))
    
    async_add_entities(entities, True)
class LuciConfigSwitch(LuciConfigEntity, ToggleEntity):
    """Representation of a Luci switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

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
