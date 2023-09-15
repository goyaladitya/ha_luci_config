"""Constants for the luci_config integration."""

from datetime import timedelta


DOMAIN = "luci_config"
SIGNAL_STATE_UPDATED = "{}.updated".format(DOMAIN)

MIN_UPDATE_INTERVAL = 1
DEFAULT_UPDATE_INTERVAL = 10

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

CONN_TIMEOUT = 5.0
