"""Profile class for Climate Scheduler."""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import HVAC_MODES
from homeassistant.core import HomeAssistant

from .common import ComputedClimateData, ResolvedScheduleEntry
from .const import (
    CONF_PROFILE_DEFAULT_FAN_MODE,
    CONF_PROFILE_DEFAULT_HVAC_MODE,
    CONF_PROFILE_DEFAULT_MAX_TEMP,
    CONF_PROFILE_DEFAULT_MIN_TEMP,
    CONF_PROFILE_DEFAULT_SWING_MODE,
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
)
from .schedule import SCHEDULE_SCHEMA, ClimateSchedulerSchedule
from .validation import unique_schedule_times

_LOGGER = logging.getLogger(__name__)

PROFILES_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_PROFILE_ID): vol.All(cv.string),
            vol.Optional(CONF_PROFILE_SCHEDULE, default=[]): vol.All(SCHEDULE_SCHEMA, unique_schedule_times),
            vol.Optional(CONF_PROFILE_DEFAULT_HVAC_MODE): vol.All(cv.string, vol.In(HVAC_MODES)),
            vol.Optional(CONF_PROFILE_DEFAULT_FAN_MODE): cv.string,
            vol.Optional(CONF_PROFILE_DEFAULT_SWING_MODE): cv.string,
            vol.Optional(CONF_PROFILE_DEFAULT_MIN_TEMP): vol.Coerce(float),
            vol.Optional(CONF_PROFILE_DEFAULT_MAX_TEMP): vol.Coerce(float),
        }
    ]
)


class ClimateSchedulerProfile:
    """Representation of a profile."""

    def __init__(self, config: dict) -> None:
        """Initialize the profile."""
        self._id: str = config.get(CONF_PROFILE_ID)

        self._default_hvac_mode = config.get(CONF_PROFILE_DEFAULT_HVAC_MODE)
        self._default_fan_mode = config.get(CONF_PROFILE_DEFAULT_FAN_MODE)
        self._default_swing_mode = config.get(CONF_PROFILE_DEFAULT_SWING_MODE)
        self._default_min_temp = config.get(CONF_PROFILE_DEFAULT_MIN_TEMP)
        self._default_max_temp = config.get(CONF_PROFILE_DEFAULT_MAX_TEMP)

        self._schedules = [ClimateSchedulerSchedule(c) for c in config.get(CONF_PROFILE_SCHEDULE)]

    @property
    def profile_id(self) -> str:
        """Return the profile ID."""
        return self._id

    def get_time_entities(self) -> set[str]:
        """Return a set of entity IDs used in this profile's schedules."""
        entities = set()
        for schedule in self._schedules:
            if schedule.entity_id:
                entities.add(schedule.entity_id)
        return entities

    def compute_climate(self, time_of_day: timedelta, hass: HomeAssistant) -> ComputedClimateData:
        """Compute the climate settings for a specific time of day."""
        resolved_schedules = self._resolve_schedules(hass)
        schedule = self._find_schedule(time_of_day, resolved_schedules)

        _LOGGER.debug(
            "Computed climate for profile %s at %s. Using schedule: %s",
            self._id,
            time_of_day,
            schedule,
        )

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

    def get_trigger_times(self, hass: HomeAssistant) -> list[timedelta]:
        """Return a list of times when the schedule changes."""
        # Use a dict to deduplicate times, then return sorted list
        # or just set
        resolved = self._resolve_schedules(hass)
        return sorted(list({entry.time for entry in resolved}))

    def _resolve_schedules(self, hass: HomeAssistant) -> list[ResolvedScheduleEntry]:
        """Resolve all schedules to static times and sort them."""
        resolved_entries = []
        for schedule in self._schedules:
            time = schedule.resolve_time(hass)
            if time is not None:
                resolved_entries.append(ResolvedScheduleEntry(time, schedule))

        resolved_entries.sort(key=lambda x: x.time.total_seconds())

        # Check for collisions
        if len(resolved_entries) > 1:
            for i in range(len(resolved_entries) - 1):
                if resolved_entries[i].time == resolved_entries[i + 1].time:
                    _LOGGER.warning(
                        "Collision detected in profile %s for time %s. Using the last defined schedule.",
                        self._id,
                        resolved_entries[i].time,
                    )

        return resolved_entries

    def _find_schedule(
        self, time_of_day: timedelta, resolved_schedules: list[ResolvedScheduleEntry]
    ) -> ClimateSchedulerSchedule | None:
        if len(resolved_schedules) == 0:
            return None

        if len(resolved_schedules) == 1:
            return resolved_schedules[0].schedule

        # If the current time is earlier than the first schedule, wrap around and
        # return the last schedule of the day
        if time_of_day < resolved_schedules[0].time:
            return resolved_schedules[-1].schedule

        for index, entry in enumerate(resolved_schedules):
            schedule = entry.schedule
            schedule_time = entry.time

            next_entry = None
            if index < len(resolved_schedules) - 1:
                next_entry = resolved_schedules[index + 1]

            if time_of_day >= schedule_time and (next_entry is None or time_of_day < next_entry.time):
                return schedule

        return None
