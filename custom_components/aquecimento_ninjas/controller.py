"""Heating logic for Aquecimento Ninjas."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    APPLY_INTERVAL_MINUTES,
    BOILER_CREATE,
    CONF_AWAY_DELAY,
    CONF_BATTERY_THRESHOLD,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_MODE,
    CONF_BOILER_SWITCH,
    CONF_NOTIFY,
    CONF_NOTIFY_BATTERY,
    CONF_NOTIFY_WINDOWS,
    CONF_PERSONS,
    CONF_ROOM_BATTERIES,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_SENSOR,
    CONF_ROOM_VALVES,
    CONF_ROOM_WINDOWS,
    CONF_ROOMS,
    DEFAULT_AWAY_DELAY,
    DEFAULT_BATTERY_THRESHOLD,
    MASTER_SETTLE_SECONDS,
    MAX_TEMP,
    MIN_TEMP,
    MODE_COMFORT,
    SIGNAL_STATS,
    SIGNAL_TEMPERATURES,
    SUPPRESS_SECONDS,
)

if TYPE_CHECKING:
    from .climate import BoilerThermostat
    from .number import TemperatureNumber
    from .select import ModeSelect
    from .switch import AquecimentoSwitch

_LOGGER = logging.getLogger(__name__)

_INVALID = (STATE_UNAVAILABLE, STATE_UNKNOWN)

_MESSAGES = {
    "en": {
        "window_title": "Heating",
        "window": "Window open in {room}. Heating paused on that valve.",
        "battery_title": "Heating - battery",
        "battery_low": "Low battery: {names}",
    },
    "pt": {
        "window_title": "Aquecimento",
        "window": "Janela aberta em {room}. Aquecimento em pausa nessa válvula.",
        "battery_title": "Aquecimento - bateria",
        "battery_low": "Bateria fraca: {names}",
    },
}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _state_float(state: State | None) -> float | None:
    if state is None or state.state in _INVALID:
        return None
    return _as_float(state.state)


@dataclass
class Room:
    """A heated room: one Better Thermostat climate with 1+ valves."""

    id: str
    name: str
    climate: str
    sensor: str
    valves: list[str] = field(default_factory=list)
    batteries: list[str] = field(default_factory=list)
    windows: list[str] = field(default_factory=list)


class BoilerStats:
    """Daily boiler on-time and cycle counter."""

    def __init__(self) -> None:
        self.on_seconds = 0.0
        self.cycles = 0
        self._since: datetime | None = None

    def start(self, is_on: bool) -> None:
        self._since = dt_util.utcnow() if is_on else None

    def update(self, is_on: bool) -> bool:
        now = dt_util.utcnow()
        if is_on and self._since is None:
            self.cycles += 1
            self._since = now
            return True
        if not is_on and self._since is not None:
            self.on_seconds += (now - self._since).total_seconds()
            self._since = None
            return True
        return False

    def reset(self) -> None:
        self.on_seconds = 0.0
        self.cycles = 0
        if self._since is not None:
            self._since = dt_util.utcnow()

    @property
    def total_seconds(self) -> float:
        running = (dt_util.utcnow() - self._since).total_seconds() if self._since else 0.0
        return self.on_seconds + running

    @property
    def on_hours(self) -> float:
        return round(self.total_seconds / 3600, 2)

    @property
    def average_cycle_minutes(self) -> float:
        return round(self.total_seconds / 60 / self.cycles, 1) if self.cycles else 0.0


class HeatingController:
    """Applies the heating rules to the Better Thermostat climates and the boiler."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config: dict[str, Any] = {**entry.data, **entry.options}
        self.rooms: list[Room] = [
            Room(
                id=r[CONF_ROOM_ID],
                name=r[CONF_ROOM_NAME],
                climate=r[CONF_ROOM_CLIMATE],
                sensor=r[CONF_ROOM_SENSOR],
                valves=list(r.get(CONF_ROOM_VALVES, [])),
                batteries=list(r.get(CONF_ROOM_BATTERIES, [])),
                windows=list(r.get(CONF_ROOM_WINDOWS, [])),
            )
            for r in self.config.get(CONF_ROOMS, [])
        ]
        self.lang = "pt" if (hass.config.language or "").startswith("pt") else "en"
        self.unique_ids: set[str] = set()

        self.master: AquecimentoSwitch | None = None
        self.away: AquecimentoSwitch | None = None
        self.mode: ModeSelect | None = None
        self.away_temperature: TemperatureNumber | None = None
        self.comfort: dict[str, TemperatureNumber] = {}
        self.eco: dict[str, TemperatureNumber] = {}
        self.use_for_boiler: dict[str, AquecimentoSwitch] = {}
        self.boiler_entity: BoilerThermostat | None = None

        self.stats = BoilerStats()
        self._lock = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._away_timer: CALLBACK_TYPE | None = None
        self._settle_timer: CALLBACK_TYPE | None = None
        self._suppress_until = 0.0
        self._was_home: bool | None = None
        self._range_warned: set[str] = set()

    # ---------- configuration helpers ----------

    @property
    def signal_temperatures(self) -> str:
        return f"{SIGNAL_TEMPERATURES}_{self.entry.entry_id}"

    @property
    def signal_stats(self) -> str:
        return f"{SIGNAL_STATS}_{self.entry.entry_id}"

    @property
    def creates_boiler(self) -> bool:
        return self.config.get(CONF_BOILER_MODE) == BOILER_CREATE

    @property
    def boiler_climate_id(self) -> str | None:
        if self.creates_boiler:
            return self.boiler_entity.entity_id if self.boiler_entity else None
        return self.config.get(CONF_BOILER_CLIMATE)

    @property
    def boiler_switch_id(self) -> str | None:
        return self.config.get(CONF_BOILER_SWITCH) or None

    @property
    def persons(self) -> list[str]:
        return list(self.config.get(CONF_PERSONS) or [])

    @property
    def master_on(self) -> bool:
        return self.master.is_on if self.master else True

    @property
    def away_on(self) -> bool:
        return bool(self.away and self.away.is_on)

    @property
    def comfort_mode(self) -> bool:
        return bool(self.mode and self.mode.current_option == MODE_COMFORT)

    def room_by_climate(self, entity_id: str) -> Room | None:
        return next((r for r in self.rooms if r.climate == entity_id), None)

    # ---------- temperatures ----------

    def room_temperature(self, room: Room) -> float | None:
        return _state_float(self.hass.states.get(room.sensor))

    def room_temperatures(self) -> list[float]:
        return [t for r in self.rooms if (t := self.room_temperature(r)) is not None]

    def reference(self) -> tuple[float | None, list[str]]:
        """Average of rooms marked 'use for boiler'; first room as fallback."""
        used = [
            (r.name, t)
            for r in self.rooms
            if (switch := self.use_for_boiler.get(r.id)) is not None
            and switch.is_on
            and (t := self.room_temperature(r)) is not None
        ]
        if not used:
            used = [
                (r.name, t)
                for r in self.rooms[:1]
                if (t := self.room_temperature(r)) is not None
            ]
        if not used:
            return None, []
        value = round(sum(t for _, t in used) / len(used), 1)
        return value, [name for name, _ in used]

    @callback
    def notify_temperatures(self) -> None:
        async_dispatcher_send(self.hass, self.signal_temperatures)

    # ---------- lifecycle ----------

    @callback
    def async_start(self) -> None:
        self._unsubs.append(async_at_started(self.hass, self._async_on_started))

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for timer in (self._away_timer, self._settle_timer):
            if timer:
                timer()
        self._away_timer = self._settle_timer = None

    async def _async_on_started(self, hass: HomeAssistant) -> None:
        track = self._unsubs.append

        sensors = [r.sensor for r in self.rooms]
        track(async_track_state_change_event(hass, sensors, self._on_room_sensor))

        climates = [r.climate for r in self.rooms]
        if not self.creates_boiler and self.boiler_climate_id:
            climates.append(self.boiler_climate_id)
        track(async_track_state_change_event(hass, climates, self._on_climate_change))

        if self.persons:
            track(async_track_state_change_event(hass, self.persons, self._on_person_change))

        windows = [w for r in self.rooms for w in r.windows]
        if windows:
            track(async_track_state_change_event(hass, windows, self._on_window_change))

        batteries = [b for r in self.rooms for b in r.batteries]
        if batteries:
            track(async_track_state_change_event(hass, batteries, self._on_battery_change))
            track(async_track_time_change(hass, self._daily_battery_check, hour=9, minute=0, second=0))

        source = self._stats_source()
        if source:
            self.stats.start(self._stats_is_on(hass.states.get(source)))
            track(async_track_state_change_event(hass, [source], self._on_stats_source))
        track(async_track_time_change(hass, self._midnight, hour=0, minute=0, second=0))
        track(async_track_time_interval(hass, self._stats_tick, timedelta(minutes=1)))

        track(
            async_track_time_interval(
                hass, self._periodic_apply, timedelta(minutes=APPLY_INTERVAL_MINUTES)
            )
        )

        self._was_home = self._anyone_home() if self.persons else None
        if self._was_home is False:
            self._start_away_timer()

        await self.async_master_changed()

    # ---------- service helpers ----------

    async def _call(self, domain: str, service: str, entity_id: str | None, **data: Any) -> None:
        if entity_id:
            data["entity_id"] = entity_id
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("%s.%s on %s failed: %s", domain, service, entity_id, err)

    def _mark_own_change(self) -> None:
        self._suppress_until = time.monotonic() + SUPPRESS_SECONDS

    async def _notify(self, title: str, message: str) -> None:
        service = (self.config.get(CONF_NOTIFY) or "").strip()
        if not service:
            return
        domain, _, name = service.partition(".")
        await self._call(domain, name, None, title=title, message=message)

    def _msg(self, key: str, **kwargs: Any) -> str:
        return _MESSAGES[self.lang][key].format(**kwargs)

    # ---------- apply rules ----------

    @callback
    def request_apply(self) -> None:
        self.hass.async_create_task(self.async_apply())

    @callback
    def _periodic_apply(self, _now: datetime) -> None:
        self.request_apply()

    def _room_target(self, room: Room) -> float | None:
        number = (self.comfort if self.comfort_mode else self.eco).get(room.id)
        return number.native_value if number else None

    def _away_target(self, room: Room) -> float | None:
        return self.away_temperature.native_value if self.away_temperature else None

    async def async_apply(self) -> None:
        """Send the right target temperature to every room thermostat."""
        async with self._lock:
            if not self.master_on:
                return
            target_fn = self._away_target if self.away_on else self._room_target
            for room in self.rooms:
                await self._apply_room(room, target_fn(room))

    async def _apply_room(self, room: Room, target: float | None) -> None:
        state = self.hass.states.get(room.climate)
        if state is None or state.state in _INVALID or target is None:
            return
        self._mark_own_change()
        attrs = state.attributes
        if state.state == HVACMode.OFF:
            await self._call("climate", "set_hvac_mode", room.climate, hvac_mode=HVACMode.HEAT)
        preset = attrs.get("preset_mode")
        if preset not in (None, "none") and "none" in (attrs.get("preset_modes") or []):
            await self._call("climate", "set_preset_mode", room.climate, preset_mode="none")
        if attrs.get("temperature") is None and attrs.get("target_temp_low") is not None:
            if room.id not in self._range_warned:
                self._range_warned.add(room.id)
                _LOGGER.warning(
                    "%s uses a heat/cool range (a cooler is configured in Better Thermostat). "
                    "Remove the cooler so Aquecimento Ninjas can set a single target",
                    room.climate,
                )
            return
        if _as_float(attrs.get("temperature")) != target:
            await self._call("climate", "set_temperature", room.climate, temperature=target)

    async def async_master_changed(self) -> None:
        """Master switch: heat or off for boiler and every room."""
        mode = HVACMode.HEAT if self.master_on else HVACMode.OFF
        self._mark_own_change()
        await self._set_boiler_mode(mode)
        for room in self.rooms:
            state = self.hass.states.get(room.climate)
            if state is not None and state.state not in _INVALID and state.state != mode:
                await self._call("climate", "set_hvac_mode", room.climate, hvac_mode=mode)
        if self._settle_timer:
            self._settle_timer()
            self._settle_timer = None
        if mode == HVACMode.HEAT:
            self._settle_timer = async_call_later(
                self.hass, MASTER_SETTLE_SECONDS, self._after_master_on
            )

    @callback
    def _after_master_on(self, _now: datetime) -> None:
        self._settle_timer = None
        self.request_apply()

    async def _set_boiler_mode(self, mode: HVACMode) -> None:
        if self.boiler_entity is not None:
            await self.boiler_entity.async_set_hvac_mode(mode)
            return
        climate = self.boiler_climate_id
        state = self.hass.states.get(climate) if climate else None
        if state is not None and state.state not in _INVALID and state.state != mode:
            await self._call("climate", "set_hvac_mode", climate, hvac_mode=mode)

    # ---------- event handlers ----------

    @callback
    def _on_room_sensor(self, event: Event[EventStateChangedData]) -> None:
        self.notify_temperatures()

    @callback
    def _on_climate_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None:
            return
        if not self.master_on:
            if new.state == HVACMode.HEAT and (old is None or old.state != HVACMode.HEAT):
                self.hass.async_create_task(
                    self._call("climate", "set_hvac_mode", entity_id, hvac_mode=HVACMode.OFF)
                )
            return
        room = self.room_by_climate(entity_id)
        if room is not None and old is not None:
            self._sync_slider(room, old, new)

    def _sync_slider(self, room: Room, old: State, new: State) -> None:
        """A target changed on the room thermostat becomes the new comfort/eco value."""
        if self.away_on or time.monotonic() < self._suppress_until:
            return
        if new.state != HVACMode.HEAT or new.attributes.get("preset_mode") not in (None, "none"):
            return
        old_t = _as_float(old.attributes.get("temperature"))
        new_t = _as_float(new.attributes.get("temperature"))
        if old_t is None or new_t is None or old_t == new_t:
            return
        number = (self.comfort if self.comfort_mode else self.eco).get(room.id)
        value = min(max(new_t, MIN_TEMP), MAX_TEMP)
        if number is not None and number.native_value != value:
            self.hass.async_create_task(number.async_set_native_value(value))

    # ---------- presence ----------

    def _anyone_home(self) -> bool:
        return any(self.hass.states.is_state(p, STATE_HOME) for p in self.persons)

    def _start_away_timer(self) -> None:
        if self._away_timer or self.away_on:
            return
        delay = int(self.config.get(CONF_AWAY_DELAY, DEFAULT_AWAY_DELAY)) * 60
        self._away_timer = async_call_later(self.hass, delay, self._away_timeout)

    @callback
    def _away_timeout(self, _now: datetime) -> None:
        self._away_timer = None
        if self.away is not None and not self._anyone_home() and not self.away_on:
            self.hass.async_create_task(self.away.async_turn_on())

    @callback
    def _on_person_change(self, event: Event[EventStateChangedData]) -> None:
        home = self._anyone_home()
        if home == self._was_home:
            return
        self._was_home = home
        if home:
            if self._away_timer:
                self._away_timer()
                self._away_timer = None
            if self.away is not None and self.away_on:
                self.hass.async_create_task(self.away.async_turn_off())
        else:
            self._start_away_timer()

    # ---------- windows and batteries ----------

    @callback
    def _on_window_change(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if not self.config.get(CONF_NOTIFY_WINDOWS, True) or new is None:
            return
        if new.state != STATE_ON or (old is not None and old.state == STATE_ON):
            return
        room = next((r for r in self.rooms if event.data["entity_id"] in r.windows), None)
        name = room.name if room else new.name
        self.hass.async_create_task(
            self._notify(self._msg("window_title"), self._msg("window", room=name))
        )

    def _battery_threshold(self) -> float:
        return float(self.config.get(CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD))

    @callback
    def _on_battery_change(self, event: Event[EventStateChangedData]) -> None:
        if not self.config.get(CONF_NOTIFY_BATTERY, True):
            return
        new_v = _state_float(event.data["new_state"])
        old_v = _state_float(event.data["old_state"])
        limit = self._battery_threshold()
        if new_v is None or new_v >= limit or (old_v is not None and old_v < limit):
            return
        name = f"{event.data['new_state'].name} ({new_v:.0f}%)"
        self.hass.async_create_task(
            self._notify(self._msg("battery_title"), self._msg("battery_low", names=name))
        )

    @callback
    def _daily_battery_check(self, _now: datetime) -> None:
        if not self.config.get(CONF_NOTIFY_BATTERY, True):
            return
        limit = self._battery_threshold()
        low = []
        for entity_id in (b for r in self.rooms for b in r.batteries):
            state = self.hass.states.get(entity_id)
            value = _state_float(state)
            if state is not None and value is not None and value < limit:
                low.append(f"{state.name} ({value:.0f}%)")
        if low:
            self.hass.async_create_task(
                self._notify(self._msg("battery_title"), self._msg("battery_low", names=", ".join(low)))
            )

    # ---------- boiler statistics ----------

    def _stats_source(self) -> str | None:
        return self.boiler_switch_id or self.boiler_climate_id

    @staticmethod
    def _stats_is_on(state: State | None) -> bool:
        if state is None:
            return False
        if state.domain == "climate":
            return state.attributes.get("hvac_action") == HVACAction.HEATING
        return state.state == STATE_ON

    @callback
    def _on_stats_source(self, event: Event[EventStateChangedData]) -> None:
        if self.stats.update(self._stats_is_on(event.data["new_state"])):
            async_dispatcher_send(self.hass, self.signal_stats)

    @callback
    def _stats_tick(self, _now: datetime) -> None:
        async_dispatcher_send(self.hass, self.signal_stats)

    @callback
    def _midnight(self, _now: datetime) -> None:
        self.stats.reset()
        async_dispatcher_send(self.hass, self.signal_stats)
