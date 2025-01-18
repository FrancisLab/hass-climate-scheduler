"""Test component setup."""
from datetime import timedelta
from homeassistant.setup import async_setup_component

from custom_components.climate_scheduler import DOMAIN, CONF_UPDATE_INTERVAL, DATA_CLIMATE_SCHEDULER


async def test_async_setup_without_config_fails(hass):
    assert await async_setup_component(hass, DOMAIN, {}) is False

async def test_async_setup_with_min_config(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}}) is True
    assert hass.data[DATA_CLIMATE_SCHEDULER].update_interval == timedelta(minutes=15)

async def test_async_setup_with_interval_config(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_UPDATE_INTERVAL: "00:10:00"}}) is True
    assert hass.data[DATA_CLIMATE_SCHEDULER].update_interval == timedelta(minutes=10)

async def test_async_setup_with_negative_interval_fails(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_UPDATE_INTERVAL: "-00:10:00"}}) is False

async def test_async_setup_with_invalid_interval_fails(hass):
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_UPDATE_INTERVAL: "not_a_valid_time_period"}}) is False