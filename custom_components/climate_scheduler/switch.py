"""
Climate Schduler Switch for Home-Assistant.
"""

DEPENDENCIES = ["climate_scheduler", "climate"]


import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from . import (
    ClimateScheduler,
    DATA_CLIMATE_SCHEDULER,
    DOMAIN,
)

ICON = "mdi:calendar-clock"

CONF_CLIMATE_ENTITIES = "climate_entities"

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "climate_scheduler",
        vol.Optional(CONF_NAME, default="Climate Scheduler"): cv.string,
        vol.Optional(CONF_CLIMATE_ENTITIES): cv.entity_ids,
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass: HomeAssistant, config: dict, add_devices, discovery_info=None):
    """Set up the Climate Scheduler switches."""
    cs: ClimateScheduler = hass.data.get(DATA_CLIMATE_SCHEDULER)

    if cs is None:
        return False

    name = config.get(CONF_NAME)

    cs_switch = ClimateSchedulerSwitch(hass, cs, name)
    add_devices([cs_switch])

    def update(call=None):
        """Update climate"""
        cs_switch.update_climate()

    return True


class ClimateSchedulerSwitch(SwitchEntity):
    """Representation of a Climate Scheduler swith."""

    def __init__(self, hass: HomeAssistant, cs: ClimateScheduler, name: str) -> None:
        """Initialize the Climate Scheduler swith."""
        self.hass = hass
        self._cs = cs
        self._name = name
        self._entity_id = "switch." + slugify("{} {}".format("climate_scheduler", name))

    def update_climate(self):
        pass

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def name(self):
        return self._name
