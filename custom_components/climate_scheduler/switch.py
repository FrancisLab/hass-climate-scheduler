"""
Climate Schduler Switch for Home-Assistant.
"""

DEPENDENCIES = ["climate_scheduler", "climate"]


import logging
from homeassistant.components import climate
import voluptuous as vol
from typing import Coroutine, Iterable, List, Callable

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_PLATFORM,
    STATE_ON,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from . import (
    ClimateScheduler,
    DATA_CLIMATE_SCHEDULER,
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Callable[[Iterable[Entity], bool], Coroutine],
    discovery_info=None,
):
    """Set up the Climate Scheduler switches."""
    cs: ClimateScheduler = hass.data.get(DATA_CLIMATE_SCHEDULER)

    if cs is None:
        return False

    cs_switch = ClimateSchedulerSwitch(hass, cs, config)
    await async_add_entities([cs_switch])

    return True


class ClimateSchedulerSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Climate Scheduler swith."""

    def __init__(self, hass: HomeAssistant, cs: ClimateScheduler, config: dict) -> None:
        """Initialize the Climate Scheduler swith."""
        self._hass = hass
        self._cs = cs

        self._name: str = config.get(CONF_NAME)
        self._state: bool = config.get(CONF_DEFAULT_STATE)
        self._climate_entities: List[str] = config.get(CONF_CLIMATE_ENTITIES)

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
        _LOGGER.debug(self.entity_id + ": Turn on")

        self._state = True
        await self.async_update_climate()
        await self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        _LOGGER.debug(self.entity_id + ": Turn off")

        self._state = False
        await self.async_schedule_update_ha_state()

    async def async_update_climate(self) -> None:
        """Update all climate entities controlled by the swtich"""
        _LOGGER.debug(self.entity_id + ": Updating climate")

        if not self.is_on:
            _LOGGER.debug(self.entity_id + ": Disabled")
            return

        # For testing, just turn off all climate entities
        for climate_entity in self._climate_entities:
            _LOGGER.debug(self.entity_id + ": Turning off " + climate_entity)
            service_data = {ATTR_ENTITY_ID: climate_entity}
            await self._hass.services.async_call(
                CLIMATE_DOMAIN, SERVICE_TURN_OFF, service_data
            )
