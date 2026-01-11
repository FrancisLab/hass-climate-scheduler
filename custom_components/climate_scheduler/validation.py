"""Validation logic for Climate Scheduler."""

from datetime import timedelta

import voluptuous as vol

from .const import CONF_PROFILE_ID, CONF_SCHEDULE_TIME


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
