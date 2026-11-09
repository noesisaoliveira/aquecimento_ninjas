# Aquecimento Ninjas

Per-room radiator heating for Home Assistant, built on **Better Thermostat**.
Up to **5 radiator valves (TRVs)**, a setup wizard, and an automatically created dashboard with charts.

🇵🇹 **Documentação em português:** [docs/README.pt.md](docs/README.pt.md)

---

## Features

- **Master switch** – turns the boiler and every room on/off. *Off* has priority over everything.
- **Comfort / Eco mode** – one selector for the whole house; each room has its own comfort and eco temperature.
- **Change on the thermostat = new setting** – changing a room's target on its thermostat card (or the valve knob)
  saves it as that room's comfort or eco temperature.
- **Away mode** – automatic when everyone has been away for a configurable time, or manual; uses an away temperature.
- **Boiler reference rooms** – choose which rooms the boiler thermostat reads; with two or more, it uses the average.
- **Boiler thermostat** – use an existing one (e.g. `generic_thermostat`) or let the integration create one.
- **Notifications** – open windows and low batteries.
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
1. **HACS → ⋮ → Custom repositories** → URL `https://github.com/YOUR_GITHUB_USER/aquecimento_ninjas`, type **Integration**.
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
| 5. Dashboard | Create dashboard and its title |

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

Entity ids depend on the name you choose and the Home Assistant language.

## How it works

Priority (highest first):

1. **Master switch off** → boiler and all rooms *off*. Turning one back to *heat* is undone.
2. **Away mode on** → every room at the away temperature.
3. **Mode Comfort / Eco** → every room at its comfort / eco temperature.

The integration re-applies the targets on every change and every 30 minutes, removes Better Thermostat presets
(they would override the target), and turns a room back to *heat* if the master switch is on.

## Dashboard

Created at `/aquecimento-ninjas` with the views **Heating** and **Charts**. It is a normal dashboard: you can edit it.
- **Recreate** (overwrites edits): *Configure → Dashboard → Recreate*, or action `aquecimento_ninjas.create_dashboard`.
- Room changes in *Configure → Rooms* recreate it automatically.
- The dashboard uses internal Home Assistant APIs. If a future Home Assistant version changes them, the heating keeps
  working and a warning is logged; create the dashboard manually in that case.

## Updates

HACS shows an update when a new **GitHub release** is published. See [CHANGELOG.md](CHANGELOG.md).

## Troubleshooting

| Problem | Check |
|---|---|
| Wizard says Better Thermostat is missing | Install and configure Better Thermostat first, restart |
| A room shows two targets (e.g. 16 / 23) | A cooler is configured in its Better Thermostat → remove it |
| A room does not follow Comfort/Eco | Master switch on? Away mode off? See *Settings → System → Logs* |
| Boiler never fires | Existing thermostat: is its target sensor the reference sensor? Created: is the relay correct? |
| Dashboard missing | Check the log; run `aquecimento_ninjas.create_dashboard` |

## For maintainers – publishing a release

1. Replace `YOUR_GITHUB_USER` in `manifest.json`, `const.py` and this README with your GitHub user/organisation.
2. Bump `version` in `custom_components/aquecimento_ninjas/manifest.json` **and** `VERSION` in `const.py`.
3. Add the changes to `CHANGELOG.md`.
4. Commit, then create a GitHub **release** with tag `vX.Y.Z` (same version). The *Release check* workflow verifies it.
5. Add the topics `home-assistant`, `hacs`, `integration` and a description to the repository (HACS requirement).

## License

[MIT](LICENSE)
