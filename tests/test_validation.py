from datetime import timedelta

import pytest
import voluptuous as vol
from homeassistant.components.climate import HVACMode

from custom_components.climate_scheduler.const import (
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_MIN_TEMP,
    CONF_SCHEDULE_TIME,
)
from custom_components.climate_scheduler.validation import (
    PROFILES_SCHEMA,
    SCHEDULE_SCHEMA,
    less_than_24h,
    unique_profiles,
    unique_schedule_times,
)


def test_less_than_24h_valid():
    assert less_than_24h(timedelta(hours=23, minutes=59)) == timedelta(
        hours=23, minutes=59
    )
    assert less_than_24h(timedelta(hours=0)) == timedelta(hours=0)


def test_less_than_24h_invalid():
    with pytest.raises(vol.Invalid):
        less_than_24h(timedelta(hours=24))
    with pytest.raises(vol.Invalid):
        less_than_24h(timedelta(hours=25))


def test_unique_profiles_valid():
    profiles = [
        {CONF_PROFILE_ID: "p1"},
        {CONF_PROFILE_ID: "p2"},
    ]
    assert unique_profiles(profiles) == profiles


def test_unique_profiles_invalid():
    profiles = [
        {CONF_PROFILE_ID: "p1"},
        {CONF_PROFILE_ID: "p1"},
    ]
    with pytest.raises(vol.Invalid):
        unique_profiles(profiles)


def test_unique_schedule_times_valid():
    schedules = [
        {CONF_SCHEDULE_TIME: timedelta(hours=1)},
        {CONF_SCHEDULE_TIME: timedelta(hours=2)},
    ]
    assert unique_schedule_times(schedules) == schedules


def test_unique_schedule_times_invalid():
    schedules = [
        {CONF_SCHEDULE_TIME: timedelta(hours=1)},
        {CONF_SCHEDULE_TIME: timedelta(hours=1)},
    ]
    with pytest.raises(vol.Invalid):
        unique_schedule_times(schedules)


def test_schedule_schema_valid():
    schedule = {
        CONF_SCHEDULE_TIME: timedelta(hours=1),
        CONF_SCHEDULE_HVAC: HVACMode.HEAT,
        CONF_SCHEDULE_MIN_TEMP: 20,
    }
    assert SCHEDULE_SCHEMA([schedule]) == [schedule]


def test_profiles_schema_valid():
    profile = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=1), CONF_SCHEDULE_HVAC: HVACMode.HEAT}
        ],
    }
    assert PROFILES_SCHEMA([profile]) == [profile]


def test_profiles_schema_empty_schedule():
    profile = {
        CONF_PROFILE_ID: "test",
        # Default empty schedule
    }
    validated = PROFILES_SCHEMA([profile])
    assert validated[0][CONF_PROFILE_SCHEDULE] == []
