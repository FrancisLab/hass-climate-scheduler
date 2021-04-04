"""
Climate Schduler Switch for Home-Assistant.
"""


import asyncio
from collections import namedtuple
from datetime import timedelta
from homeassistant.components.input_select import (
    CONF_INITIAL,
    CONF_OPTIONS,
    InputSelect,
)
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    HVAC_MODES,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
import logging
import voluptuous as vol
from typing import Iterable, List, Callable, Dict, Optional

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    ATTR_TEMPERATURE,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_SELECT_OPTION,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify
from homeassistant.util.dt import now
from homeassistant.helpers.entity_platform import EntityPlatform, async_get_platforms

from . import (
    ClimateScheduler,
    DATA_CLIMATE_SCHEDULER,
)

from homeassistant.components.input_select import DOMAIN as INPUT_SELECT_DOMAIN

ICON = "mdi:calendar-clock"

CONF_CLIMATE_ENTITIES = "climate_entities"
CONF_DEFAULT_STATE = "default_state"
CONF_DEFAULT_PROFILE = "default_profile"
CONF_PROFILES = "profiles"

CONF_PROFILE_ID = "id"
CONF_PROFILE_SCHEDULE = "schedule"
CONF_PROFILE_DEFAULT_HVAC_MODE = "default_hvac_mode"
CONF_PROFILE_DEFAULT_FAN_MODE = "default_fan_mode"
CONF_PROFILE_DEFAULT_SWING_MODE = "default_swing_mode"
CONF_PROFILE_DEFAULT_MIN_TEMP = "default_min_temp"
CONF_PROFILE_DEFAULT_MAX_TEMP = "default_max_temp"

CONF_SCHEDULE_TIME = "time"
CONF_SCHEDULE_HVAC = "hvac_mode"
CONF_SCHEDULE_MIN_TEMP = "min_temp"
CONF_SCHEDULE_MAX_TEMP = "max_temp"
CONF_SCHEDULE_FAN_MODE = "fan_mode"
CONF_SCHEDULE_SWING_MODE = "swing_mode"


def less_than_24h(delta: timedelta) -> timedelta:
    if delta.total_seconds() >= 24 * 60 * 60:
        raise vol.Invalid("Schedule time must be less than 24h")
    return delta


def unique_profiles(profiles: dict) -> dict:
    names = [p.get(CONF_PROFILE_ID) for p in profiles]
    if len(names) != len(set(names)):
        raise vol.Invalid("Profile names must be unique within scheduler")
    return profiles


def unique_schedule_times(schedules: dict) -> dict:
    times = [s.get(CONF_SCHEDULE_TIME).total_seconds() for s in schedules]
    if (len(times)) != len(set(times)):
        raise vol.Invalid("Schedule times must be unique within a profile")
    return schedules


SCHEDULE_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_SCHEDULE_TIME): vol.All(
                cv.positive_time_period,
                less_than_24h,
            ),
            vol.Optional(CONF_SCHEDULE_HVAC): vol.All(cv.string, vol.In(HVAC_MODES)),
            vol.Optional(CONF_SCHEDULE_MIN_TEMP): vol.Coerce(float),
            vol.Optional(CONF_SCHEDULE_MAX_TEMP): vol.Coerce(float),
            vol.Optional(CONF_SCHEDULE_FAN_MODE): cv.string,
            vol.Optional(CONF_SCHEDULE_SWING_MODE): cv.string,
        }
    ]
)

PROFILES_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_PROFILE_ID): vol.All(cv.string),
            vol.Optional(CONF_PROFILE_SCHEDULE, default=[]): vol.All(
                SCHEDULE_SCHEMA, unique_schedule_times
            ),
            vol.Optional(CONF_PROFILE_DEFAULT_HVAC_MODE): vol.All(
                cv.string, vol.In(HVAC_MODES)
            ),
            vol.Optional(CONF_PROFILE_DEFAULT_FAN_MODE): cv.string,
            vol.Optional(CONF_PROFILE_DEFAULT_SWING_MODE): cv.string,
            vol.Optional(CONF_PROFILE_DEFAULT_MIN_TEMP): vol.Coerce(float),
            vol.Optional(CONF_PROFILE_DEFAULT_MAX_TEMP): vol.Coerce(float),
        }
    ]
)

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "climate_scheduler",
        vol.Required(CONF_PROFILES): vol.All(
            PROFILES_SCHEMA, unique_profiles, vol.Length(min=1)
        ),
        vol.Optional(CONF_NAME, default="Climate Scheduler"): cv.string,
        vol.Optional(CONF_DEFAULT_STATE, default=False): cv.boolean,
        vol.Optional(CONF_DEFAULT_PROFILE): cv.string,
        vol.Optional(CONF_CLIMATE_ENTITIES): cv.entity_ids,
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


