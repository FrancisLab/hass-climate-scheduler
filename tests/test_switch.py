from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
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
from custom_components.climate_scheduler.switch import (
    CONF_CLIMATE_ENTITIES,
    CONF_PROFILE_DEFAULT_HVAC_MODE,
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
    input_select = hass.states.get(
        "input_select.climate_scheduler_test_scheduler_profile_selector"
    )
    assert input_select is not None
    assert input_select.state == "Default"


async def test_turn_on_updates_climate(
    hass: HomeAssistant, mock_climate_scheduler_config
):
    await async_setup_scheduler(hass, mock_climate_scheduler_config)
    entity_id = "switch.climate_scheduler_test_scheduler"

    # Mock service calls
    mock_set_hvac = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
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
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    # Freeze time before 9am
    now = dt_util.now().replace(hour=8, minute=0, second=0)
    with patch("homeassistant.util.dt.now", return_value=now):
        # Switch profile to Weekend via input_select
        await hass.services.async_call(
            "input_select",
            "select_option",
            {
                ATTR_ENTITY_ID: (
                    "input_select.climate_scheduler_test_scheduler_profile_selector"
                ),
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
            ATTR_ENTITY_ID: (
                "input_select.climate_scheduler_test_scheduler_profile_selector"
            ),
            "option": "Weekend",
        },
        blocking=True,
    )

    # Turn On
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    # Now verify that when time passes, it re-applies or changes.
    # The Weekend schedule is at 9am.

    # let's simulate time passing to 09:00:00
    target_time = dt_util.now().replace(hour=9, minute=0, second=0)

    # We need to mock 'now()' inside the component too, because it calls `now()`
    # to get current time.
    with patch(
        "custom_components.climate_scheduler.switch.now", return_value=target_time
    ):
        async_fire_time_changed(hass, target_time)
        await hass.async_block_till_done()

    # Should verify calls
    assert len(mock_set_hvac) > 0
    assert mock_set_hvac[-1].data[ATTR_HVAC_MODE] == HVACMode.COOL

    assert len(mock_set_temp) > 0
    assert mock_set_temp[-1].data[ATTR_TEMPERATURE] == 20.0
