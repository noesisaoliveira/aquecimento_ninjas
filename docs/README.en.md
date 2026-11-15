# Aquecimento Ninjas

Per-room radiator heating for Home Assistant, built on **Better Thermostat**.
Up to **5 radiator valves (TRVs)**, a setup wizard, and an automatically created dashboard with charts.

🇵🇹 **Documentação em português:** [README.md](../README.md)

---

## Features

- **Master switch** – turns the boiler and every room on/off. *Off* has priority over everything.
- **Comfort / Eco mode** – one selector for the whole house; each room has its own comfort and eco temperature.
- **Change on the thermostat = new setting** – changing a room's target on its thermostat card (or the valve knob)
  saves it as that room's comfort or eco temperature.
- **Away mode** – automatic when everyone has been away for a configurable time, or manual; uses an away temperature.
- **Boiler reference rooms** – choose which rooms the boiler thermostat reads; with two or more, it uses the average.
- **Boiler thermostat** – use an existing one (e.g. `generic_thermostat`) or let the integration create one.
- **Boost** – heat only the selected rooms to a boost temperature for 30 min to 6 h; the other rooms are turned off and everything is restored at the end.
- **Windows** – pauses the room 10 s after the window sensor opens and resumes 10 s after it closes; without a sensor, detects an open window from a fast temperature drop.
- **Reliability** – every command to the valve is verified and resent up to 3 times; if the room sensor fails, the room switches to emergency mode (eco temperature).
- **Diagnostics** – "room not heating", "sensor problem", failed command count and diagnostics download.
- **Notifications** – open windows, low batteries, sensor problems and rooms not heating.
- **Statistics** – average, minimum, maximum, spread between rooms, boiler hours/cycles today.
- **Dashboard** – views *Heating* and *Charts* created automatically.
- Portuguese and English.

## Requirements

