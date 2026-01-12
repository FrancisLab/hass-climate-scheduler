from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
    mock_component,
    mock_restore_cache,
)

from custom_components.climate_scheduler import DOMAIN
from custom_components.climate_scheduler.const import (
    ATTR_PROFILE,
    CONF_CLIMATE_ENTITIES,
    CONF_DEFAULT_PROFILE,
    CONF_DEFAULT_STATE,
    CONF_PROFILE_DEFAULT_FAN_MODE,
    CONF_PROFILE_DEFAULT_HVAC_MODE,
    CONF_PROFILE_DEFAULT_MAX_TEMP,
    CONF_PROFILE_DEFAULT_MIN_TEMP,
    CONF_PROFILE_DEFAULT_SWING_MODE,
    CONF_PROFILE_ID,
    CONF_PROFILE_SCHEDULE,
    CONF_PROFILES,
    CONF_SCHEDULE_HVAC,
    CONF_SCHEDULE_MAX_TEMP,
    CONF_SCHEDULE_TIME,
)

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
                CONF_PROFILE_DEFAULT_HVAC_MODE: HVACMode.HEAT,
            },
            {
                CONF_PROFILE_ID: "Weekend",
                CONF_PROFILE_SCHEDULE: [
                    {
                        CONF_SCHEDULE_TIME: timedelta(hours=9),
                        CONF_SCHEDULE_HVAC: HVACMode.COOL,
                        CONF_SCHEDULE_MAX_TEMP: 20,
                    }
                ],
            },
        ],
    }


async def async_setup_scheduler(hass, config):
    # Mock climate entity
    mock_component(hass, "climate")
    hass.states.async_set("climate.test_ac", HVACMode.OFF)

    full_config = {DOMAIN: {}, SWITCH_DOMAIN: [config]}

    assert await async_setup_component(hass, DOMAIN, full_config)
    assert await async_setup_component(hass, SWITCH_DOMAIN, full_config)
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
    input_select = hass.states.get("input_select.input_select_climate_scheduler_test_scheduler_profile_selector")
    assert input_select is not None
    assert input_select.state == "Default"


async def test_setup_with_custom_default_state(hass: HomeAssistant, mock_climate_scheduler_config):
    mock_climate_scheduler_config[CONF_DEFAULT_STATE] = True
    await async_setup_scheduler(hass, mock_climate_scheduler_config)

    state = hass.states.get("switch.climate_scheduler_test_scheduler")
    assert state.state == STATE_ON


async def test_ignore_invalid_default_profile(hass: HomeAssistant, mock_climate_scheduler_config):
    mock_climate_scheduler_config[CONF_DEFAULT_PROFILE] = "InvalidProfile"
    # Should not fail, just fallback
    await async_setup_scheduler(hass, mock_climate_scheduler_config)

    state = hass.states.get("switch.climate_scheduler_test_scheduler")
    # Fallback to first available
    assert state.attributes.get("current_profile") == "Default"


async def test_restore_state(hass: HomeAssistant, mock_climate_scheduler_config):
    # We need to mock services because restoring state triggers an immediate update
    async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)
    async_mock_service(hass, "climate", SERVICE_SET_FAN_MODE)
    async_mock_service(hass, "climate", SERVICE_SET_SWING_MODE)

    entity_id = "switch.climate_scheduler_test_scheduler"
    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                STATE_ON,
                attributes={ATTR_PROFILE: "Weekend"},
            )
        ],
    )

    await async_setup_scheduler(hass, mock_climate_scheduler_config)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_PROFILE) == "Weekend"


