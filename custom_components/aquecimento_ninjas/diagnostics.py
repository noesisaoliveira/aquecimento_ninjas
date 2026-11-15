"""Diagnostics download (Device → ⋮ → Download diagnostics)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AquecimentoConfigEntry
from .const import CONF_NOTIFY, VERSION

TO_REDACT = {CONF_NOTIFY}


def _state(hass: HomeAssistant, entity_id: str | None) -> dict[str, Any] | None:
    state = hass.states.get(entity_id) if entity_id else None
    if state is None:
        return None
    return {
        "state": state.state,
        "attributes": {
            k: v
            for k, v in state.attributes.items()
            if k in (
                "temperature", "current_temperature", "hvac_action", "preset_mode",
                "target_temp_low", "target_temp_high", "unit_of_measurement",
            )
        },
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AquecimentoConfigEntry
) -> dict[str, Any]:
    c = entry.runtime_data
    reference, reference_rooms = c.reference()
    rooms = []
    for room in c.rooms:
        rt = c.runtime[room.id]
        rooms.append(
            {
                "name": room.name,
                "climate": _state(hass, room.climate),
                "sensor": _state(hass, room.sensor),
                "valves": {v: _state(hass, v) for v in room.valves},
                "windows": {w: _state(hass, w) for w in room.windows},
                "batteries": {b: _state(hass, b) for b in room.batteries},
                "comfort": c.comfort[room.id].native_value if room.id in c.comfort else None,
                "eco": c.eco[room.id].native_value if room.id in c.eco else None,
                "use_for_boiler": bool(s.is_on) if (s := c.use_for_boiler.get(room.id)) else None,
                "boost_selected": c.boost_selected(room),
                "runtime": {
                    "paused": rt.paused,
                    "pause_reason": rt.pause_reason,
                    "sensor_failed": rt.sensor_failed,
                    "sensor_age_hours": rt.sensor_age_hours,
                    "not_heating": rt.not_heating,
                    "command_failures": rt.command_failures,
                    "pending_command": rt.desired,
                    "recent_readings": [(t.isoformat(), v) for t, v in list(rt.readings)[-10:]],
                },
            }
        )
    return {
        "version": VERSION,
        "config": async_redact_data({**entry.data, **entry.options}, TO_REDACT),
        "state": {
            "master_on": c.master_on,
            "away_on": c.away_on,
            "comfort_mode": c.comfort_mode,
            "boost_until": c.boost_until.isoformat() if c.boost_until else None,
            "reference": reference,
            "reference_rooms": reference_rooms,
            "boiler": _state(hass, c.boiler_climate_id),
            "boiler_switch": _state(hass, c.boiler_switch_id),
            "stats": {"on_hours": c.stats.on_hours, "cycles": c.stats.cycles},
        },
        "rooms": rooms,
    }
