"""Test component setup."""
from homeassistant.setup import async_setup_component

from custom_components.climate_scheduler import DOMAIN, CONF_UPDATE_INTERVAL


async def test_async_setup_without_config_fails(hass):
    assert await async_setup_component(hass, DOMAIN, {}) is False

async def test_async_setup_with_min_config_succeeds(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}}) is True

async def test_async_setup_with_correct_interval_config_succeeds(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_UPDATE_INTERVAL: "00:10:00"}}) is True

async def test_async_setup_with_negative_interval_config_fails(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_UPDATE_INTERVAL: "-00:10:00"}}) is False

async def test_async_setup_with_invalid_interval_config_fails(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_UPDATE_INTERVAL: "not_a_valid_time_period"}}) is False