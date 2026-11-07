"""Validation logic for Climate Scheduler."""

from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import CONF_PROFILE_ID, CONF_SCHEDULE_OFFSET, CONF_SCHEDULE_TIME, TIME_ENTITY_DOMAINS


def wrap_to_day(delta: timedelta) -> timedelta:
    """Wrap a time of day around midnight. Schedules trigger on whole seconds, so drop any fraction."""
    wrapped = delta % timedelta(days=1)
    return wrapped - timedelta(microseconds=wrapped.microseconds)


def valid_time_or_entity(value):
    """Validate that value is a time of day under 24h or the ID of a time entity."""
    try:
        return less_than_24h(cv.positive_time_period(value))
    except vol.Invalid:
        pass

    try:
        return vol.All(cv.entity_id, cv.entity_domain(TIME_ENTITY_DOMAINS))(value)
    except vol.Invalid as err:
        domains = " or ".join(TIME_ENTITY_DOMAINS)
        raise vol.Invalid(f"Expected a time (HH:MM:SS) under 24h or an {domains} entity ID, got {value}") from err


def valid_offset(value):
    """Validate that value is a time offset (can be negative, less than +/- 24h)."""
    offset = cv.time_period(value)
    if abs(offset) >= timedelta(days=1):
        raise vol.Invalid("Offset must be less than 24 hours")
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
    """Validate that schedule times are unique within a profile.

    Static times are compared once their offset is applied. Entity times are only known at runtime, so they are
    compared by entity and offset, wrapped like resolved times.
    """
    times = []
    for s in schedules:
        time = s.get(CONF_SCHEDULE_TIME)
        offset = s.get(CONF_SCHEDULE_OFFSET, timedelta(0))
        if isinstance(time, timedelta):
            times.append(wrap_to_day(time + offset))
        else:
            times.append((time, wrap_to_day(offset)))

    if (len(times)) != len(set(times)):
        raise vol.Invalid("Schedule times must be unique within a profile")
    return schedules
