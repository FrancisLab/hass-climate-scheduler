# Home Assistant Climate Scheduler

A Home Assistant component to facililate the automation of climate entities. Allows the creation of multiple climate profiles each with their own schedules and configuration. Allows easy toggling between profiles with an associated input_select entity.

## Installation

Install the custom component using [HACS](https://hacs.xyz/) (recommended), or manually by copying `custom_components\climate_scheduler` to your `config\custom_components` directory.

TODO: HACs badge & integration

## Configuration

### Component Configuration

```yaml
climate_scheduler:
  update_interval: "00:10:00"
```

| Variable | Description | Type | Default |
| update_interval | How often schedulers should attempt to update climate entities. | (Optional) Positive Time HH:MM:SS | 00:15:00 |

### Scheduler Configuration

Each individual scheduler is configured as a switch component. Each scheduler must be assigned climate entities to control and at least one profile.

**Schedulers**

```yaml
switch:
  - platform: climate_scheduler
    name: Bedroom
    default_state: True
    default_profile: "Override"
    climate_entities:
      - climate.bedroom
    profiles:
      # See section bellow
```

| Variable         | Description                       | Type                    | Default             |
| ---------------- | --------------------------------- | ----------------------- | ------------------- | ------------- |
| name             | Name of the scheduler             | Required String         | "Climate Scheduler" |
| default_state    | Initial state of scheduler        | Optional Bool           | False               |
| default_profile  | Initial profile of scheduler      | String                  | Optional String     | First profile |
| climate_entities | Climate entities to control       | Optional List[String]   | []                  |
| profiles         | Climate profiles of the scheduler | Required List[Profiles] |                     |

TODO: Section for each param

**Profiles**

Profiles define when and how to configure climate entities. At least one must be provided per scheduler. Multiple profiles can be provided to make it easy to swith between configurations via UI or automations.

```yaml
    ...
    profiles:
    - id: "Bedroom Heating"
      default_hvac_mode: "heat"
      default_fan_mode: "auto"
      default_swing_mode: "auto"
      default_min_temp: 22
      schedule:
        # See section bellow
```

| Variable           | Description                                                                 | Type                    | Default |
| ------------------ | --------------------------------------------------------------------------- | ----------------------- | ------- |
| id                 | Name of the profile. Must be unique in list.                                | Required String         |         |
| default_hvac_mode  | HVAC mode to use when none specified by schedule entry                      | Optional String         | None    |
| default_fan_mode   | Fan mode to use when none specified by schedule entry                       | Optional String         | None    |
| default_swing_mode | Swing mode to use when none specified by schedule entry                     | Optional String         | None    |
| default_min_temp   | Default min temperature to set when none specified by schedule entry        | Optional Float          | None    |
| default_max_temp   | Default max temperature to set when none specified by schedule entry        | Optional Float          | None    |
| schedule           | List of schedule entries defining climate changes to apply at certain times | Optional List[Schedule] | None    |

TODO: Section for each param

**Schedules**

A schedule is an optional list of times at which the target climate changes. If none are provided the scheduler will only set default values if any are presence. Having a single entry will cause the scheduler to set the desired values at all time. Having multiple entries will have the scheduler update climate entities at the specific time.

```yaml
    ...
    schedule:
      # Heat quietly during morning. Rely on default temp
      - time: "06:30:00"
        fan_mode: "superQuiet"
        swing_mode: "vertical"
      # Heat during the day. Relying on default values
      - time: "07:30:00"
      # Lower temperature during the night with quiet heating
      - time: "20:30:00"
        fan_mode: "superQuiet"
        swing_mode: "vertical"
        min_temp: 17.5
```

| Variable   | Description                                                  | Type                                | Default                                           |
| ---------- | ------------------------------------------------------------ | ----------------------------------- | ------------------------------------------------- |
| time       | Time where the climate must be updated                       | Required Time (HH:MM:SS) < 24:00:00 |                                                   |
| hvac_mode  | HVAC mode to set at time                                     | Optional String                     | Default value from profile if any, otherwise none |
| fan_mode   | Fan mode to set at time                                      | Optional String                     | Default value from profile if any, otherwise none |
| swing_mode | Swing mode to set at time                                    | Optional String                     | Default value from profile if any, otherwise none |
| min_temp   | Min temperature to set at time. Use with relevant HVAC modes | Optional Float                      | Default value from profile if any, otherwise none |
| max_temp   | Man temperature to set at time. Use with relevant HVAC modes | Optional Float                      | Default value from profile if any, otherwise none |

TODO: Section for each param

## Tips & Tricks

### Organizing & Sharing Profiles

You can define profiles in their own separate yaml files and share them across schedulers.

In `configuration.yaml`

```yaml
- platform: climate_scheduler
  name: Bedroom
  default_profile: "Override"
  climate_entities:
    - climate.bedroom
  profiles:
    - !include climate_profiles/bedroom/heating.yaml
    - !include climate_profiles/bedroom/cooling.yaml
    - !include climate_profiles/common/override.yaml
    - !include climate_profiles/common/away.yaml
    - !include climate_profiles/common/vacation.yaml
- platform: climate_scheduler
  name: Living Room
  default_profile: "Override"
  climate_entities:
    - climate.living_room
  profiles:
    - !include climate_profiles/common/heating.yaml
    - !include climate_profiles/common/cooling.yaml
    - !include climate_profiles/common/override.yaml
    - !include climate_profiles/common/away.yaml
    - !include climate_profiles/common/vacation.yaml
```

Example content of `climate_profiles\bedroom\heating.yaml

```yaml
# Climate profile for winter. Only allows heating.
id: "Bedroom Heating"
default_hvac_mode: "heat"
default_fan_mode: "auto"
default_swing_mode: "auto"
default_min_temp: 22
schedule:
  # Heat quietly during morning. Rely on default temp
  - time: "06:30:00"
    fan_mode: "superQuiet"
    swing_mode: "vertical"
  # Heat during the day. Relying on default values
  - time: "07:30:00"
  # Lower temperature during the night with quiet heating
  - time: "20:30:00"
    fan_mode: "superQuiet"
    swing_mode: "vertical"
    min_temp: 17.5
```

### Empty Profile as Override

If you want an override where the scheduler does nothing and let's you manually setup the climate. You can either turn of the scheduler as a switch, or define an override profile which does nothing

```yaml
- platform: climate_scheduler
  name: Living Room
  default_profile: "Override"
  climate_entities:
    - climate.living_room
  profiles:
    - id: "Override"
    - !include climate_profiles/common/heating.yaml
    - !include climate_profiles/common/cooling.yaml
```