ComputedClimateData = namedtuple(
    "ComputedClimateData",
    ["hvac_mode", "fan_mode", "swing_mode", "min_temp", "max_temp"],
)


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


class ClimateSchedulerProfile:
    def __init__(self, config: dict) -> None:
        self._id: str = config.get(CONF_PROFILE_ID)

        self._default_hvac_mode = config.get(CONF_PROFILE_DEFAULT_HVAC_MODE)
        self._default_fan_mode = config.get(CONF_PROFILE_DEFAULT_FAN_MODE)
        self._default_swing_mode = config.get(CONF_PROFILE_DEFAULT_SWING_MODE)
        self._default_min_temp = config.get(CONF_PROFILE_DEFAULT_MIN_TEMP)
        self._default_max_temp = config.get(CONF_PROFILE_DEFAULT_MAX_TEMP)

        self._schedules = [
            ClimateShedulerSchedule(c) for c in config.get(CONF_PROFILE_SCHEDULE)
        ]
        self._schedules.sort(key=lambda x: x.time.total_seconds())

    @property
    def profile_id(self) -> str:
        return self._id

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

        return ComputedClimateData(
            schedule.hvac_mode if schedule.hvac_mode else self._default_hvac_mode,
            schedule.fan_mode if schedule.fan_mode else self._default_fan_mode,
            schedule.swing_mode if schedule.swing_mode else self._default_swing_mode,
            schedule.min_temp if schedule.min_temp else self._default_min_temp,
            schedule.max_temp if schedule.max_temp else self._default_max_temp,
        )

    def get_trigger_times(self) -> List[timedelta]:
        return [s.time for s in self._schedules]

    def _find_schedule(
        self, time_of_day: timedelta
    ) -> Optional[ClimateShedulerSchedule]:
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


ATTR_IS_ON = "is_on"
ATTR_PROFILE = "current_profile"
ATTR_PROFILE_OPTIONS = "profile_options"
# TODO: Add an "explanation string" attribute and property


