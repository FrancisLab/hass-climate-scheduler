"""Validation logic for Climate Scheduler."""

from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import CONF_PROFILE_ID, CONF_SCHEDULE_TIME


def valid_time_or_entity(value):
    """Validate that value is a time period or an entity ID."""
    try:
        return cv.positive_time_period(value)
    except vol.Invalid:
        pass

    return cv.entity_id(value)


def valid_offset(value):
    """Validate that value is a time offset (can be negative, max +/- 24h)."""
    offset = cv.time_period(value)
    if abs(offset.total_seconds()) > 86400:
        raise vol.Invalid("Offset cannot exceed 24 hours")
    return offset


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
    times = [s.get(CONF_SCHEDULE_TIME) for s in schedules]
    if (len(times)) != len(set(times)):
        raise vol.Invalid("Schedule times must be unique within a profile")
    return schedules
