"""Climate Scheduler Implementation"""

from datetime import timedelta

from homeassistant.core import HomeAssistant

from .const import CONF_UPDATE_INTERVAL


class ClimateScheduler:
    """Climate Scheduler Implementation"""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass = hass
        self._update_interval: timedelta = config.get(
            CONF_UPDATE_INTERVAL, timedelta(minutes=15)
        )

    @property
    def update_interval(self) -> timedelta:
        return self._update_interval
