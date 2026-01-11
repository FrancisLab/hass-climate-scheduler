"""The Climate Scheduler integration."""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant

VERSION = "0.0.0"

DOMAIN = "climate_scheduler"
CLIMATE_SCHEDULER_PLATFORMS = ["switch"]
CLIMATE_SCHEDULER_UPDATE_TOPIC = f"{DOMAIN}_update"
DATA_CLIMATE_SCHEDULER = "data_climate_scheduler"

CONF_UPDATE_INTERVAL = "update_interval"


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


class ClimateScheduler:
    """Climate Scheduler Implementation"""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass = hass
        self._update_interval: timedelta = config.get(
            CONF_UPDATE_INTERVAL, timedelta(minutes=15)
        )

    @property
    def update_interval(self) -> timedelta:
        return self._update_interval
