import logging

from homeassistant.helpers.entity import ToggleEntity

from . import DATA_KEY, LuciConfigEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a Volvo switch."""
    if discovery_info is None:
        return
    async_add_entities([LuciConfigSwitch(*discovery_info)])


class LuciConfigSwitch(LuciConfigEntity, ToggleEntity):
    """Representation of a Luci switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        params = self.cfg.test_key.split(".")
        cfg_value = self.data.rpc_call('get', *params)
        if (cfg_value is None):
            _LOGGER.error("LuciConfig: cannot get current value for %s", self.cfg.test_key)
            return False
        else:
            _LOGGER.debug("Luci get %s returned: %s", self.cfg.test_key, cfg_value) 
            return (cfg_value == self.cfg.test_value)

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        #await self.instrument.turn_on()
        _LOGGER.debug("LuciConfig: %s turned on", self.cfg.name)

        for key in self.cfg.values:
            params = key.split(".")
            params.append(self.cfg.values[key])
            self.data.rpc_call("set", *params)
        self.data.rpc_call("apply")

        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off. NOOP"""

