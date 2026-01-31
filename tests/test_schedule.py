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
    assert not schedule.is_dynamic

    resolved = schedule.resolve_time(mock_hass)
    assert resolved == timedelta(hours=10)


def test_entity_time_resolution(mock_hass):
    mock_hass.states.get.return_value.state = "10:30:00"
    config = {CONF_SCHEDULE_TIME: "input_datetime.test"}
    schedule = ClimateSchedulerSchedule(config)
    assert schedule.is_dynamic
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


def test_invalid_offset_validation():
    """Test that offsets greater than 24h are invalid."""
    import voluptuous as vol

    from custom_components.climate_scheduler.validation import valid_offset

    # Valid
    assert valid_offset(timedelta(hours=23)) == timedelta(hours=23)
    assert valid_offset(timedelta(hours=-23)) == timedelta(hours=-23)

    # Invalid
    with pytest.raises(vol.Invalid):
        valid_offset(timedelta(hours=25))
    with pytest.raises(vol.Invalid):
        valid_offset(timedelta(hours=-25))
