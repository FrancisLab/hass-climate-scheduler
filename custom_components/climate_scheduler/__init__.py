"""The Climate Scheduler integration."""
import asyncio

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

import datetime

from homeassistant.core import HomeAssistant

DOMAIN = "climate_scheduler"
CONF_UPDATE_INTERVAL = "update_interval"

DATA_CLIMATE_SCHEDULER = "data_climate_scheduler"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Optional(CONF_UPDATE_INTERVAL, default="00:15:00"): cv.time_period}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, global_config: dict):
    """Set up the Climate Scheduler component."""

    if DOMAIN not in global_config:
        return True

    config = global_config[DOMAIN]
    update_interval: datetime.timedelta = config.get(CONF_UPDATE_INTERVAL)

    climate_scheduler = ClimateScheduler(hass, update_interval)

    hass.data[DATA_CLIMATE_SCHEDULER] = climate_scheduler

    return True


class ClimateScheduler(object):
    """ Climate Scheduler Implementation """

    def __init__(
        self, hass: HomeAssistant, update_interval: datetime.timedelta
    ) -> None:
        self.hass = hass
        self.data = {}
        self.data["update_interval"] = update_interval