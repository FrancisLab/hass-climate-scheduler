
import pytest
from datetime import timedelta, datetime
from unittest.mock import patch, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT_COOL,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_SWING_MODE,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_FAN_MODE,
    ATTR_SWING_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_OFF,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_CLIMATE_ENTITIES,
    CONF_PROFILES,
    CONF_DEFAULT_PROFILE
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.climate_scheduler.switch import (
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
    CONF_SCHEDULE_TIME,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_MIN_TEMP,
    CONF_PROFILE_DEFAULT_HVAC_MODE,
)
from custom_components.climate_scheduler import DOMAIN

# Fixtures and Helpers

@pytest.fixture
def mock_climate_scheduler_config():
    return {
        CONF_PLATFORM: "climate_scheduler",
        CONF_NAME: "Test Scheduler",
        CONF_CLIMATE_ENTITIES: ["climate.test_ac"],
        CONF_PROFILES: [
            {
                CONF_PROFILE_ID: "Default",
                CONF_PROFILE_DEFAULT_HVAC_MODE: HVAC_MODE_HEAT,
            },
            {
                CONF_PROFILE_ID: "Weekend",
                CONF_PROFILE_SCHEDULE: [
                    {
                        CONF_SCHEDULE_TIME: timedelta(hours=9),
                        CONF_SCHEDULE_HVAC: HVAC_MODE_COOL,
                        CONF_SCHEDULE_MIN_TEMP: 20,
                    }
                ]
            }
        ]
    }

async def async_setup_scheduler(hass, config):
    assert await async_setup_component(hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: config})
    await hass.async_block_till_done()

# Tests

async def test_setup_platform(hass: HomeAssistant, mock_climate_scheduler_config):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    
    state = hass.states.get("switch.climate_scheduler_test_scheduler")
    assert state is not None
    assert state.state == STATE_OFF  # Default is off
    assert state.attributes.get("current_profile") == "Default"
    assert state.attributes.get("profile_options") == ["Default", "Weekend"]

    # Check input_select creation
    input_select = hass.states.get("input_select.climate_scheduler_test_scheduler_profile_selector")
    assert input_select is not None
    assert input_select.state == "Default"

async def test_turn_on_updates_climate(hass: HomeAssistant, mock_climate_scheduler_config):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"

    # Mock service calls
    set_hvac =  patch.object(hass.services, 'async_call', side_effect=hass.services.async_call)
    
    with patch("homeassistant.core.ServiceRegistry.async_call") as mock_service:
         await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
         
         # Should call climate set_hvac_mode HEAT (from Default profile)
         mock_service.assert_any_call(
             "climate",
             SERVICE_SET_HVAC_MODE,
             {ATTR_ENTITY_ID: "climate.test_ac", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
         )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

async def test_switch_profile(hass: HomeAssistant, mock_climate_scheduler_config):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"
    
    # Turn on first
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)

    # Freeze time before 9am
    now = dt_util.now().replace(hour=8, minute=0, second=0)
    with patch("homeassistant.util.dt.now", return_value=now), \
         patch("homeassistant.core.ServiceRegistry.async_call") as mock_service:
         
        # Switch profile to Weekend via input_select
        await hass.services.async_call(
            "input_select",
            "select_option",
            {
                ATTR_ENTITY_ID: "input_select.climate_scheduler_test_scheduler_profile_selector",
                "option": "Weekend"
            },
            blocking=True
        )
        await hass.async_block_till_done()

        # In Weekend profile, no schedule matches yet (starts at 9).
        # Wait, if no schedule matches, and no default for the profile, it might do nothing or error?
        # The test config for Weekend only has a schedule at 9am.
        # Let's check ClimateSchedulerProfile._find_schedule logic.
        # It says "If the current time is earlier than the first schedule, wrap around and return the last schedule of the day"
        # So it should return the 9am schedule (which is the last/only schedule).
        
        # So it should be COOL, 20
        mock_service.assert_any_call(
             "climate",
             SERVICE_SET_HVAC_MODE,
             {ATTR_ENTITY_ID: "climate.test_ac", ATTR_HVAC_MODE: HVAC_MODE_COOL},
         )
        mock_service.assert_any_call(
             "climate",
             SERVICE_SET_TEMPERATURE,
             {ATTR_ENTITY_ID: "climate.test_ac", ATTR_HVAC_MODE: HVAC_MODE_COOL, ATTR_TEMPERATURE: 20.0},
         )
         
    state = hass.states.get(entity_id)
    assert state.attributes.get("current_profile") == "Weekend"


async def test_time_change_trigger(hass: HomeAssistant, mock_climate_scheduler_config):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"
    
    # Switch to Weekend profile
    await hass.services.async_call(
        "input_select",
        "select_option",
        {
            ATTR_ENTITY_ID: "input_select.climate_scheduler_test_scheduler_profile_selector",
            "option": "Weekend"
        },
        blocking=True
    )
    
    # Turn On
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)

    # Initially it will apply the schedule (tested above).
    
    # Now verify that when time passes, it re-applies or changes.
    # Actually, the logic is: it tracks time change at the specific schedule times.
    # The Weekend schedule is at 9am.
    
    # let's simulate time passing to 09:00:00
    with patch("homeassistant.core.ServiceRegistry.async_call") as mock_service:
        # We need to fire the time change event that the scheduler is listening for.
        # It uses `async_track_time_change` which uses `async_track_utc_time_change`.
        # However, checking `switch.py`:
        # self._schedule_tracker_remove_callbacks.append(async_track_time_change(..., hour=..., ...))
        
        # We can probably just trigger `async_update_climate` manually or use `async_fire_time_changed` (if available via pytest-homeassistant-custom-component)
        # But `async_fire_time_changed` fires `time_changed` event which `async_track_time_change` listens to.
        
        from pytest_homeassistant_custom_component.common import async_fire_time_changed
        
        target_time = dt_util.now().replace(hour=9, minute=0, second=0)
        
        # We need to mock 'now()' inside the component too, because it calls `now()` to get current time.
        with patch("custom_components.climate_scheduler.switch.now", return_value=target_time):
             async_fire_time_changed(hass, target_time)
             await hass.async_block_till_done()

        # Should verify calls
        mock_service.assert_any_call(
             "climate",
             SERVICE_SET_HVAC_MODE,
             {ATTR_ENTITY_ID: "climate.test_ac", ATTR_HVAC_MODE: HVAC_MODE_COOL},
        )

