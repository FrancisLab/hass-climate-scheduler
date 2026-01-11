"""Profile class for Climate Scheduler."""

from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import HVAC_MODES

from .common import ComputedClimateData
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

        self._schedules = [
            ClimateSchedulerSchedule(c) for c in config.get(CONF_PROFILE_SCHEDULE)
        ]
        self._schedules.sort(key=lambda x: x.time.total_seconds())

    @property
    def profile_id(self) -> str:
        """Return the profile ID."""
        return self._id

    def compute_climate(self, time_of_day: timedelta) -> ComputedClimateData:
        """Compute the climate settings for a specific time of day."""
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

    def get_trigger_times(self) -> list[timedelta]:
        """Return a list of times when the schedule changes."""
        return [s.time for s in self._schedules]

    def _find_schedule(self, time_of_day: timedelta) -> ClimateSchedulerSchedule | None:
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