async def test_turn_on_updates_climate(hass: HomeAssistant, mock_climate_scheduler_config):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"

    # Mock service calls
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)

    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Should call climate set_hvac_mode HEAT (from Default profile)
    assert len(mock_set_hvac) == 1
    assert mock_set_hvac[0].data[ATTR_ENTITY_ID] == "climate.test_ac"
    assert mock_set_hvac[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_switch_profile(hass: HomeAssistant, mock_climate_scheduler_config):
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    mock_set_temp = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)

    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"

    # Turn on first
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Freeze time before 9am
    now = dt_util.now().replace(hour=8, minute=0, second=0)
    with patch("homeassistant.util.dt.now", return_value=now):
        # Switch profile to Weekend via input_select
        await hass.services.async_call(
            "input_select",
            "select_option",
            {
                ATTR_ENTITY_ID: ("input_select.input_select_climate_scheduler_test_scheduler_profile_selector"),
                "option": "Weekend",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        # In Weekend profile, no schedule matches yet (starts at 9).
        # It should wrap around to the last schedule (9am).
        assert len(mock_set_hvac) > 0
        assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL

        assert len(mock_set_temp) > 0
        assert mock_set_temp[-1].data[ATTR_TEMPERATURE] == 20.0

    state = hass.states.get(entity_id)
    assert state.attributes.get("current_profile") == "Weekend"


async def test_time_change_trigger(hass: HomeAssistant, mock_climate_scheduler_config):
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    mock_set_temp = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)

    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"

    # Switch to Weekend profile
    await hass.services.async_call(
        "input_select",
        "select_option",
        {
            ATTR_ENTITY_ID: ("input_select.input_select_climate_scheduler_test_scheduler_profile_selector"),
            "option": "Weekend",
        },
        blocking=True,
    )

    # Turn On
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Now verify that when time passes, it re-applies or changes.
    # The Weekend schedule is at 9am.

    # let's simulate time passing to 09:00:00
    target_time = dt_util.now().replace(hour=9, minute=0, second=0)

    # We need to mock 'now()' inside the component too, because it calls `now()`
    # to get current time.
    with patch("custom_components.climate_scheduler.switch.now", return_value=target_time):
        async_fire_time_changed(hass, target_time)
        await hass.async_block_till_done()

    # Should verify calls
    assert len(mock_set_hvac) > 0
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL

    assert len(mock_set_temp) > 0
    assert mock_set_temp[-1].data[ATTR_TEMPERATURE] == 20.0


async def test_climate_attributes_set_correctly(hass: HomeAssistant):
    # Setup a complex profile
    config = {
        CONF_PLATFORM: "climate_scheduler",
        CONF_NAME: "Complex Scheduler",
        CONF_CLIMATE_ENTITIES: ["climate.complex_ac"],
        CONF_PROFILES: [
            {
                CONF_PROFILE_ID: "Full",
                CONF_PROFILE_DEFAULT_HVAC_MODE: HVACMode.HEAT_COOL,
                CONF_PROFILE_DEFAULT_FAN_MODE: "high",
                CONF_PROFILE_DEFAULT_SWING_MODE: "vertical",
                CONF_PROFILE_DEFAULT_MIN_TEMP: 18,
                CONF_PROFILE_DEFAULT_MAX_TEMP: 22,
            }
        ],
    }

    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    mock_set_temp = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)
    mock_set_fan = async_mock_service(hass, "climate", SERVICE_SET_FAN_MODE)
    mock_set_swing = async_mock_service(hass, "climate", SERVICE_SET_SWING_MODE)

    await async_setup_scheduler(hass, config)
    entity_id = "switch.climate_scheduler_complex_scheduler"

    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT_COOL
    assert mock_set_fan[-1].data[ATTR_FAN_MODE] == "high"
    assert mock_set_swing[-1].data[ATTR_SWING_MODE] == "vertical"

    # Heat_cool uses target_temp_low/high
    assert mock_set_temp[-1].data[ATTR_TARGET_TEMP_LOW] == 18
    assert mock_set_temp[-1].data[ATTR_TARGET_TEMP_HIGH] == 22


async def test_climate_attributes_omitted_if_none(hass: HomeAssistant):
    # Profile with only HVAC mode
    config = {
        CONF_PLATFORM: "climate_scheduler",
        CONF_NAME: "Simple Scheduler",
        CONF_CLIMATE_ENTITIES: ["climate.simple_ac"],
        CONF_PROFILES: [
            {
                CONF_PROFILE_ID: "Simple",
                CONF_PROFILE_DEFAULT_HVAC_MODE: HVACMode.HEAT,
                # No temp, fan, or swing
            }
        ],
    }

    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    mock_set_temp = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)
    mock_set_fan = async_mock_service(hass, "climate", SERVICE_SET_FAN_MODE)

    await async_setup_scheduler(hass, config)
    entity_id = "switch.climate_scheduler_simple_scheduler"

    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Verify HVAC is called
    assert len(mock_set_hvac) == 1
    # Verify others are NOT called
    assert len(mock_set_temp) == 0
    assert len(mock_set_fan) == 0