| Requirement | Notes |
|---|---|
| Home Assistant 2025.1 or newer | |
| [HACS](https://hacs.xyz) | To install this integration and Better Thermostat |
| **Better Thermostat** (required) | One Better Thermostat per room |
| Radiator valves (TRVs) | Max 5 in total, any brand supported by Better Thermostat |
| One temperature sensor per room | Used by Better Thermostat and by the boiler reference |
| Boiler on/off switch or thermostat | Relay that fires the boiler |

### Optional – for the Enhanced dashboard

Without these the integration works normally and creates the Standard dashboard (built-in cards only).

| Frontend card (HACS → Frontend) | Used for | Without it |
|---|---|---|
| [Mushroom](https://github.com/piitaya/lovelace-mushroom) | Whole Enhanced layout | Standard dashboard is used |
| [ApexCharts card](https://github.com/RomRider/apexcharts-card) | Room temperature chart | Chart is skipped |
| [mini-graph-card](https://github.com/kalkih/mini-graph-card) | Room sensors chart | Built-in history graph is used |
| [Scheduler card](https://github.com/nielsfaber/scheduler-card) **+** [Scheduler component](https://github.com/nielsfaber/scheduler-component) (integration) | *Schedule* view (Comfort/Eco by time) | View is hidden |

Install: **HACS → search the name → Download**, then reload the browser (Ctrl+F5). The Scheduler component also needs
*Settings → Devices & services → Add integration → Scheduler* and a restart.
Install the cards **before** creating the dashboard, or recreate it afterwards (*Configure → Dashboard → Recreate*).

## 1. Install Better Thermostat (required)

1. **HACS → Integrations →** search **Better Thermostat** → **Download** → restart Home Assistant.
2. **Settings → Devices & services → Add integration → Better Thermostat**, once per room:
   - **Name:** the room (e.g. `BT_Living room`).
   - **Temperature sensor:** the room sensor.
   - **Thermostat (TRV):** the valve(s) of the room. A room with two radiators uses **one** Better Thermostat with both valves.
   - **Window sensor:** optional.
   - **Cooler:** leave **empty**. A cooler switches the thermostat to a heat/cool range and Aquecimento Ninjas cannot set a single target.
3. Advanced settings (recommended):

   | Setting | Value |
   |---|---|
   | Calibration type | **Offset Based** (if your TRV supports a temperature offset) |
   | Calibration mode | **External Sensor Offset Only** |

## 2. Install Aquecimento Ninjas

### HACS (recommended)
1. **HACS → ⋮ → Custom repositories** → URL `https://github.com/noesisaoliveira/aquecimento_ninjas`, type **Integration**.
2. Search **Aquecimento Ninjas** → **Download** → restart Home Assistant.

### Manual
Copy `custom_components/aquecimento_ninjas` to `/config/custom_components/` and restart.

## 3. Setup wizard

**Settings → Devices & services → Add integration → Aquecimento Ninjas**

| Step | What you choose |
|---|---|
| 1. Name | Name and boiler thermostat: *use existing* or *create* |
| 2. Boiler | Existing: the climate entity (+ optional relay for statistics). Create: the relay, tolerances and minimum cycle (5 min recommended) |
| 3. Rooms | Per room: name, Better Thermostat, its valves, room sensor, optional battery and window sensors. Repeat until all rooms are added (max 5 valves) |
| 4. Presence | People for away mode, delay, notification service (`notify.mobile_app_…`), window/battery notifications |
| 5. Dashboard | Create dashboard, its title and style (Automatic / Enhanced / Standard) |

Change anything later in **Settings → Devices & services → Aquecimento Ninjas → Configure**.

### Using an existing boiler thermostat
Set its target sensor to the integration's **Reference temperature** sensor, e.g. for `generic_thermostat`:

```yaml
climate:
  - platform: generic_thermostat
    name: Boiler
    heater: switch.boiler_relay
    target_sensor: sensor.aquecimento_reference_temperature   # check the exact entity id
    min_cycle_duration:
      minutes: 5
```

## Entities

| Entity | Purpose |
|---|---|
| `switch.*_heating_on` | Master switch |
| `select.*_mode` | Eco / Comfort |
| `switch.*_away_mode`, `number.*_away_temperature` | Away mode and its temperature |
| `number.*_<room>_comfort`, `number.*_<room>_eco` | Room temperatures |
| `switch.*_<room>_use_for_boiler` | Room used by the boiler reference (first room by default) |
| `sensor.*_reference_temperature` | Average of the selected rooms → boiler |
| `sensor.*_average/minimum/maximum_temperature`, `sensor.*_warmest_to_coldest_room` | House statistics |
| `sensor.*_boiler_on_today`, `…_boiler_cycles_today`, `…_boiler_average_cycle` | Boiler statistics |
| `climate.*_boiler` | Only when the integration creates the boiler thermostat |
| `switch.*_boost`, `sensor.*_boost_ends` | Boost on/off and when it ends |
| `binary_sensor.*_<room>_window_open` | Room paused by an open window (reason: contact or temperature) |
| `binary_sensor.*_<room>_sensor_problem` | Sensor unavailable or silent for 3 h → emergency mode |
| `binary_sensor.*_<room>_not_heating` | 1 °C or more below target for 2 h |
| `switch.*_window_detection_by_temperature_drop` | Turns the sensor-less window detection on/off |
| `number.*_boost_duration`, `number.*_boost_temperature`, `switch.*_<room>_boost` | Boost settings and rooms |

Entity ids depend on the name you choose and the Home Assistant language.

## How it works

Priority (highest first):

1. **Master switch off** → boiler and all rooms *off*. Turning one back to *heat* is undone.
2. **Away mode on** → every room at the away temperature.
3. **Mode Comfort / Eco** → every room at its comfort / eco temperature.

The integration re-applies the targets on every change and every 30 minutes, removes Better Thermostat presets
(they would override the target), and turns a room back to *heat* if the master switch is on.

## Windows, reliability and diagnostics

**Open window – automatic pause and resume** (works with any valve):
- *With a window sensor:* open for 10 s → the room is turned off; closed for 10 s → back to the right temperature.
- *Without a sensor:* if the room temperature drops 1 °C or more within 5 minutes while heating, the room is paused.
  It resumes when the temperature stops falling (at least 15 min, at most 60 min).
  Turn it off with the *Window detection by temperature drop* switch.

**Verified commands:** after every command the integration checks after 90 s that the valve applied it and resends
up to 3 times. Failures are counted in the `command_failures` attribute of *not heating*.

**Emergency mode:** if a room sensor is unavailable or silent for 3 h, the room is left out of the boiler average and
kept at its eco temperature until the sensor is back. If no reference room has a valid sensor, the boiler thermostat
created by the integration turns the boiler off.

**Room not heating:** on when the room is 1 °C or more below target for 2 hours in a row
(weak boiler, unbalanced radiator or stuck valve).

**Diagnostics download:** *Settings → Devices & services → Aquecimento Ninjas → ⋮ → Download diagnostics*.
Includes the configuration, each room's state and the latest readings. Attach it to GitHub issues.

## Boost

Select the rooms (`<room> boost` switches), set duration and temperature, then turn on **Boost** or call
`aquecimento_ninjas.start_boost` (optional `hours`, `temperature`). During the boost:
- the selected rooms and the boiler heat to the boost temperature, other rooms are off;
- the boiler reads only the selected rooms;
- Comfort/Eco, away mode and "change on the thermostat" are paused.

When it ends (or `aquecimento_ninjas.stop_boost`), the previous state is restored. Turning the master switch off cancels it.
A running boost survives a Home Assistant restart.

## Dashboard

Created at `/aquecimento-ninjas`. Two styles (*Configure → Dashboard → Style*):

| Style | Views | Needs |
|---|---|---|
| **Enhanced** | Heating (with Boost), Schedule\*, Maintenance, Charts | [Mushroom](https://github.com/piitaya/lovelace-mushroom). Optional: [ApexCharts](https://github.com/RomRider/apexcharts-card), [mini-graph](https://github.com/kalkih/mini-graph-card), [Scheduler card](https://github.com/nielsfaber/scheduler-card) + Scheduler component |
| **Standard** | Heating, Charts | Nothing (built-in cards) |
| **Automatic** (default) | Enhanced when Mushroom is installed, otherwise Standard | |

\* The *Schedule* view appears only when the Scheduler card and the Scheduler integration are installed; it schedules the Comfort/Eco mode.

It is a normal dashboard: you can edit it.
- **Recreate** (overwrites edits): *Configure → Dashboard → Recreate*, or action `aquecimento_ninjas.create_dashboard`.
- Room changes in *Configure → Rooms* recreate it automatically.
- The dashboard uses internal Home Assistant APIs. If a future Home Assistant version changes them, the heating keeps
  working and a warning is logged; create the dashboard manually in that case.

## Updates

HACS shows an update when a new **GitHub release** is published. See [CHANGELOG.md](../CHANGELOG.md).

## Troubleshooting

| Problem | Check |
|---|---|
| Wizard says Better Thermostat is missing | Install and configure Better Thermostat first, restart |
| A room shows two targets (e.g. 16 / 23) | A cooler is configured in its Better Thermostat → remove it |
| A room does not follow Comfort/Eco | Master switch on? Away mode off? See *Settings → System → Logs* |
| Boiler never fires | Existing thermostat: is its target sensor the reference sensor? Created: is the relay correct? |
| Dashboard missing | Check the log; run `aquecimento_ninjas.create_dashboard` |
| A room stops for no reason | Check *window open* (reason `temperature`): turn off *Window detection by temperature drop* if draughts trigger it |
| Room at eco temperature in Comfort mode | *Sensor problem* is on: the room sensor is not reporting (battery, range) |


## License

[MIT](../LICENSE)
