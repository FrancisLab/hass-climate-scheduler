"""
Climate Schduler Switch for Home-Assistant.
"""

import asyncio
import logging
from collections.abc import Callable, Iterable
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.input_select import (
    CONF_INITIAL,
    CONF_OPTIONS,
    InputSelect,
)
from homeassistant.components.input_select import DOMAIN as INPUT_SELECT_DOMAIN
from homeassistant.components.switch import SwitchEntity
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import EntityPlatform, async_get_platforms
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify
from homeassistant.util.dt import now

from . import (
    DATA_CLIMATE_SCHEDULER,
    ClimateScheduler,
)
from .common import ComputedClimateData
from .const import (
    ATTR_PROFILE,
    ATTR_PROFILE_OPTIONS,
    CONF_CLIMATE_ENTITIES,
    CONF_DEFAULT_PROFILE,
    CONF_DEFAULT_STATE,
    CONF_PROFILE_ID,
    CONF_PROFILES,
    ICON,
)
from .profile import ClimateSchedulerProfile
from .validation import PROFILES_SCHEMA, unique_profiles

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

        _LOGGER.info(f"Initializing Climate Scheduler switch {self.entity_id}")
        self._climate_entities: list[str] = config.get(CONF_CLIMATE_ENTITIES)

        # Setup state
        self._state: str | None = None
        self._default_state: str | None = (
            STATE_ON if config.get(CONF_DEFAULT_STATE) else STATE_OFF
        )

        # Setup profiles
        self._profiles: dict[str, ClimateSchedulerProfile] = {
            profile_conf[CONF_PROFILE_ID]: ClimateSchedulerProfile(profile_conf)
            for profile_conf in config.get(CONF_PROFILES)
        }

        # Setup default profile
        self._default_profile_id: str | None = config.get(CONF_DEFAULT_PROFILE)
        if self._default_profile_id not in self._profiles:
            _LOGGER.info(
                f"Ignoring invalid default profile id {self._default_profile_id}"
            )
            self._default_profile_id = None

        # Setup current profile
        self._current_profile: ClimateSchedulerProfile | None = None
        self._current_profile = self._profiles.get(
            # Using current_profile_id property will resolve the default profile for us
            self.current_profile_id
        )

        # Setup time trackers
        self._interval_tracker_remove_callbacks = async_track_time_interval(
            hass, self.async_update_climate, self._update_interval
        )
        self._schedule_tracker_remove_callbacks: list[Callable[[], None]] = []
        self._update_schedule_trackers()

        logging.info(f"Initialized Climate Scheduler switch {self.entity_id}")

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
    def profile_options(self) -> list[str]:
        return list(self._profiles.keys())

    @property
    def state(self) -> str | None:
        if self._state is None:
            return self._default_state or STATE_OFF
        return self._state

    @property
    def current_profile_id(self) -> str | None:
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
            logging.error("No input select platform, not adding selectors")
            return
        input_select_platform: EntityPlatform = platforms[0]

        selector_config = {
            CONF_ID: self.entity_id_suffix + "_profile_selector",
            CONF_NAME: self.name + " Climate Profile Selector",
            CONF_OPTIONS: self.profile_options,
            CONF_ICON: "mdi:mdiFormSelect ",
            CONF_INITIAL: self.current_profile_id,
        }

        self._profile_selector = InputSelect.from_yaml(selector_config)
        await input_select_platform.async_add_entities([self._profile_selector])

        # Subscribe for profile changes
        self._profile_tracker_remover = async_track_state_change_event(
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

    async def _async_on_profile_selector_change(self, event) -> None:
        """Invoked when a different profile has been chosen via input select"""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        _LOGGER.info(f"Profile selector changed to {new_state.state}")
        await self._async_update_profile(new_state.state)

    async def _async_update_profile(self, new_profile_id: str) -> None:
        if new_profile_id not in self._profiles:
            logging.warning(f"Ignoring invalid profile with id={new_profile_id}")
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
        _LOGGER.info(self.entity_id + ": Turn on")

        self._state = STATE_ON
        await self.async_update_climate()
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        _LOGGER.info(self.entity_id + ": Turn off")

        self._state = STATE_OFF
        self.async_schedule_update_ha_state()

    async def async_update_climate(self, *args, **kwargs) -> None:
        """Update all climate entities controlled by the swtich"""
        _LOGGER.info(self.entity_id + ": Updating climate")

        if not self.is_on:
            _LOGGER.info(self.entity_id + ": Disabled")
            return

        if self._current_profile is None:
            _LOGGER.info(self.entity_id + ": No profile")
            return

        # TODO: Track temperature of entities. Only heat/cool if under/above threshold
        # TODO: Allow specifying a desired idle mode (e.g. fan-only for allergies,
        # forest fire, etc.)

        dt = now()
        time_of_day = timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second)
        climate_data = self._current_profile.compute_climate(time_of_day)

        update_tasks = [
            asyncio.create_task(self._async_update_climate_entity(entity, climate_data))
            for entity in self._climate_entities
        ]
        await asyncio.gather(*update_tasks)

    async def _async_update_climate_entity(
        self, entity: str, data: ComputedClimateData | None
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
            _LOGGER.info(self.entity_id + ": No HVAC mode")
            return

        data = {ATTR_ENTITY_ID: entity, ATTR_HVAC_MODE: hvac_mode}
        await self._hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, data
        )

    async def _async_set_climate_temperature(
        self,
        entity: str,
        hvac_mode: str,
        min_temperature: float | None,
        max_temperature: float | None,
    ):
        if hvac_mode is None:
            return

        if min_temperature is None and max_temperature is None:
            return

        # TODO: Validation could be more robust here
        data = {ATTR_ENTITY_ID: entity, ATTR_HVAC_MODE: hvac_mode}
        if hvac_mode == "heat":
            data[ATTR_TEMPERATURE] = min_temperature
        elif hvac_mode == "cool":
            data[ATTR_TEMPERATURE] = max_temperature
        elif hvac_mode == "heat_cool":
            data[ATTR_TARGET_TEMP_LOW] = min_temperature
            data[ATTR_TARGET_TEMP_HIGH] = max_temperature

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
