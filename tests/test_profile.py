from datetime import timedelta

from custom_components.climate_scheduler.const import (
    CONF_PROFILE_DEFAULT_FAN_MODE,
    CONF_PROFILE_DEFAULT_HVAC_MODE,
    CONF_PROFILE_DEFAULT_MAX_TEMP,
    CONF_PROFILE_DEFAULT_MIN_TEMP,
    CONF_PROFILE_DEFAULT_SWING_MODE,
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_TIME,
)
from custom_components.climate_scheduler.profile import ClimateSchedulerProfile


def test_profile_no_schedule_uses_defaults():
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_DEFAULT_HVAC_MODE: "heat",
        CONF_PROFILE_DEFAULT_FAN_MODE: "auto",
        CONF_PROFILE_DEFAULT_SWING_MODE: "off",
        CONF_PROFILE_DEFAULT_MIN_TEMP: 20.0,
        CONF_PROFILE_DEFAULT_MAX_TEMP: 25.0,
        CONF_PROFILE_SCHEDULE: [],
    }
    profile = ClimateSchedulerProfile(config)
    data = profile.compute_climate(timedelta(hours=12))

    assert data.hvac_mode == "heat"
    assert data.fan_mode == "auto"
    assert data.swing_mode == "off"
    assert data.min_temp == 20.0
    assert data.max_temp == 25.0


def test_profile_schedules_sorted():
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=14), CONF_SCHEDULE_HVAC: "cool"},
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    # Access private _schedules to verify sort order directly or check behavior
    triggers = profile.get_trigger_times()
    assert triggers == [timedelta(hours=8), timedelta(hours=14)]


def test_profile_wraps_around_to_last_schedule():
    # If the current time is earlier than the very first schedule,
    # wrap around to last schedule of the day.
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            # First schedule
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
            # Last schedule
            {CONF_SCHEDULE_TIME: timedelta(hours=20), CONF_SCHEDULE_HVAC: "cool"},
        ],
    }
    profile = ClimateSchedulerProfile(config)

    # Time before first schedule (e.g., 6 AM)
    data = profile.compute_climate(timedelta(hours=6))
    # Should find the last schedule of the day (cool)
    assert data.hvac_mode == "cool"


def test_profile_finds_correct_schedule_mid_day():
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
            {CONF_SCHEDULE_TIME: timedelta(hours=20), CONF_SCHEDULE_HVAC: "cool"},
        ],
    }
    profile = ClimateSchedulerProfile(config)

    # Time between schedules (e.g., 12 PM)
    data = profile.compute_climate(timedelta(hours=12))
    assert data.hvac_mode == "heat"


def test_profile_matches_exact_start_time():
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
        ],
    }
    profile = ClimateSchedulerProfile(config)

    # Exactly 8 AM
    data = profile.compute_climate(timedelta(hours=8))
    assert data.hvac_mode == "heat"


def test_profile_only_one_schedule():
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
        ],
    }
    profile = ClimateSchedulerProfile(config)

    # Before
    assert profile.compute_climate(timedelta(hours=6)).hvac_mode == "heat"
    # After
    assert profile.compute_climate(timedelta(hours=12)).hvac_mode == "heat"


def test_profile_schedule_fallback_to_defaults():
    # Falling back to a schedule's default values if specific schedule entry omits them
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_DEFAULT_HVAC_MODE: "off",
        CONF_PROFILE_DEFAULT_FAN_MODE: "low",
        CONF_PROFILE_SCHEDULE: [
            {
                CONF_SCHEDULE_TIME: timedelta(hours=8),
                # Only HVAC provided, others should fallback
                CONF_SCHEDULE_HVAC: "heat",
            }
        ],
    }
    profile = ClimateSchedulerProfile(config)

    data = profile.compute_climate(timedelta(hours=10))
    assert data.hvac_mode == "heat"
    assert data.fan_mode == "low"  # fallback
