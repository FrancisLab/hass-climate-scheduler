"""
Climate Schduler Switch for Home-Assistant.
"""

DEPENDENCIES = ["climate_scheduler", "climate"]


import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME, CONF_PLATFORM, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

from . import (
    ClimateScheduler,
    DATA_CLIMATE_SCHEDULER,
    DOMAIN,
)

ICON = "mdi:calendar-clock"

CONF_CLIMATE_ENTITIES = "climate_entities"
CONF_DEFAULT_STATE = "default_state"

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "climate_scheduler",
        vol.Optional(CONF_NAME, default="Climate Scheduler"): cv.string,
        vol.Optional(CONF_DEFAULT_STATE, default=False): cv.boolean,
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

    cs_switch = ClimateSchedulerSwitch(hass, cs, config)
    add_devices([cs_switch])

    def update(call=None):
        """Update climate"""
        cs_switch.update_climate()

    return True


class ClimateSchedulerSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Climate Scheduler swith."""

    def __init__(self, hass: HomeAssistant, cs: ClimateScheduler, config: dict) -> None:
        """Initialize the Climate Scheduler swith."""
        self._hass = hass
        self._cs = cs

        self._name: str = config.get(CONF_NAME)
        self._state: bool = config.get(CONF_DEFAULT_STATE)

        self._entity_id = "switch." + slugify(
            "{} {}".format("climate_scheduler", self._name)
        )

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._state is not None:
            return

        state = await self.async_get_last_state()
        self._state = state and state.state == STATE_ON

    def update_climate(self):
        """Update all climate entities controlled by the swtich"""
        pass

    @property
    def entity_id(self) -> str:
        return self._entity_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool:
        return self._state

    @property
    def icon(self) -> str:
        return ICON

    async def async_turn_on(self, **kwargs) -> None:
        self._state = True
        self.update_climate()
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._state = False
        self.schedule_update_ha_state()