import logging

from homeassistant.helpers.entity import ToggleEntity # pylint: disable=import-error

from . import DATA_KEY, LuciConfigEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Volvo switch."""
    if discovery_info is None:
        return
    add_entities([LuciConfigSwitch(*discovery_info)])


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
        params = self._cfg.test_key.split(".")
        cfg_value = self._rpc.rpc_call('get', *params)
        if (cfg_value is None):
            _LOGGER.error("LuciConfig: cannot get current value for %s", self._cfg.test_key)
            self._is_on = False
        else:
            _LOGGER.debug("Luci get %s returned: %s", self._cfg.test_key, cfg_value) 
            self._is_on = (cfg_value == self._cfg.test_value)
