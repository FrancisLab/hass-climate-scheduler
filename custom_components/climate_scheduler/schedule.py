"""Schedule class for Climate Scheduler."""

from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import HVAC_MODES

from .const import (
    CONF_SCHEDULE_FAN_MODE,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_MAX_TEMP,
    CONF_SCHEDULE_MIN_TEMP,
    CONF_SCHEDULE_SWING_MODE,
    CONF_SCHEDULE_TIME,
)
from .validation import less_than_24h

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


class ClimateSchedulerSchedule:
    """Representation of a single schedule entry."""

    def __init__(self, config: dict) -> None:
        """Initialize the schedule."""
        self._time: timedelta = config.get(CONF_SCHEDULE_TIME)
        self._hvac_mode: str | None = config.get(CONF_SCHEDULE_HVAC)
        self._fan_mode: str | None = config.get(CONF_SCHEDULE_FAN_MODE)
        self._swing_mode: str | None = config.get(CONF_SCHEDULE_SWING_MODE)
        self._min_temp: int | None = config.get(CONF_SCHEDULE_MIN_TEMP)
        self._max_temp: int | None = config.get(CONF_SCHEDULE_MAX_TEMP)

    @property
    def time(self) -> timedelta:
        """Return the time of the schedule."""
        return self._time

    @property
    def hvac_mode(self) -> str | None:
        """Return the hvac mode."""
        return self._hvac_mode

    @property
    def fan_mode(self) -> str | None:
        """Return the fan mode."""
        return self._fan_mode

    @property
    def swing_mode(self) -> str | None:
        """Return the swing mode."""
        return self._swing_mode

    @property
    def min_temp(self) -> float | None:
        """Return the min temp."""
        return self._min_temp

    @property
    def max_temp(self) -> float | None:
        """Return the max temp."""
        return self._max_temp
