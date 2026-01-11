"""Common data structures for Climate Scheduler."""

from collections import namedtuple

ComputedClimateData = namedtuple(
    "ComputedClimateData",
    ["hvac_mode", "fan_mode", "swing_mode", "min_temp", "max_temp"],
)
