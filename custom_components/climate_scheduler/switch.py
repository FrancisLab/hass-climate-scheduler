"""
Climate Schduler Switch for Home-Assistant.
"""

DEPENDENCIES = ["climate_scheduler", "climate"]


import asyncio
from collections import namedtuple
from datetime import timedelta
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
import logging
import voluptuous as vol
from typing import Coroutine, Iterable, List, Callable, Dict, Optional, Tuple

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.util.dt import now

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
CONF_PROFILE_DEFAULT_HVAC_MODE = "default_hvac_mode"
CONF_PROFILE_DEFAULT_FAN_MODE = "default_fan_mode"
CONF_PROFILE_DEFAULT_SWING_MODE = "default_swing_mode"
CONF_PROFILE_DEFAULT_MIN_TEMP = "default_min_temp"
CONF_PROFILE_DEFAULT_MAX_TEMP = "default_max_temp"

CONF_SCHEDULE_TIME = "time"
CONF_SCHEDULE_HVAC = "hvac_mode"
CONF_SCHEDULE_MIN_TEMP = "min_temperature"
CONF_SCHEDULE_MAX_TEMP = "max_temperature"
CONF_SCHEDULE_FAN_MODE = "fan_mode"
CONF_SCHEDULE_SWING_MODE = "swing_mode"

SCHEDULE_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_SCHEDULE_TIME): cv.positive_time_period,  # Validator?
            vol.Optional(CONF_SCHEDULE_HVAC): cv.string,  # Validator?
            vol.Optional(CONF_SCHEDULE_MIN_TEMP): vol.Coerce(float),
            vol.Optional(CONF_SCHEDULE_MAX_TEMP): vol.Coerce(float),
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
            vol.Optional(CONF_PROFILE_DEFAULT_HVAC_MODE): str,  # Validator?
            vol.Optional(CONF_PROFILE_DEFAULT_FAN_MODE): str,  # Validator?
            vol.Optional(CONF_PROFILE_DEFAULT_SWING_MODE): str,  # Validator?
            vol.Optional(CONF_PROFILE_DEFAULT_MIN_TEMP): vol.Coerce(float),
            vol.Optional(CONF_PROFILE_DEFAULT_MAX_TEMP): vol.Coerce(float),
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


ComputedClimateData = namedtuple(
    "ComputedClimateData",
    ["hvac_mode", "fan_mode", "swing_mode", "min_temperature", "max_temperature"],
)


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

        # TODO: How to switch between profiles? New service? Implement input_select?
        # TODO: How to display current profile in entity state/attributes?
        # TODO: How to restore current profile in async_added_to_hass?
        self._curent_profile = self._profiles.get("master_bedroom_heating")

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

    # TODO: Expose more properties to UI

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

        if self._curent_profile is None:
            _LOGGER.debug(self.entity_id + ": No profile")
            return

        # TODO: Track temperature of entities. Only heat/cool if under/above threshold

        dt = now()
        time_of_day = timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second)
        climate_data = self._curent_profile.compute_climate(time_of_day)

        update_tasks = [
            self._async_update_climate_entity(entity, climate_data)
            for entity in self._climate_entities
        ]
        await asyncio.wait(update_tasks)

    async def _async_update_climate_entity(
        self, entity: str, data: Optional[ComputedClimateData]
    ) -> None:
        if data is None:
            return

        await self._async_set_climate_hvac_mode(entity, data.hvac_mode)
        await self._async_set_climate_fan_mode(entity, data.fan_mode)
        await self._async_set_climate_swing_mode(entity, data.swing_mode)
        await self._async_set_climate_temperature(
            entity, data.hvac_mode, data.min_temperature, data.max_temperature
        )

    async def _async_set_climate_hvac_mode(
        self,
        entity: str,
        hvac_mode: str,
    ):
        if hvac_mode is None:
            return

        data = {ATTR_ENTITY_ID: entity, ATTR_HVAC_MODE: hvac_mode}
        await self._hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, data
        )

    async def _async_set_climate_temperature(
        self,
        entity: str,
        hvac_mode: str,
        min_temperature: Optional[float],
        max_temperature: Optional[float],
    ):
        if hvac_mode is None:
            return

        if min_temperature is None and max_temperature is None:
            return

        data = {ATTR_ENTITY_ID: entity}
        if hvac_mode == "heat":
            data[ATTR_TEMPERATURE] = min_temperature
        elif hvac_mode == "cool":
            data[ATTR_TEMPERATURE] = max_temperature
        elif hvac_mode == "heat_cool":
            data[ATTR_MIN_TEMP] = min_temperature
            data[ATTR_MAX_TEMP] = max_temperature

        await self._hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, data
        )

    async def _async_set_climate_fan_mode(self, entity: str, fan_mode: str):
        if fan_mode is None:
            return

        data = {ATTR_ENTITY_ID: entity, ATTR_FAN_MODE: fan_mode}
        await self._hass.services.async_call(CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE, data)

    async def _async_set_climate_swing_mode(self, entity: str, swing_mode: str):
        if swing_mode is None:
            return

        data = {ATTR_ENTITY_ID: entity, ATTR_SWING_MODE: swing_mode}
        await self._hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_SWING_MODE, data
        )


