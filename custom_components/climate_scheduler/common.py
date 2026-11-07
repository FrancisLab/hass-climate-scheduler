"""Common data structures for Climate Scheduler."""

import logging
from collections import namedtuple

ComputedClimateData = namedtuple(
    "ComputedClimateData",
    ["hvac_mode", "fan_mode", "swing_mode", "min_temp", "max_temp"],
)


class PrefixAdapter(logging.LoggerAdapter):
    """Logger adapter to add a prefix to messages."""

    def process(self, msg, kwargs):
        """Process the message."""
        return f"{self.extra['prefix']} {msg}", kwargs
