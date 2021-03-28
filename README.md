# Home Assistant Climate Scheduler

## Configuration Example

```
climate_scheduler:
    # How often to re-evaluate climate
    update_interval: 10 minutes
    # Interpolate current target temperature between two schedules
    interpolate_between_targets: true
    # Max window of time to interpolate target temperature over
    max_interpolation_window: 20 minutes

switch:
    - platform: climate_scheduler
      name: "Master Bedroom"
      climate_entities:
        - climate.master_bedroom
      climate_sensor_entities:
        - sensor.master_bedroom_side_table
      profiles:
        !include climate_profiles/master_bedroom/winter.yaml
        !include climate_profiles/master_bedroom/summer.yaml
        !include climate_profiles/common/away.yaml
        !include climate_profiles/common/vacation.yaml
    - platform: climate_scheduler
      name: "Living Room"
      climate_entities:
        - climate.living_room
      profiles:
        !include climate_profiles/living_room/winter.yaml
        !include climate_profiles/living_room/summer.yaml
        !include climate_profiles/common/away.yaml
        !include climate_profiles/common/vacation.yaml

# climate_profiles/master_bedroom/winter.yaml
- name: "Master Bedroom Winter"
  id: "winter_home"
  default_hvac_mode: "head"
  # other defaults
  schedules:
  - time: 06:30
    hvac_mode: "heat"
    temperature: 22
    fan_mode: "auto"
    swing_mode: "auto"
  - time: 21:00
    hvac_mode: "heat"
    temperature: 18
    fan_mode: "quiet"
    swing_mode: "midpoint"

# climate_profiles/master_bedroom/summer.yaml
- name: "Master Bedroom Summer"
  id: "summer_home"
  default_fan_mode: "auto"
  default_swing_mode: "auto"
  schedules:
  - time: 06:30
      hvac_mode: "cool"
      temperature: 22
  - time: 21:00
      hvac_mode: "cool"
      temperature: 18
      fan_mode: "quiet"
      swing_mode: "midpoint"
```
