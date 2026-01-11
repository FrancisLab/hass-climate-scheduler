"""Validation logic for Climate Scheduler."""

from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import HVAC_MODES

from .const import (
    CONF_PROFILE_DEFAULT_FAN_MODE,
    CONF_PROFILE_DEFAULT_HVAC_MODE,
    CONF_PROFILE_DEFAULT_MAX_TEMP,
    CONF_PROFILE_DEFAULT_MIN_TEMP,
    CONF_PROFILE_DEFAULT_SWING_MODE,
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
    CONF_SCHEDULE_FAN_MODE,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_MAX_TEMP,
    CONF_SCHEDULE_MIN_TEMP,
    CONF_SCHEDULE_SWING_MODE,
    CONF_SCHEDULE_TIME,
)


def less_than_24h(delta: timedelta) -> timedelta:
    """Validate that a duration is less than 24 hours."""
    if delta.total_seconds() >= 24 * 60 * 60:
        raise vol.Invalid("Schedule time must be less than 24h")
    return delta


def unique_profiles(profiles: dict) -> dict:
    """Validate that profile IDs are unique."""
    names = [p.get(CONF_PROFILE_ID) for p in profiles]
    if len(names) != len(set(names)):
        raise vol.Invalid("Profile names must be unique within scheduler")
    return profiles


def unique_schedule_times(schedules: dict) -> dict:
    """Validate that schedule times are unique within a profile."""
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
