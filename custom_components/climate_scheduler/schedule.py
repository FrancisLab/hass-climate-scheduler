"""Schedule class for Climate Scheduler."""

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import HVAC_MODES
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
from .validation import valid_offset, valid_time_or_entity

_LOGGER = logging.getLogger(__name__)


SCHEDULE_SCHEMA = vol.Schema(
    [
        {
            vol.Required(CONF_SCHEDULE_TIME): vol.All(
                valid_time_or_entity,
            ),
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

    def __init__(self, config: dict, logger: logging.Logger = _LOGGER) -> None:
        """Initialize the schedule."""
        self._logger = logger
        self._static_time: timedelta | None = None
        self._time_entity_id: str | None = None
        self._offset: timedelta = timedelta(0)
        self._parse_time_config(config)

    def _parse_time_config(self, config: dict) -> None:
        """Parse time configuration."""
        time_val = config.get(CONF_SCHEDULE_TIME)
        if isinstance(time_val, timedelta):
            self._static_time = time_val
        else:
            self._time_entity_id = time_val

        self._offset = config.get(CONF_SCHEDULE_OFFSET, timedelta(0))

        self._hvac_mode: str | None = config.get(CONF_SCHEDULE_HVAC)
        self._fan_mode: str | None = config.get(CONF_SCHEDULE_FAN_MODE)
        self._swing_mode: str | None = config.get(CONF_SCHEDULE_SWING_MODE)
        self._min_temp: int | None = config.get(CONF_SCHEDULE_MIN_TEMP)
        self._max_temp: int | None = config.get(CONF_SCHEDULE_MAX_TEMP)

    @property
    def is_dynamic(self) -> bool:
        """Return True if the schedule time depends on an entity."""
        return self._time_entity_id is not None

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
        """Resolve the schedule time, accounting for entities and offsets."""
        base_time = self._static_time

        if self._time_entity_id:
            state = hass.states.get(self._time_entity_id)
            self._logger.debug(f"resolving {self._time_entity_id}, state found: {state}")
            if state is None:
                self._logger.warning("Entity %s not found for schedule", self._time_entity_id)
                return None

            # parse_time handles strings like "10:00:00"
            parsed = parse_time(state.state)
            if parsed is None:
                self._logger.warning("Invalid time state %s for entity %s", state.state, self._time_entity_id)
                return None

            base_time = timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)

        if base_time is None:
            return None

        # Apply offset
        final_time = base_time + self._offset

        # Handle wrap around (modulo 24h)
        total_seconds = final_time.total_seconds() % 86400
        return timedelta(seconds=total_seconds)

    def __str__(self) -> str:
        if self._time_entity_id:
            return f"Dynamic: {self._time_entity_id} + {self._offset}"
        return f"Static: {self._static_time} + {self._offset}"