class ClimateSchedulerSwitch(SwitchEntity, RestoreEntity):
    """Representation of a Climate Scheduler swith."""

    def __init__(self, hass: HomeAssistant, cs: ClimateScheduler, config: dict) -> None:
        """Initialize the Climate Scheduler swith."""
        self._hass = hass
        self._cs = cs

        # Global configs
        self._update_interval = self._cs._update_interval

        # Simple configs
        self._name: str = config.get(CONF_NAME)
        self._climate_entities: List[str] = config.get(CONF_CLIMATE_ENTITIES)

        # Setup state
        self._state: Optional[str] = None
        self._default_state: Optional[str] = (
            STATE_ON if config.get(CONF_DEFAULT_STATE) else STATE_OFF
        )

        # Setup profiles
        self._profiles: Dict[str, ClimateSchedulerProfile] = {
            profile_conf[CONF_PROFILE_ID]: ClimateSchedulerProfile(profile_conf)
            for profile_conf in config.get(CONF_PROFILES)
        }

        # Setup default profile
        self._default_profile_id: Optional[str] = config.get(CONF_DEFAULT_PROFILE)
        if self._default_profile_id not in self._profiles:
            logging.warn(
                "Ignoring invalid default profile id {}".format(
                    self._default_profile_id
                )
            )
            self._default_profile_id = None

        # Setup current profile
        self._current_profile: Optional[ClimateSchedulerProfile] = None
        self._current_profile = self._profiles.get(
            # Using current_profile_id property will resolve the default profile for us
            self.current_profile_id
        )

        # Setup time trackers
        self._interval_tracker_remove_callbacks = async_track_time_interval(
            hass, self.async_update_climate, self._update_interval
        )
        self._schedule_tracker_remove_callbacks: List[Callable[[], None]] = []
        self._update_schedule_trackers()

    @property
    def entity_id(self) -> str:
        return "switch." + self.entity_id_suffix

    @property
    def entity_id_suffix(self) -> str:
        return slugify("{} {}".format("climate_scheduler", self._name))

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool:
        return self._state == STATE_ON

    @property
    def icon(self) -> str:
        return ICON

    @property
    def profile_options(self) -> List[str]:
        return list(self._profiles.keys())

    @property
    def state(self) -> Optional[str]:
        if self._state is None:
            return self._default_state or STATE_OFF
        return self._state

    @property
    def current_profile_id(self) -> Optional[str]:
        if self._current_profile is None:
            return self._default_profile_id or list(self._profiles.keys())[0]
        return self._current_profile.profile_id

    @property
    def state_attributes(self):
        return {
            ATTR_PROFILE: self.current_profile_id,
            ATTR_PROFILE_OPTIONS: self.profile_options,
        }

    async def async_create_profile_selector(
        self,
    ) -> None:
        """Create input_select entity for picking profiles"""

        platforms = async_get_platforms(self._hass, INPUT_SELECT_DOMAIN)
        if len(platforms) == 0:
            logging.warn("No input select platform, not adding selectors")
            return
        input_select_platform: EntityPlatform = platforms[0]

        selector_config = {
            CONF_ID: "input_select." + self.entity_id_suffix + "_profile_selector",
            CONF_NAME: self.name + " Climate Profile Selector",
            CONF_OPTIONS: self.profile_options,
            CONF_ICON: "mdi:mdiFormSelect ",
            CONF_INITIAL: self.current_profile_id,
        }

        self._profile_selector = InputSelect(selector_config)
        await input_select_platform.async_add_entities([self._profile_selector])

        # Subscribe for profile changes
        self._profile_tracker_remover = async_track_state_change(
            self._hass,
            [self._profile_selector.entity_id],
            self._async_on_profile_selector_change,
        )

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass. Used to restore state."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._state is not None:
            return

        previous_state = await self.async_get_last_state()
        if previous_state is None:
            return

        previous_attributes = previous_state.attributes

        if previous_state.state:
            self._state = previous_state.state

        if ATTR_PROFILE in previous_attributes:
            await self._async_update_profile(previous_attributes[ATTR_PROFILE])
            await self._hass.services.async_call(
                INPUT_SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                {
                    ATTR_ENTITY_ID: self._profile_selector.entity_id,
                    ATTR_OPTION: self.current_profile_id,
                },
            )

        self.async_schedule_update_ha_state()

    async def _async_on_profile_selector_change(
        self, entity_id: str, old_state: State, new_state: State
    ) -> None:
        """Invoked when a different profile has been chosen via input select"""
        await self._async_update_profile(new_state.state)

    async def _async_update_profile(self, new_profile_id: str) -> None:
        if new_profile_id not in self._profiles:
            logging.warn("Ignoring invalid profile with id={}".format(new_profile_id))
            return

        self._current_profile = self._profiles.get(new_profile_id)

        self._update_schedule_trackers()
        await self.async_update_climate()

        self.async_schedule_update_ha_state()

    def _update_schedule_trackers(self):
        """Update time intervals and schedule times tracked by the scheduler"""
        if self._current_profile is None:
            return

        # Clear any previous schedule trackers
        for remove_callback in self._schedule_tracker_remove_callbacks:
            remove_callback()

        # Register new trackers
        self._schedule_tracker_remove_callbacks = []
        for schedule in self._current_profile.get_trigger_times():
            self._schedule_tracker_remove_callbacks.append(
                async_track_time_change(
                    self._hass,
                    self.async_update_climate,
                    hour=schedule.seconds // 3600,
                    minute=schedule.seconds // 60 % 60,
                    second=schedule.seconds % 60,
                )
            )

    async def async_turn_on(self, **kwargs) -> None:
        _LOGGER.debug(self.entity_id + ": Turn on")

        self._state = STATE_ON
        await self.async_update_climate()
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        _LOGGER.debug(self.entity_id + ": Turn off")

        self._state = STATE_OFF
        self.async_schedule_update_ha_state()

    async def async_update_climate(self, *args, **kwargs) -> None:
        """Update all climate entities controlled by the swtich"""
        _LOGGER.debug(self.entity_id + ": Updating climate")

        if not self.is_on:
            _LOGGER.debug(self.entity_id + ": Disabled")
            return

        if self._current_profile is None:
            _LOGGER.debug(self.entity_id + ": No profile")
            return

        # TODO: Track temperature of entities. Only heat/cool if under/above threshold
        # TODO: Allow specifying a desired idle mode (e.g. fan-only for allergies, forest fire, etc.)

        dt = now()
        time_of_day = timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second)
        climate_data = self._current_profile.compute_climate(time_of_day)

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
            entity, data.hvac_mode, data.min_temp, data.max_temp
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Callable[[Iterable[Entity], bool], None],
    discovery_info=None,
):
    """Set up the Climate Scheduler switches"""
    cs: ClimateScheduler = hass.data.get(DATA_CLIMATE_SCHEDULER)

    if cs is None:
        return False

    cs_switch = ClimateSchedulerSwitch(hass, cs, config)
    async_add_entities([cs_switch], True)

    await cs_switch.async_create_profile_selector()

    return True