class ClimateSchedulerProfile:
    def __init__(self, config: dict) -> None:
        self._id: str = config.get(CONF_PROFILE_ID)
        self._name: str = config.get(CONF_PROFILE_NAME)

        self._default_hvac_mode = config.get(CONF_PROFILE_DEFAULT_HVAC_MODE)
        self._default_fan_mode = config.get(CONF_PROFILE_DEFAULT_FAN_MODE)
        self._default_swing_mode = config.get(CONF_PROFILE_DEFAULT_SWING_MODE)
        self._default_min_temp = config.get(CONF_PROFILE_DEFAULT_MIN_TEMP)
        self._default_max_temp = config.get(CONF_PROFILE_DEFAULT_MAX_TEMP)

        # TODO: Validate schedule time < 24h. Do in config validator?
        # TODO: Validate that no two schedules have same start time. Do in config validator?

        self._schedules = [
            ClimateShedulerSchedule(c) for c in config.get(CONF_PROFILE_SCHEDULE)
        ]
        self._schedules.sort(key=lambda x: x.time.total_seconds())

    def compute_climate(self, time_of_day: timedelta) -> ComputedClimateData:
        schedule = self._find_schedule(time_of_day)
        if schedule is None:
            return ComputedClimateData(
                self._default_hvac_mode,
                self._default_fan_mode,
                self._default_swing_mode,
                self._default_min_temp,
                self._default_max_temp,
            )

        # TODO: Replace None values with profile defaults if any
        return ComputedClimateData(
            schedule.hvac_mode if schedule.hvac_mode else self._default_hvac_mode,
            schedule.fan_mode if schedule.fan_mode else self._default_fan_mode,
            schedule.swing_mode if schedule.swing_mode else self._default_swing_mode,
            schedule.min_temp if schedule.min_temp else self._default_min_temp,
            schedule.max_temp if schedule.max_temp else self._default_max_temp,
        )

    def _find_schedule(self, time_of_day: timedelta) -> Optional[ComputedClimateData]:
        if len(self._schedules) == 0:
            return None

        if len(self._schedules) == 1:
            return self._schedules[0]

        # If the current time is earlier than the first schedule, wrap around and
        # return the last schedule of the day
        if time_of_day < self._schedules[0].time:
            return self._schedules[-1]

        for index, schedule in enumerate(self._schedules):
            # Search for a schedule starting earlier than the current time of day
            # which appears right before a schedule which starts later than the
            # current time of the day or which is the last schedule of the day.

            next_schedule = None
            if index < len(self._schedules) - 1:
                next_schedule = self._schedules[index + 1]

            if time_of_day >= schedule.time and (
                next_schedule is None or time_of_day < next_schedule.time
            ):
                return schedule

        return None


class ClimateShedulerSchedule:
    def __init__(self, config: dict) -> None:
        self._time: timedelta = config.get(CONF_SCHEDULE_TIME)
        self._hvac_mode: Optional[str] = config.get(CONF_SCHEDULE_HVAC)
        self._fan_mode: Optional[str] = config.get(CONF_SCHEDULE_FAN_MODE)
        self._swing_mode: Optional[str] = config.get(CONF_SCHEDULE_SWING_MODE)
        self._min_temp: Optional[int] = config.get(CONF_SCHEDULE_MIN_TEMP)
        self._max_temp: Optional[int] = config.get(CONF_SCHEDULE_MAX_TEMP)

    @property
    def time(self) -> timedelta:
        return self._time

    @property
    def hvac_mode(self) -> Optional[str]:
        return self._hvac_mode

    @property
    def fan_mode(self) -> Optional[str]:
        return self._fan_mode

    @property
    def swing_mode(self) -> Optional[str]:
        return self._swing_mode

    @property
    def min_temp(self) -> Optional[float]:
        return self._min_temp

    @property
    def max_temp(self) -> Optional[float]:
        return self._max_temp