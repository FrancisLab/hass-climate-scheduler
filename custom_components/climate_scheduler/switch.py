"""
Climate Schduler Switch for Home-Assistant.
"""

DEPENDENCIES = ["climate_scheduler", "climate"]


from datetime import timedelta
import logging
import voluptuous as vol
from typing import Coroutine, Iterable, List, Callable, Dict, Optional

from voluptuous.schema_builder import Object
from voluptuous.validators import Coerce

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
CONF_PROFILES = "profiles"

CONF_PROFILE_NAME = "name"
CONF_PROFILE_ID = "id"
CONF_PROFILE_SCHEDULE = "schedule"

CONF_SCHEDULE_TIME = "time"
CONF_SCHEDULE_HVAC = "hvac_mode"
CONF_SCHEDULE_MIN_TEMPERATURE = "min_temperature"
CONF_SCHEDULE_MAX_TEMPERATURE = "max_temperature"
CONF_SCHEDULE_FAN_MODE = "fan_mode"
CONF_SCHEDULE_SWING_MODE = "swing_mode"

SCHEDULE_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_SCHEDULE_TIME): cv.positive_time_period,  # Validator?
            vol.Optional(CONF_SCHEDULE_HVAC): cv.string,  # Validator?
            vol.Optional(CONF_SCHEDULE_MIN_TEMPERATURE): vol.Coerce(float),
            vol.Optional(CONF_SCHEDULE_MAX_TEMPERATURE): vol.Coerce(float),
            vol.Optional(CONF_SCHEDULE_FAN_MODE): cv.string,  # Validator?
            vol.Optional(CONF_SCHEDULE_SWING_MODE): cv.string,  # Validator?
        }
    ]
)

PROFILES_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_PROFILE_ID): str,
            vol.Optional(CONF_NAME, default="Unamed Profile"): str,
            vol.Required(CONF_PROFILE_SCHEDULE): SCHEDULE_SCHEMA,
        }
    ]
)

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "climate_scheduler",
        vol.Optional(CONF_NAME, default="Climate Scheduler"): cv.string,
        vol.Optional(CONF_DEFAULT_STATE, default=False): cv.boolean,
        vol.Optional(CONF_CLIMATE_ENTITIES): cv.entity_ids,
        vol.Optional(CONF_PROFILES): PROFILES_SCHEMA,
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
    async_add_entities([cs_switch])

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

        self._profiles: Dict[str, ClimateSchedulerProfile] = {
            profile_conf[CONF_PROFILE_ID]: ClimateSchedulerProfile(profile_conf)
            for profile_conf in config.get(CONF_PROFILES)
        }

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
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        _LOGGER.debug(self.entity_id + ": Turn off")

        self._state = False
        self.async_schedule_update_ha_state()

    async def async_update_climate(self) -> None:
        """Update all climate entities controlled by the swtich"""
        _LOGGER.debug(self.entity_id + ": Updating climate")

        if not self.is_on:
            _LOGGER.debug(self.entity_id + ": Disabled")
            return

        # For testing, just turn off all climate entities
        # for climate_entity in self._climate_entities:
        #     _LOGGER.debug(self.entity_id + ": Turning off " + climate_entity)
        #     service_data = {ATTR_ENTITY_ID: climate_entity}
        #     await self._hass.services.async_call(
        #         CLIMATE_DOMAIN, SERVICE_TURN_OFF, service_data
        #     )


class ClimateSchedulerProfile(Object):
    def __init__(self, config: dict) -> None:
        self._id: str = config.get(CONF_PROFILE_ID)
        self._name: str = config.get(CONF_PROFILE_NAME)

        # TODO: Validate schedule time < 24h. Do in validator?

        self._schedules = [
            ClimateShedulerSchedule(c) for c in config.get(CONF_PROFILE_SCHEDULE)
        ]
        self._schedules.sort(key=lambda x: x.time)


class ClimateShedulerSchedule(Object):
    def __init__(self, config: dict) -> None:
        self._time: timedelta = config.get(CONF_SCHEDULE_TIME)
        self._hvac_mode: Optional[str] = config.get(CONF_SCHEDULE_HVAC)
        self._fan_mode: Optional[str] = config.get(CONF_SCHEDULE_FAN_MODE)
        self._swing_mode: Optional[str] = config.get(CONF_SCHEDULE_SWING_MODE)
        self._min_temperature: Optional[int] = config.get(CONF_SCHEDULE_MIN_TEMPERATURE)
        self._max_temperature: Optional[int] = config.get(CONF_SCHEDULE_MAX_TEMPERATURE)

    @property
    def time(self) -> timedelta:
        return self._time