async def test_turn_off_stops_updates(hass: HomeAssistant, mock_climate_scheduler_config):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"

    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)

    # Turn On
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()
    assert len(mock_set_hvac) == 1  # Initial update

    # Turn Off
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Pass time
    mock_set_hvac.clear()
    target_time = dt_util.now() + timedelta(minutes=30)
    with patch("custom_components.climate_scheduler.switch.now", return_value=target_time):
        async_fire_time_changed(hass, target_time)
        await hass.async_block_till_done()

    # Should be NO extra calls
    assert len(mock_set_hvac) == 0


async def test_climate_attributes_set_for_heat_and_cool_modes(hass: HomeAssistant):
    # Test setting temp for pure HEAT and COOL modes with defaults
    config = {
        CONF_PLATFORM: "climate_scheduler",
        CONF_NAME: "Temp Scheduler",
        CONF_CLIMATE_ENTITIES: ["climate.temp_ac"],
        CONF_PROFILES: [
            {
                CONF_PROFILE_ID: "HeatProfile",
                CONF_PROFILE_DEFAULT_HVAC_MODE: HVACMode.HEAT,
                CONF_PROFILE_DEFAULT_MIN_TEMP: 19,
            },
            {
                CONF_PROFILE_ID: "CoolProfile",
                CONF_PROFILE_DEFAULT_HVAC_MODE: HVACMode.COOL,
                CONF_PROFILE_DEFAULT_MAX_TEMP: 24,
            },
        ],
        CONF_DEFAULT_PROFILE: "HeatProfile",
    }

    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    mock_set_temp = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)

    await async_setup_scheduler(hass, config)
    entity_id = "switch.climate_scheduler_temp_scheduler"

    # Turn On - Should trigger HeatProfile
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    await hass.async_block_till_done()

    # Verify Heat
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.HEAT
    assert mock_set_temp[-1].data[ATTR_TEMPERATURE] == 19

    # Switch to CoolProfile
    await hass.services.async_call(
        "input_select",
        "select_option",
        {
            ATTR_ENTITY_ID: "input_select.input_select_climate_scheduler_temp_scheduler_profile_selector",
            "option": "CoolProfile",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify Cool
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL
    assert mock_set_temp[-1].data[ATTR_TEMPERATURE] == 24


async def test_setup_fails_gracefully_without_scheduler(hass: HomeAssistant):
    # If DATA_CLIMATE_SCHEDULER is missing, setup should fail returning False
    # To simulate this, we try to setup the platform directly without setting up the
    # domain logic that puts the scheduler in hass.data
    from custom_components.climate_scheduler.switch import async_setup_platform

    assert await async_setup_platform(hass, {}, None) is False


async def test_profile_selector_creation_fails_gracefully(hass: HomeAssistant, mock_climate_scheduler_config):
    # Mock async_get_platforms to return empty list to simulate no input_select platform
    with patch(
        "custom_components.climate_scheduler.switch.async_get_platforms",
        return_value=[],
    ):
        await async_setup_scheduler(hass, mock_climate_scheduler_config)

        # Check that the switch still set up
        state = hass.states.get("switch.climate_scheduler_test_scheduler")
        assert state is not None

        # Check that the selector does NOT exist (or at least we didn't crash)
        # The selector entity ID is usually created by the input_select platform
        # tracking it. Since we mocked it out, it won't be there.
        input_select = hass.states.get("input_select.input_select_climate_scheduler_test_scheduler_profile_selector")
        assert input_select is None


async def test_update_climate_entity_guards(hass: HomeAssistant, mock_climate_scheduler_config):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)

    # We need to access the switch instance directly to test the private method
    # Since we don't have easy access to the instance from the state machine,
    # we can rely on the fact that if we call the method effectively, it returns.

    # However, testing "return None" is tricky without mocking something else
    # that would be called if it proceeding.

    # Let's try to grab the entity instance from the platform if possible,
    # but hass.data[SWITCH_DOMAIN] might store it?
    # Easier way: The auditing tool showed lines 327 'if data is None: return'
    # We can try to craft a scenario where compute_climate returns None?
    # Profile.compute_climate always returns a ComputedClimateData object or falls back to defaults.

    # Let's try to mock the profile's compute_climate to return None
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)

    with patch(
        "custom_components.climate_scheduler.profile.ClimateSchedulerProfile.compute_climate",
        return_value=None,
    ):
        # Force an update
        # We need to get the component instance to call async_update_climate directly or trigger it
        # Triggering via time change or turn_on
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.climate_scheduler_test_scheduler"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(mock_set_hvac) == 0
