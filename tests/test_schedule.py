"""Test schedule time resolution."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.climate_scheduler.const import (
    CONF_SCHEDULE_OFFSET,
    CONF_SCHEDULE_TIME,
)
from custom_components.climate_scheduler.schedule import ClimateSchedulerSchedule


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.states = MagicMock()
    return hass


def test_static_time_resolution(mock_hass):
    config = {CONF_SCHEDULE_TIME: timedelta(hours=10)}
    schedule = ClimateSchedulerSchedule(config)
    assert schedule.entity_id is None

    resolved = schedule.resolve_time(mock_hass)
    assert resolved == timedelta(hours=10)


def test_entity_time_resolution(mock_hass):
    mock_hass.states.get.return_value.state = "10:30:00"
    config = {CONF_SCHEDULE_TIME: "input_datetime.test"}
    schedule = ClimateSchedulerSchedule(config)
    assert schedule.entity_id == "input_datetime.test"

    resolved = schedule.resolve_time(mock_hass)
    assert resolved == timedelta(hours=10, minutes=30)
    mock_hass.states.get.assert_called_with("input_datetime.test")


def test_entity_resolution_with_offset(mock_hass):
    mock_hass.states.get.return_value.state = "10:00:00"
    config = {
        CONF_SCHEDULE_TIME: "input_datetime.test",
        # -30 minutes
        CONF_SCHEDULE_OFFSET: timedelta(minutes=-30),
    }
    schedule = ClimateSchedulerSchedule(config)

    resolved = schedule.resolve_time(mock_hass)
    assert resolved == timedelta(hours=9, minutes=30)


def test_offset_wrapping(mock_hass):
    mock_hass.states.get.return_value.state = "00:10:00"
    config = {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_OFFSET: timedelta(minutes=-20)}
    schedule = ClimateSchedulerSchedule(config)

    resolved = schedule.resolve_time(mock_hass)
    # Should wrap to previous day: 23:50
    assert resolved == timedelta(hours=23, minutes=50)


def test_fractional_offset_truncated_to_whole_seconds(mock_hass):
    mock_hass.states.get.return_value.state = "07:00:00"
    config = {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_OFFSET: timedelta(seconds=0.5)}
    schedule = ClimateSchedulerSchedule(config)

    assert schedule.resolve_time(mock_hass) == timedelta(hours=7)


def test_missing_entity_returns_none(mock_hass):
    mock_hass.states.get.return_value = None
    config = {CONF_SCHEDULE_TIME: "input_datetime.missing"}
    schedule = ClimateSchedulerSchedule(config)

    resolved = schedule.resolve_time(mock_hass)
    assert resolved is None


def test_invalid_entity_state_returns_none(mock_hass):
    mock_hass.states.get.return_value.state = "invalid"
    config = {CONF_SCHEDULE_TIME: "input_datetime.invalid"}
    schedule = ClimateSchedulerSchedule(config)

    resolved = schedule.resolve_time(mock_hass)
    assert resolved is None


def test_input_datetime_with_date_uses_time_attributes(mock_hass):
    state = mock_hass.states.get.return_value
    state.state = "2026-11-07 06:45:30"
    state.attributes = {"has_date": True, "has_time": True, "hour": 6, "minute": 45, "second": 30}
    schedule = ClimateSchedulerSchedule({CONF_SCHEDULE_TIME: "input_datetime.test"})

    assert schedule.resolve_time(mock_hass) == timedelta(hours=6, minutes=45, seconds=30)


def test_date_only_input_datetime_returns_none(mock_hass):
    state = mock_hass.states.get.return_value
    state.state = "2026-11-07"
    state.attributes = {"has_date": True, "has_time": False, "year": 2026, "month": 11, "day": 7}
    schedule = ClimateSchedulerSchedule({CONF_SCHEDULE_TIME: "input_datetime.test"})

    assert schedule.resolve_time(mock_hass) is None


@pytest.mark.parametrize("unreadable_state", ["unavailable", "unknown", None])
def test_unreadable_entity_keeps_last_known_time(mock_hass, unreadable_state):
    mock_hass.states.get.return_value.state = "07:00:00"
    config = {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_OFFSET: timedelta(minutes=-30)}
    schedule = ClimateSchedulerSchedule(config)
    assert schedule.resolve_time(mock_hass) == timedelta(hours=6, minutes=30)

    if unreadable_state is None:
        mock_hass.states.get.return_value = None
    else:
        mock_hass.states.get.return_value.state = unreadable_state

    assert schedule.resolve_time(mock_hass) == timedelta(hours=6, minutes=30)


def test_unavailable_entity_without_last_known_time_returns_none(mock_hass):
    mock_hass.states.get.return_value.state = "unavailable"
    schedule = ClimateSchedulerSchedule({CONF_SCHEDULE_TIME: "input_datetime.test"})

    assert schedule.resolve_time(mock_hass) is None


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({CONF_SCHEDULE_TIME: timedelta(hours=7)}, "Static: 7:00:00 + 0:00:00"),
        (
            {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_OFFSET: timedelta(minutes=-30)},
            "Dynamic: input_datetime.test - 0:30:00",
        ),
        (
            {CONF_SCHEDULE_TIME: "input_datetime.test", CONF_SCHEDULE_OFFSET: timedelta(hours=1)},
            "Dynamic: input_datetime.test + 1:00:00",
        ),
    ],
)
def test_str(config, expected):
    assert str(ClimateSchedulerSchedule(config)) == expected


def test_invalid_offset_validation():
    """Test that offsets greater than 24h are invalid."""
    import voluptuous as vol

    from custom_components.climate_scheduler.validation import valid_offset

    # Valid
    assert valid_offset(timedelta(hours=23)) == timedelta(hours=23)
    assert valid_offset(timedelta(hours=-23)) == timedelta(hours=-23)

    # Invalid
    with pytest.raises(vol.Invalid):
        valid_offset(timedelta(hours=24))
    with pytest.raises(vol.Invalid):
        valid_offset(timedelta(hours=25))
    with pytest.raises(vol.Invalid):
        valid_offset(timedelta(hours=-25))
