from datetime import timedelta

import pytest
import voluptuous as vol
from homeassistant.components.climate import HVACMode

from custom_components.climate_scheduler.const import (
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_MIN_TEMP,
    CONF_SCHEDULE_OFFSET,
    CONF_SCHEDULE_TIME,
)
from custom_components.climate_scheduler.profile import PROFILES_SCHEMA
from custom_components.climate_scheduler.schedule import SCHEDULE_SCHEMA
from custom_components.climate_scheduler.validation import (
    less_than_24h,
    unique_profiles,
    unique_schedule_times,
)


def test_less_than_24h_valid():
    assert less_than_24h(timedelta(hours=23, minutes=59)) == timedelta(hours=23, minutes=59)
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


def test_unique_schedule_times_same_entity_different_offsets():
    schedules = [
        {CONF_SCHEDULE_TIME: "input_datetime.sleep", CONF_SCHEDULE_OFFSET: timedelta(minutes=-30)},
        {CONF_SCHEDULE_TIME: "input_datetime.sleep"},
    ]
    assert unique_schedule_times(schedules) == schedules


def test_unique_schedule_times_same_entity_same_offset():
    schedules = [
        {CONF_SCHEDULE_TIME: "input_datetime.sleep", CONF_SCHEDULE_OFFSET: timedelta(minutes=-30)},
        {CONF_SCHEDULE_TIME: "input_datetime.sleep", CONF_SCHEDULE_OFFSET: timedelta(minutes=-30)},
    ]
    with pytest.raises(vol.Invalid):
        unique_schedule_times(schedules)


def test_unique_schedule_times_same_entity_offsets_wrapping_to_same_time():
    schedules = [
        {CONF_SCHEDULE_TIME: "input_datetime.sleep", CONF_SCHEDULE_OFFSET: timedelta(hours=-1)},
        {CONF_SCHEDULE_TIME: "input_datetime.sleep", CONF_SCHEDULE_OFFSET: timedelta(hours=23)},
    ]
    with pytest.raises(vol.Invalid):
        unique_schedule_times(schedules)


def test_unique_schedule_times_compared_on_whole_seconds():
    schedules = [
        {CONF_SCHEDULE_TIME: "input_datetime.sleep", CONF_SCHEDULE_OFFSET: timedelta(seconds=0.5)},
        {CONF_SCHEDULE_TIME: "input_datetime.sleep"},
    ]
    with pytest.raises(vol.Invalid):
        unique_schedule_times(schedules)


def test_unique_schedule_times_static_compared_with_offset():
    schedules = [
        {CONF_SCHEDULE_TIME: timedelta(hours=8)},
        {CONF_SCHEDULE_TIME: timedelta(hours=7), CONF_SCHEDULE_OFFSET: timedelta(hours=1)},
    ]
    with pytest.raises(vol.Invalid):
        unique_schedule_times(schedules)


@pytest.mark.parametrize("time", ["24:00:00", "25:00:00"])
def test_schedule_schema_rejects_times_over_24h(time):
    with pytest.raises(vol.Invalid):
        SCHEDULE_SCHEMA([{CONF_SCHEDULE_TIME: time}])


@pytest.mark.parametrize("entity_id", ["input_datetime.wake_up", "time.alarm"])
def test_schedule_schema_accepts_time_entities(entity_id):
    assert SCHEDULE_SCHEMA([{CONF_SCHEDULE_TIME: entity_id}])[0][CONF_SCHEDULE_TIME] == entity_id


@pytest.mark.parametrize("value", ["sensor.wake_up", "7:0o:00"])
def test_schedule_schema_rejects_other_values(value):
    with pytest.raises(vol.Invalid, match="Expected a time"):
        SCHEDULE_SCHEMA([{CONF_SCHEDULE_TIME: value}])


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
        CONF_PROFILE_SCHEDULE: [{CONF_SCHEDULE_TIME: timedelta(hours=1), CONF_SCHEDULE_HVAC: HVACMode.HEAT}],
    }
    assert PROFILES_SCHEMA([profile]) == [profile]


def test_profiles_schema_empty_schedule():
    profile = {
        CONF_PROFILE_ID: "test",
        # Default empty schedule
    }
    validated = PROFILES_SCHEMA([profile])
    assert validated[0][CONF_PROFILE_SCHEDULE] == []
