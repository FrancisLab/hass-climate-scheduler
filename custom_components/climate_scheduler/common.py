"""Common data structures for Climate Scheduler."""

import logging
from collections import namedtuple
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schedule import ClimateSchedulerSchedule

ComputedClimateData = namedtuple(
    "ComputedClimateData",
    ["hvac_mode", "fan_mode", "swing_mode", "min_temp", "max_temp"],
)


@dataclass
class ResolvedScheduleEntry:
    """Entry with resolved time."""

    time: timedelta
    schedule: "ClimateSchedulerSchedule"


class PrefixAdapter(logging.LoggerAdapter):
    """Logger adapter to add a prefix to messages."""

    def process(self, msg, kwargs):
        """Process the message."""
        return f"{self.extra['prefix']} {msg}", kwargs
