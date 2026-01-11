"""The Climate Scheduler integration."""

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant

from .const import CONF_UPDATE_INTERVAL, DATA_CLIMATE_SCHEDULER
from .scheduler import ClimateScheduler

DOMAIN = "climate_scheduler"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL, default="00:15:00"
                ): cv.positive_time_period
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, global_config: dict) -> bool:
    """Set up the Climate Scheduler component."""

    _LOGGER.debug("Setting up with config: %s", global_config)

    config = global_config.get(DOMAIN)
    if config is None:
        _LOGGER.error("No config found for Climate Scheduler")
        return False

    climate_scheduler = ClimateScheduler(hass, config)
    hass.data[DATA_CLIMATE_SCHEDULER] = climate_scheduler

    return True
