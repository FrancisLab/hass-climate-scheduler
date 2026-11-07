"""Schedule class for Climate Scheduler."""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import HVAC_MODES
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import parse_time

from .const import (
    CONF_SCHEDULE_FAN_MODE,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_MAX_TEMP,
    CONF_SCHEDULE_MIN_TEMP,
    CONF_SCHEDULE_OFFSET,
    CONF_SCHEDULE_SWING_MODE,
    CONF_SCHEDULE_TIME,
)
from .validation import valid_offset, valid_time_or_entity, wrap_to_day

_LOGGER = logging.getLogger(__name__)


SCHEDULE_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_SCHEDULE_TIME): valid_time_or_entity,
            vol.Optional(CONF_SCHEDULE_OFFSET): valid_offset,
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

    def __init__(self, config: dict, logger: logging.Logger | logging.LoggerAdapter = _LOGGER) -> None:
        """Initialize the schedule."""
        self._logger = logger

        # Time is either static or read from an entity
        time_val = config.get(CONF_SCHEDULE_TIME)
        self._static_time: timedelta | None = time_val if isinstance(time_val, timedelta) else None
        self._time_entity_id: str | None = None if isinstance(time_val, timedelta) else time_val
        self._last_entity_time: timedelta | None = None
        self._offset: timedelta = config.get(CONF_SCHEDULE_OFFSET, timedelta(0))

        self._hvac_mode: str | None = config.get(CONF_SCHEDULE_HVAC)
        self._fan_mode: str | None = config.get(CONF_SCHEDULE_FAN_MODE)
        self._swing_mode: str | None = config.get(CONF_SCHEDULE_SWING_MODE)
        self._min_temp: int | None = config.get(CONF_SCHEDULE_MIN_TEMP)
        self._max_temp: int | None = config.get(CONF_SCHEDULE_MAX_TEMP)

    @property
    def entity_id(self) -> str | None:
        """Return the entity ID if dynamic."""
        return self._time_entity_id

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

    def resolve_time(self, hass: HomeAssistant) -> timedelta | None:
        """Resolve the schedule time, accounting for entities and offsets.

        If the time entity can't be read, fall back to the last time it resolved to, so that a briefly unavailable
        entity doesn't drop the schedule.
        """
        base_time = self._static_time

        if self._time_entity_id:
            base_time = self._read_entity_time(hass)
            if base_time is not None:
                self._last_entity_time = base_time
            elif self._last_entity_time is not None:
                self._logger.warning(
                    "Using last known time %s for entity %s", self._last_entity_time, self._time_entity_id
                )
                base_time = self._last_entity_time

        if base_time is None:
            return None

        return wrap_to_day(base_time + self._offset)

    def _read_entity_time(self, hass: HomeAssistant) -> timedelta | None:
        """Read the time of day from the time entity."""
        state = hass.states.get(self._time_entity_id)
        self._logger.debug("Resolving %s, state found: %s", self._time_entity_id, state)
        if state is None:
            self._logger.warning("Entity %s not found for schedule", self._time_entity_id)
            return None

        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._logger.warning("Entity %s is %s", self._time_entity_id, state.state)
            return None

        # input_datetime exposes its time as attributes, which also covers helpers that have a date
        if "hour" in state.attributes:
            return timedelta(
                hours=state.attributes["hour"],
                minutes=state.attributes.get("minute", 0),
                seconds=state.attributes.get("second", 0),
            )

        if state.attributes.get("has_time") is False:
            self._logger.warning("Entity %s has no time, only a date", self._time_entity_id)
            return None

        # time entities have a "HH:MM:SS" state
        parsed = parse_time(state.state)
        if parsed is None:
            self._logger.warning("Invalid time state %s for entity %s", state.state, self._time_entity_id)
            return None

        return timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)

    def __str__(self) -> str:
        # timedelta prints negative values as "-1 day, 23:30:00", so print the sign separately
        sign = "-" if self._offset < timedelta(0) else "+"
        if self._time_entity_id:
            return f"Dynamic: {self._time_entity_id} {sign} {abs(self._offset)}"
        return f"Static: {self._static_time} {sign} {abs(self._offset)}"
