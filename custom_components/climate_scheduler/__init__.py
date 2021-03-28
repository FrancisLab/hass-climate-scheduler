"""The Climate Scheduler integration."""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant


VERSION = "0.0.0"

DOMAIN = "climate_scheduler"
CLIMATE_SCHEDULER_PLATFORMS = ["switch"]
CLIMATE_SCHEDULER_UPDATE_TOPIC = "{0}_update".format(DOMAIN)
DATA_CLIMATE_SCHEDULER = "data_climate_scheduler"

CONF_UPDATE_INTERVAL = "update_interval"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_UPDATE_INTERVAL, default="00:15:00"): cv.positive_time_period}
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, global_config: dict):
    """Set up the Climate Scheduler component."""

    if DOMAIN not in global_config:
        return True

    config = global_config[DOMAIN]
    update_interval: timedelta = config.get(CONF_UPDATE_INTERVAL)

    climate_scheduler = ClimateScheduler(hass, update_interval)

    hass.data[DATA_CLIMATE_SCHEDULER] = climate_scheduler

    return True


class ClimateScheduler(object):
    """ Climate Scheduler Implementation """

    def __init__(self, hass: HomeAssistant, update_interval: timedelta) -> None:
        self.hass = hass
        self.data = {}
        self.data["update_interval"] = update_interval