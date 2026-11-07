"""Integration tests for input_time support."""

from datetime import datetime, timedelta

import pytest
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SERVICE_SET_HVAC_MODE,
    HVACMode,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
    mock_component,
)

from custom_components.climate_scheduler import DOMAIN
from custom_components.climate_scheduler.const import (
    CONF_CLIMATE_ENTITIES,
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
    CONF_PROFILES,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_OFFSET,
    CONF_SCHEDULE_TIME,
)

ENTITY_ID = "switch.climate_scheduler_input_time_scheduler"


@pytest.fixture
def input_time_config():
    return {
        CONF_PLATFORM: "climate_scheduler",
        CONF_NAME: "Input Time Scheduler",
        CONF_CLIMATE_ENTITIES: ["climate.test_ac"],
        CONF_PROFILES: [
            {
                CONF_PROFILE_ID: "Dynamic",
                CONF_PROFILE_SCHEDULE: [
                    {
                        CONF_SCHEDULE_TIME: "input_datetime.wake_up",
                        CONF_SCHEDULE_HVAC: HVACMode.HEAT,
                    },
                    {
                        CONF_SCHEDULE_TIME: "input_datetime.sleep",
                        CONF_SCHEDULE_OFFSET: timedelta(minutes=-30),  # 30 min before sleep
                        CONF_SCHEDULE_HVAC: HVACMode.COOL,
                    },
                ],
            },
        ],
    }


def local_time(hour: int, minute: int = 0, second: int = 0) -> datetime:
    """Return a datetime on a fixed day, in the test instance's time zone."""
    return datetime(2026, 1, 15, hour, minute, second, tzinfo=dt_util.get_default_time_zone())


async def async_setup_scheduler(hass, config):
    # Mock climate entity
    mock_component(hass, "climate")
    hass.states.async_set("climate.test_ac", HVACMode.OFF)

    # Mock input_datetime entities
    hass.states.async_set("input_datetime.wake_up", "07:00:00")
    hass.states.async_set("input_datetime.sleep", "22:00:00")

    full_config = {DOMAIN: {}, SWITCH_DOMAIN: [config]}

    assert await async_setup_component(hass, DOMAIN, full_config)
    assert await async_setup_component(hass, SWITCH_DOMAIN, full_config)
    await hass.async_block_till_done()


async def async_turn_on(hass):
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True)
    await hass.async_block_till_done()


async def test_input_time_initial_state(hass: HomeAssistant, input_time_config, freezer):
    """Test initial state based on input times."""
    freezer.move_to(local_time(8))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)

    await async_turn_on(hass)

    # 08:00 is after wake up (07:00) -> HEAT
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_input_time_entity_update(hass: HomeAssistant, input_time_config, freezer):
    """Test response to input_datetime entity changes."""
    freezer.move_to(local_time(8))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    # Moving wake up to 09:00 puts 08:00 between sleep - 30m (21:30, yesterday) and wake up -> COOL
    mock_set_hvac.clear()
    hass.states.async_set("input_datetime.wake_up", "09:00:00")
    await hass.async_block_till_done()

    assert len(mock_set_hvac) > 0, "Update not triggered on entity change"
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL

    # The new wake up time is tracked
    freezer.move_to(local_time(9))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_input_time_schedule_trigger(hass: HomeAssistant, input_time_config, freezer):
    """Test that schedules trigger at dynamic times."""
    freezer.move_to(local_time(6, 59, 59))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)

    # Before wake up, wraps around to sleep -> COOL
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL

    mock_set_hvac.clear()
    freezer.move_to(local_time(7))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_set_hvac) > 0, "Update not triggered on schedule time"
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_offset_handling(hass: HomeAssistant, input_time_config, freezer):
    """Test that offsets shift the schedule time."""
    # Sleep is 22:00 with a -30m offset, so the COOL schedule starts at 21:30
    freezer.move_to(local_time(21, 29, 59))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)

    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    mock_set_hvac.clear()
    freezer.move_to(local_time(21, 30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_set_hvac) > 0, "Update not triggered on offset schedule time"
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL


async def test_same_entity_with_different_offsets(hass: HomeAssistant, input_time_config, freezer):
    """Test that one entity can drive several schedules through offsets."""
    input_time_config[CONF_PROFILES][0][CONF_PROFILE_SCHEDULE] = [
        {
            CONF_SCHEDULE_TIME: "input_datetime.wake_up",
            CONF_SCHEDULE_OFFSET: "-01:00:00",
            CONF_SCHEDULE_HVAC: HVACMode.HEAT,
        },
        {
            CONF_SCHEDULE_TIME: "input_datetime.wake_up",
            CONF_SCHEDULE_OFFSET: "01:00:00",
            CONF_SCHEDULE_HVAC: HVACMode.COOL,
        },
    ]
    freezer.move_to(local_time(7, 30))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)

    # Wake up is 07:00: HEAT from 06:00, COOL from 08:00
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    freezer.move_to(local_time(8))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL


async def test_unavailable_entity_keeps_last_known_time(hass: HomeAssistant, input_time_config, freezer):
    """Test that an entity going unavailable doesn't drop its schedule."""
    freezer.move_to(local_time(8))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    # Without the wake up schedule, only COOL would remain and be applied
    mock_set_hvac.clear()
    hass.states.async_set("input_datetime.wake_up", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert len(mock_set_hvac) == 0

    # The schedule still triggers at the last known time
    freezer.move_to(local_time(21, 30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL

    freezer.move_to(local_time(7, 0) + timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_entity_change_without_schedule_change_is_ignored(hass: HomeAssistant, input_time_config, freezer):
    """Test that moving a time entity doesn't push climate updates unless the active schedule changes."""
    freezer.move_to(local_time(14))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    # Still HEAT at 14:00, so nothing to apply
    mock_set_hvac.clear()
    hass.states.async_set("input_datetime.wake_up", "07:30:00")
    await hass.async_block_till_done()

    assert len(mock_set_hvac) == 0

    # The new wake up time is still tracked
    freezer.move_to(local_time(7, 30) + timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_attribute_only_change_is_ignored(hass: HomeAssistant, input_time_config, freezer):
    """Test that attribute-only changes of a time entity don't push climate updates."""
    freezer.move_to(local_time(8))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)

    mock_set_hvac.clear()
    hass.states.async_set("input_datetime.wake_up", "07:00:00", {"editable": True})
    await hass.async_block_till_done()

    assert len(mock_set_hvac) == 0


async def test_removed_switch_stops_tracking(hass: HomeAssistant, input_time_config, freezer):
    """Test that a removed switch no longer reacts to time or time entity changes."""
    freezer.move_to(local_time(8))
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    await async_turn_on(hass)

    platform = next(p for p in async_get_platforms(hass, DOMAIN) if p.domain == SWITCH_DOMAIN)
    await platform.async_remove_entity(ENTITY_ID)
    await hass.async_block_till_done()
    mock_set_hvac.clear()

    # Would change the active schedule, then trigger the new schedule time and the update interval
    hass.states.async_set("input_datetime.wake_up", "09:00:00")
    await hass.async_block_till_done()
    freezer.move_to(local_time(9))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(mock_set_hvac) == 0
