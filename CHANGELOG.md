# Changelog

## 1.7.1 – 2026-11-27

- Valve communication in the Maintenance panel: each room shows when the last command was sent to its thermostat (and whether it was confirmed) and when each of its valves last reported to Home Assistant. New diagnostic sensor "<room> last command". Rooms without battery or window sensors now also appear in that section.
- The same section also shows, per room, the target the rules ask for and why (comfort, eco, manual, away, boost, window paused, sensor not reporting...), the room sensor reading and age, and the thermostat state, to explain valves that go idle before the room reaches the target.

## 1.7.0 – 2026-11-27

- Fix the "Boiler - hours on per day" chart repeating the previous day's value on the day after: the on-time sensor is now a resetting total and the chart shows each day's own hours. Recreate the dashboard to update the chart; Home Assistant may ask to reset the old statistics of the sensor (Settings > Repairs).
- Add a "Slow temperature sensors" option (Automation behavior): for room sensors that only report when the temperature changes, a sensor is treated as failed after 8 h without readings instead of 3 h, so the room is not switched to eco by mistake.

## 1.6.1 – 2026-11-24

- The emergency button now also turns the heating on: the boiler shows On and every valve is sent the boiler target temperature. When it ends, heating and valves go back to what they were before. Turning the heating off during an emergency ends it.
- During an emergency, changing the target on the boiler card sends it to every valve.

## 1.6.0 – 2026-11-24

- Add a Manual mode to the mode selector: the target set on the boiler card is applied to every valve, and turning the boiler on or off on that card turns the heating on or off. Slider sync and Schedule changes are ignored while in Manual.

## 1.5.3 – 2026-11-24

- Turning the emergency boiler off no longer asks for the PIN; only turning it on does.
- The emergency maximum duration can be set down to 0.1 h in steps of 0.1 h.

## 1.5.2 – 2026-11-24

- Turning the heating on no longer waits for the boiler minimum cycle (up to 5 minutes) before switching the boiler on.

## 1.5.1 – 2026-11-23

- Fix the integration failing to set up on recent Home Assistant versions (removed `STATE_ALARM_*` constants in the emergency panel).
- Load the platform modules in the executor to avoid the blocking `import_module` warning.

## 1.5.0 – 2026-11-23

- Add an emergency button to the Maintenance panel that turns the boiler on regardless of any temperature sensor. It asks for a numeric PIN (4-8 digits) set in Settings > Boiler, stops by itself after a configurable time (default 2 h), and locks for 5 minutes after 5 wrong PINs. Without a PIN the button is not shown.
- Fix the Schedule entity mode switching failing when the entity turns off (missing imports).

## 1.4.2 – 2026-11-20

- When heating is turned on, the boiler setpoint is set to the highest room target of the current mode (Comfort or Eco); it can still be changed afterwards.

## 1.4.0 – 2026-11-19

- Add a scheduler type option: the existing Scheduler card or a Home Assistant Schedule entity.
- A selected Schedule entity maps active to Comfort and inactive to Eco; the dashboard shows the selected helper.

## 1.3.1 – 2026-11-19

- Add an optional maximum heating runtime, disabled by default, with a configurable 10-minute warning notification.
- Persist the heating cycle start and warning state across Home Assistant restarts.

## 1.3.0 – 2026-11-19

- Add individual controls for the former `aquecimento_*` YAML automations in setup and integration options.
- Make apply interval, thermostat verification delay/retries, daily battery-check time, and window detection/pause timings configurable.
- Keep the low-battery threshold configurable (20% by default).

## 1.2.0 – 2026-11-15

- **Open window pause/resume** for any valve: contact sensors (10 s debounce) or a fast temperature drop
  (≥ 1 °C in 5 min). New entities: `<room> window open`, switch *Window detection by temperature drop*.
- **Verified commands**: room thermostat commands are checked after 90 s and resent up to 3 times.
- **Emergency mode** when a room sensor is unavailable or silent for 3 h: room at eco temperature, left out of the
  boiler reference; the created boiler thermostat turns the boiler off without a valid reference.
- **Diagnostics**: `<room> sensor problem`, `<room> not heating` (≥ 1 °C below target for 2 h), notifications,
  and *Download diagnostics*.
- Dashboard: Diagnostics card (Standard) and Maintenance view always present (Enhanced).

After updating, recreate the dashboard: *Configure → Dashboard → Recreate*.

## 1.1.0 – 2026-11-15

- **Boost**: heat selected rooms to a boost temperature for 30 min–6 h, other rooms off, previous state restored at the end.
  New entities: Boost switch, Boost ends sensor, Boost duration/temperature, per-room boost switches.
  New actions: `aquecimento_ninjas.start_boost`, `aquecimento_ninjas.stop_boost`.
- **Enhanced dashboard** (Mushroom): views Heating, Schedule (Scheduler card), Maintenance and Charts
  (ApexCharts and mini-graph when installed). New option *Dashboard style*: Automatic / Enhanced / Standard.
- Standard dashboard now also shows the Boost.

After updating, recreate the dashboard: *Configure → Dashboard → Recreate*.

## 1.0.1 – 2026-11-09

- Integration icon (`brand/icon.png`, `brand/icon@2x.png`) for Home Assistant and the HACS Marketplace.

## 1.0.0 – 2026-11-09

First release.

- Setup wizard: boiler (existing or created thermostat), up to 5 valves in rooms with Better Thermostat, presence, notifications, dashboard.
- Master switch, Comfort/Eco mode, away mode with away temperature.
- Target changed on a room thermostat becomes the room's comfort/eco value.
- Boiler reference temperature from selected rooms (average).
- House and boiler statistics sensors.
- Automatic dashboard with views Heating and Charts; `aquecimento_ninjas.create_dashboard` action.
- Portuguese and English.
