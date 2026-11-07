from datetime import timedelta
from unittest.mock import MagicMock

import pytest

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


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.states = MagicMock()
    return hass


def test_profile_no_schedule_uses_defaults(mock_hass):
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
    profile.refresh(mock_hass)
    data = profile.compute_climate(timedelta(hours=12))

    assert data.hvac_mode == "heat"
    assert data.fan_mode == "auto"
    assert data.swing_mode == "off"
    assert data.min_temp == 20.0
    assert data.max_temp == 25.0


def test_profile_schedules_sorted(mock_hass):
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=14), CONF_SCHEDULE_HVAC: "cool"},
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)
    triggers = profile.get_trigger_times()
    assert triggers == [timedelta(hours=8), timedelta(hours=14)]


def test_profile_wraps_around_to_last_schedule(mock_hass):
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
    profile.refresh(mock_hass)

    # Time before first schedule (e.g., 6 AM)
    data = profile.compute_climate(timedelta(hours=6))
    # Should find the last schedule of the day (cool)
    assert data.hvac_mode == "cool"


def test_profile_finds_correct_schedule_mid_day(mock_hass):
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
            {CONF_SCHEDULE_TIME: timedelta(hours=20), CONF_SCHEDULE_HVAC: "cool"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)

    # Time between schedules (e.g., 12 PM)
    data = profile.compute_climate(timedelta(hours=12))
    assert data.hvac_mode == "heat"


def test_profile_matches_exact_start_time(mock_hass):
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)

    # Exactly 8 AM
    data = profile.compute_climate(timedelta(hours=8))
    assert data.hvac_mode == "heat"


def test_profile_only_one_schedule(mock_hass):
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)

    # Before
    assert profile.compute_climate(timedelta(hours=6)).hvac_mode == "heat"
    # After
    assert profile.compute_climate(timedelta(hours=12)).hvac_mode == "heat"


def test_profile_schedule_fallback_to_defaults(mock_hass):
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
    profile.refresh(mock_hass)

    data = profile.compute_climate(timedelta(hours=10))
    assert data.hvac_mode == "heat"
    assert data.fan_mode == "low"  # fallback


def test_profile_dynamic_time_resolution(mock_hass):
    """Test that dynamic schedules are resolved correctly."""
    mock_hass.states.get.return_value.state = "10:00:00"

    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_HVAC: "dynamic"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)

    triggers = profile.get_trigger_times()
    assert triggers == [timedelta(hours=10)]

    data = profile.compute_climate(timedelta(hours=10, minutes=1))
    assert data.hvac_mode == "dynamic"


def test_profile_dynamic_time_changing(mock_hass):
    """Test that schedule order updates when entity time changes."""
    mock_hass.states.get.return_value.state = "10:00:00"

    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=12), CONF_SCHEDULE_HVAC: "static"},
            {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_HVAC: "dynamic"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)

    # Initial state: dynamic (10:00) < static (12:00)
    assert profile.get_trigger_times() == [timedelta(hours=10), timedelta(hours=12)]

    # Change entity time to 13:00 -> static (12:00) < dynamic (13:00)
    mock_hass.states.get.return_value.state = "13:00:00"
    profile.refresh(mock_hass)
    assert profile.get_trigger_times() == [timedelta(hours=12), timedelta(hours=13)]


def test_profile_mixed_static_dynamic_input(mock_hass):
    """Test mixed input types interaction and wrapping."""
    mock_hass.states.get.return_value.state = "13:00:00"

    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=12), CONF_SCHEDULE_HVAC: "static"},
            {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_HVAC: "dynamic"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)

    # List is [12:00 (static), 13:00 (dynamic)]

    # At 11:00 (before first), should wrap to last (dynamic)
    data_wrap = profile.compute_climate(timedelta(hours=11))
    assert data_wrap.hvac_mode == "dynamic"

    # At 12:30 (between), should be static
    data_mid = profile.compute_climate(timedelta(hours=12, minutes=30))
    assert data_mid.hvac_mode == "static"


def test_profile_collision_handling(mock_hass, caplog):
    """Test that collisions are detected and the last schedule is used."""
    import logging

    mock_hass.states.get.return_value.state = "10:00:00"
    config = {
        CONF_PROFILE_ID: "test_collision",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=10), CONF_SCHEDULE_HVAC: "first"},
            # Same time collision, only detectable once the entity is resolved
            {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_HVAC: "second"},
        ],
    }

    profile = ClimateSchedulerProfile(config)

    with caplog.at_level(logging.WARNING):
        profile.refresh(mock_hass)

    # Check if collision warning was logged
    assert "Collision detected" in caplog.text

    # The sort is stable, so the last defined schedule wins for equal times
    data = profile.compute_climate(timedelta(hours=10))
    assert data.hvac_mode == "second"


def test_profile_collision_logged_on_refresh_only(mock_hass, caplog):
    """Test that computing climate doesn't re-resolve schedules or repeat warnings."""
    import logging

    mock_hass.states.get.return_value.state = "10:00:00"
    config = {
        CONF_PROFILE_ID: "test_collision",
        CONF_PROFILE_SCHEDULE: [
            {CONF_SCHEDULE_TIME: timedelta(hours=10), CONF_SCHEDULE_HVAC: "first"},
            {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_HVAC: "second"},
        ],
    }
    profile = ClimateSchedulerProfile(config)
    profile.refresh(mock_hass)
    mock_hass.states.get.reset_mock()
    caplog.clear()

    with caplog.at_level(logging.WARNING):
        profile.compute_climate(timedelta(hours=11))
        profile.get_trigger_times()

    assert "Collision detected" not in caplog.text
    mock_hass.states.get.assert_not_called()


def test_profile_not_refreshed_uses_defaults():
    """Test that an unrefreshed profile has no resolved schedules."""
    config = {
        CONF_PROFILE_ID: "test",
        CONF_PROFILE_DEFAULT_HVAC_MODE: "off",
        CONF_PROFILE_SCHEDULE: [{CONF_SCHEDULE_TIME: timedelta(hours=8), CONF_SCHEDULE_HVAC: "heat"}],
    }
    profile = ClimateSchedulerProfile(config)

    assert profile.get_trigger_times() == []
    assert profile.compute_climate(timedelta(hours=9)).hvac_mode == "off"
