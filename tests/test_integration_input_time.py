"""Integration tests for input_time support."""

from datetime import timedelta
from unittest.mock import patch

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
)
from homeassistant.core import HomeAssistant
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


async def test_input_time_initial_state(hass: HomeAssistant, input_time_config):
    """Test initial state based on input times."""
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    entity_id = "switch.climate_scheduler_input_time_scheduler"

    # Turn On
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Time: 08:00 (After wake up 07:00) -> HEAT
    target_time = dt_util.now().replace(hour=8, minute=0, second=0, microsecond=0)
    with patch("custom_components.climate_scheduler.switch.now", return_value=target_time):
        async_fire_time_changed(hass, target_time)
        await hass.async_block_till_done()

    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_input_time_entity_update(hass: HomeAssistant, input_time_config):
    """Test response to input_datetime entity changes."""
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    entity_id = "switch.climate_scheduler_input_time_scheduler"
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Initial state check logic omitted for brevity, assuming initial setup is correct
    target_time = dt_util.now().replace(hour=8, minute=0, second=0, microsecond=0)

    # Change wake_up time to 09:00 (so 08:00 is now BEFORE wake up, likely wrapping to previous day's sleep schedule)
    # Sleep is 22:00 - 30m = 21:30.
    # So 08:00 is between 21:30 (yesterday) and 09:00. Should be COOL.
    mock_set_hvac.clear()

    # We must ensure 'now' is still 08:00 when the update triggers
    with patch("custom_components.climate_scheduler.switch.now", return_value=target_time):
        hass.states.async_set("input_datetime.wake_up", "09:00:00")
        await hass.async_block_till_done()

    assert len(mock_set_hvac) > 0, "Update not triggered on entity change"
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL


async def test_input_time_schedule_trigger(hass: HomeAssistant, input_time_config):
    """Test that schedules trigger at dynamic times."""
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    await async_setup_scheduler(hass, input_time_config)
    entity_id = "switch.climate_scheduler_input_time_scheduler"
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Move time to 09:00:00. This assumes wake_up is default 07:00 unless we change it.
    # Wait, the config fixture sets it to 07:00 initially.
    # Let's verify trigger at 07:00:00
    target_time = dt_util.now().replace(hour=7, minute=0, second=0, microsecond=0)

    mock_set_hvac.clear()
    with patch("custom_components.climate_scheduler.switch.now", return_value=target_time):
        async_fire_time_changed(hass, target_time, fire_all=True)
        await hass.async_block_till_done()

    assert len(mock_set_hvac) > 0, "Update not triggered on schedule time"
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_offset_handling(hass: HomeAssistant, input_time_config):
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)

    await async_setup_scheduler(hass, input_time_config)
    entity_id = "switch.climate_scheduler_input_time_scheduler"
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Sleep is 22:00. with -30m offset = 21:30.
    # At 21:29 -> HEAT (from wake up, presumably)
    target_time = dt_util.now().replace(hour=21, minute=29, second=0, microsecond=0)
    with patch("custom_components.climate_scheduler.switch.now", return_value=target_time):
        async_fire_time_changed(hass, target_time)
        await hass.async_block_till_done()

    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    # At 21:31 -> COOL
    target_time_2 = dt_util.now().replace(hour=21, minute=31, second=0, microsecond=0)
    with patch("custom_components.climate_scheduler.switch.now", return_value=target_time_2):
        async_fire_time_changed(hass, target_time_2)
        await hass.async_block_till_done()

    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL
