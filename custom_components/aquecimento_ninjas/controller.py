"""Heating logic for Aquecimento Ninjas."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
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
    CONF_APPLY_INTERVAL,
    CONF_BATTERY_CHECK_HOUR,
    CONF_BATTERY_CHECK_MINUTE,
    CONF_BATTERY_THRESHOLD,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_MODE,
    CONF_BOILER_SWITCH,
    CONF_ENABLE_AWAY_TARGET,
    CONF_ENABLE_MASTER,
    CONF_ENABLE_MODE_APPLY,
    CONF_ENABLE_PRESENCE,
    CONF_ENABLE_SLIDER_SYNC,
    CONF_ENABLE_WINDOWS,
    CONF_MAX_RUNTIME_HOURS,
    CONF_NOTIFY,
    CONF_NOTIFY_BATTERY,
    CONF_NOTIFY_NOT_HEATING,
    CONF_NOTIFY_RUNTIME_WARNING,
    CONF_NOTIFY_SENSOR_FAILURE,
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
    CONF_SCHEDULE_ENTITY,
    CONF_SCHEDULER_TYPE,
    CONF_MASTER_SETTLE_SECONDS,
    CONF_VERIFY_RETRIES,
    CONF_VERIFY_SECONDS,
    CONF_WINDOW_CONTACT_SECONDS,
    CONF_WINDOW_DROP_DEGREES,
    CONF_WINDOW_DROP_MINUTES,
    CONF_WINDOW_MAX_PAUSE_MINUTES,
    CONF_WINDOW_MIN_PAUSE_MINUTES,
    DEFAULT_AWAY_DELAY,
    DEFAULT_BATTERY_CHECK_HOUR,
    DEFAULT_BATTERY_CHECK_MINUTE,
    DEFAULT_BATTERY_THRESHOLD,
    DEFAULT_MAX_RUNTIME_HOURS,
    DOMAIN,
    MASTER_SETTLE_SECONDS,
    RUNTIME_WARNING_MINUTES,
    MAX_RETRIES,
    MAX_TEMP,
    MIN_TEMP,
    MODE_COMFORT,
    SCHEDULER_ENTITY,
    NOT_HEATING_DELTA,
    NOT_HEATING_HOURS,
    SENSOR_STALE_HOURS,
    SIGNAL_BOOST,
    SIGNAL_DIAGNOSTICS,
    SIGNAL_STATS,
    SIGNAL_TEMPERATURES,
    SUPPRESS_SECONDS,
    VERIFY_SECONDS,
    WINDOW_CONTACT_SECONDS,
    WINDOW_DROP_DEGREES,
    WINDOW_DROP_MINUTES,
    WINDOW_MAX_PAUSE_MINUTES,
    WINDOW_MIN_PAUSE_MINUTES,
)

if TYPE_CHECKING:
    from .climate import BoilerThermostat
    from .number import HelperNumber
    from .select import ModeSelect
    from .switch import AquecimentoSwitch, BoostSwitch

_LOGGER = logging.getLogger(__name__)

_INVALID = (STATE_UNAVAILABLE, STATE_UNKNOWN)

_MESSAGES = {
    "en": {
        "window_title": "Heating",
        "window": "Window open in {room}. Heating paused in that room.",
        "window_drop": "Temperature dropping fast in {room} (open window?). Heating paused.",
        "battery_title": "Heating - battery",
        "battery_low": "Low battery: {names}",
        "problem_title": "Heating - problem",
        "sensor_failed": "{room}: room sensor not reporting. Emergency mode: eco temperature.",
        "not_heating": "{room} is not reaching its target temperature for {hours} h.",
        "runtime_title": "Heating safety limit",
        "runtime_warning": "Heating will turn off in 10 minutes when it reaches the {hours} h runtime limit.",
    },
    "pt": {
        "window_title": "Aquecimento",
        "window": "Janela aberta em {room}. Aquecimento em pausa nessa divisão.",
        "window_drop": "A temperatura está a descer depressa em {room} (janela aberta?). Aquecimento em pausa.",
        "battery_title": "Aquecimento - bateria",
        "battery_low": "Bateria fraca: {names}",
        "problem_title": "Aquecimento - problema",
        "sensor_failed": "{room}: o sensor da divisão não está a enviar dados. Modo de emergência: temperatura eco.",
        "not_heating": "{room} não chega à temperatura pretendida há {hours} h.",
        "runtime_title": "Limite de segurança do aquecimento",
        "runtime_warning": "O aquecimento será desligado dentro de 10 minutos, quando atingir o limite de {hours} h ligado.",
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


@dataclass
class RoomRuntime:
    """Live state of a room: pending command, window pause and diagnostics."""

    readings: deque[tuple[datetime, float]] = field(default_factory=lambda: deque(maxlen=120))
    desired: dict[str, Any] | None = None
    verify_unsub: CALLBACK_TYPE | None = None
    command_failures: int = 0
    paused: bool = False
    pause_reason: str | None = None
    paused_since: datetime | None = None
    contact_unsub: CALLBACK_TYPE | None = None
    sensor_failed: bool = False
    sensor_age_hours: float | None = None
    not_heating: bool = False
    not_heating_since: datetime | None = None

    def cancel_timers(self) -> None:
        for unsub in (self.verify_unsub, self.contact_unsub):
            if unsub:
                unsub()
        self.verify_unsub = self.contact_unsub = None


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
        self.runtime: dict[str, RoomRuntime] = {r.id: RoomRuntime() for r in self.rooms}
        self.window_temperature_detection: AquecimentoSwitch | None = None

        self.master: AquecimentoSwitch | None = None
        self.away: AquecimentoSwitch | None = None
        self.mode: ModeSelect | None = None
        self.away_temperature: HelperNumber | None = None
        self.comfort: dict[str, HelperNumber] = {}
        self.eco: dict[str, HelperNumber] = {}
        self.use_for_boiler: dict[str, AquecimentoSwitch] = {}
        self.boiler_entity: BoilerThermostat | None = None

        self.boost_hours: HelperNumber | None = None
        self.boost_temperature: HelperNumber | None = None
        self.boost_rooms: dict[str, AquecimentoSwitch] = {}
        self.boost_switch: BoostSwitch | None = None
        self.boost_until: datetime | None = None
        self._boost_snapshot: dict[str, Any] | None = None
        self._boost_timer: CALLBACK_TYPE | None = None

        self.stats = BoilerStats()
        self._lock = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._away_timer: CALLBACK_TYPE | None = None
        self._settle_timer: CALLBACK_TYPE | None = None
        self._runtime_warning_timer: CALLBACK_TYPE | None = None
        self._runtime_limit_timer: CALLBACK_TYPE | None = None
        self._runtime_started_at: datetime | None = None
        self._runtime_warning_sent = False
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
    def signal_boost(self) -> str:
        return f"{SIGNAL_BOOST}_{self.entry.entry_id}"

    @property
    def signal_diagnostics(self) -> str:
        return f"{SIGNAL_DIAGNOSTICS}_{self.entry.entry_id}"

    @property
    def boost_active(self) -> bool:
        return self.boost_until is not None

    @property
    def max_runtime_started_at(self) -> datetime | None:
        return self._runtime_started_at

    @property
    def max_runtime_warning_sent(self) -> bool:
        return self._runtime_warning_sent

    def boost_selected(self, room: Room) -> bool:
        switch = self.boost_rooms.get(room.id)
        return bool(switch and switch.is_on)

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
        return self.master.is_on if self.master and self.config.get(CONF_ENABLE_MASTER, True) else True

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
        if self.runtime[room.id].sensor_failed:
            return None
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
        for timer in (
            self._away_timer,
            self._settle_timer,
            self._boost_timer,
            self._runtime_warning_timer,
            self._runtime_limit_timer,
        ):
            if timer:
                timer()
        self._away_timer = self._settle_timer = self._boost_timer = None
        self._runtime_warning_timer = self._runtime_limit_timer = None
        for rt in self.runtime.values():
            rt.cancel_timers()

    async def _async_on_started(self, hass: HomeAssistant) -> None:
        track = self._unsubs.append

        sensors = [r.sensor for r in self.rooms]
        track(async_track_state_change_event(hass, sensors, self._on_room_sensor))

        climates = [r.climate for r in self.rooms]
        if not self.creates_boiler and self.boiler_climate_id:
            climates.append(self.boiler_climate_id)
        track(async_track_state_change_event(hass, climates, self._on_climate_change))

        if self.persons and self.config.get(CONF_ENABLE_PRESENCE, True):
            track(async_track_state_change_event(hass, self.persons, self._on_person_change))

        windows = [w for r in self.rooms for w in r.windows]
        if windows and self.config.get(CONF_ENABLE_WINDOWS, True):
            track(async_track_state_change_event(hass, windows, self._on_window_change))

        schedule_entity = self.config.get(CONF_SCHEDULE_ENTITY)
        if (
            self.config.get(CONF_SCHEDULER_TYPE) == SCHEDULER_ENTITY
            and schedule_entity
        ):
            track(
                async_track_state_change_event(
                    hass, [schedule_entity], self._on_schedule_change
                )
            )
            self._apply_schedule_state(hass.states.get(schedule_entity))

        batteries = [b for r in self.rooms for b in r.batteries]
        if batteries and self.config.get(CONF_NOTIFY_BATTERY, True):
            track(async_track_state_change_event(hass, batteries, self._on_battery_change))
            track(async_track_time_change(
                hass,
                self._daily_battery_check,
                hour=int(self.config.get(CONF_BATTERY_CHECK_HOUR, DEFAULT_BATTERY_CHECK_HOUR)),
                minute=int(self.config.get(CONF_BATTERY_CHECK_MINUTE, DEFAULT_BATTERY_CHECK_MINUTE)),
                second=0,
            ))

        source = self._stats_source()
        if source:
            self.stats.start(self._stats_is_on(hass.states.get(source)))
            track(async_track_state_change_event(hass, [source], self._on_stats_source))
        track(async_track_time_change(hass, self._midnight, hour=0, minute=0, second=0))
        track(async_track_time_interval(hass, self._stats_tick, timedelta(minutes=1)))
        track(async_track_time_interval(hass, self._diagnostics_tick, timedelta(minutes=1)))

        now = dt_util.utcnow()
        for room in self.rooms:
            if (value := _state_float(hass.states.get(room.sensor))) is not None:
                self.runtime[room.id].readings.append((now, value))
            if self.config.get(CONF_ENABLE_WINDOWS, True) and any(
                hass.states.is_state(w, STATE_ON) for w in room.windows
            ):
                self._schedule_contact_check(room)
        self._diagnostics_tick(now)

        if self.config.get(CONF_ENABLE_MODE_APPLY, True) or self.config.get(
            CONF_ENABLE_AWAY_TARGET, True
        ):
            track(
                async_track_time_interval(
                    hass,
                    self._periodic_apply,
                    timedelta(minutes=int(self.config.get(CONF_APPLY_INTERVAL, APPLY_INTERVAL_MINUTES))),
                )
            )

        presence_enabled = self.config.get(CONF_ENABLE_PRESENCE, True)
        self._was_home = self._anyone_home() if self.persons and presence_enabled else None
        if self._was_home is False:
            self._start_away_timer()

        if self.boost_until is not None:
            if self.boost_until <= dt_util.utcnow():
                await self.async_stop_boost()
            else:
                self._schedule_boost_end()
            return

        if self.config.get(CONF_ENABLE_MASTER, True):
            await self.async_master_changed()
        else:
            self.request_apply()

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

    def restore_runtime_state(
        self, started_at: datetime | None, warning_sent: bool
    ) -> None:
        self._runtime_started_at = started_at
        self._runtime_warning_sent = warning_sent

    def _persist_runtime_state(self) -> None:
        if self.master is not None:
            self.master.async_write_ha_state()

    def _cancel_runtime_timers(self) -> None:
        for timer in (self._runtime_warning_timer, self._runtime_limit_timer):
            if timer:
                timer()
        self._runtime_warning_timer = self._runtime_limit_timer = None

    def _sync_runtime_limit(self) -> None:
        hours = float(self.config.get(CONF_MAX_RUNTIME_HOURS, DEFAULT_MAX_RUNTIME_HOURS))
        if self.master is None or not self.master.is_on or hours <= 0:
            self._cancel_runtime_timers()
            changed = self._runtime_started_at is not None or self._runtime_warning_sent
            self._runtime_started_at = None
            self._runtime_warning_sent = False
            if changed:
                self._persist_runtime_state()
            return

        now = dt_util.utcnow()
        if self._runtime_started_at is None:
            self._runtime_started_at = now
            self._runtime_warning_sent = False
            self._persist_runtime_state()

        self._cancel_runtime_timers()
        elapsed = max(0.0, (now - self._runtime_started_at).total_seconds())
        limit_seconds = hours * 3600
        remaining = max(0.0, limit_seconds - elapsed)
        self._runtime_limit_timer = async_call_later(
            self.hass, remaining, self._max_runtime_reached
        )

        if (
            self.config.get(CONF_NOTIFY_RUNTIME_WARNING, True)
            and not self._runtime_warning_sent
        ):
            warning_after = max(
                0.0, limit_seconds - RUNTIME_WARNING_MINUTES * 60 - elapsed
            )
            self._runtime_warning_timer = async_call_later(
                self.hass, warning_after, self._max_runtime_warning
            )

    @callback
    def _max_runtime_warning(self, _now: datetime) -> None:
        self._runtime_warning_timer = None
        if self._runtime_started_at is None or self.master is None or not self.master.is_on:
            return
        self._runtime_warning_sent = True
        self._persist_runtime_state()
        hours = float(self.config.get(CONF_MAX_RUNTIME_HOURS, DEFAULT_MAX_RUNTIME_HOURS))
        self.hass.async_create_task(
            self._notify(
                self._msg("runtime_title"),
                self._msg("runtime_warning", hours=f"{hours:g}"),
            )
        )

    @callback
    def _max_runtime_reached(self, _now: datetime) -> None:
        self._runtime_limit_timer = None
        if self._runtime_started_at is None or self.master is None or not self.master.is_on:
            return
        hours = float(self.config.get(CONF_MAX_RUNTIME_HOURS, DEFAULT_MAX_RUNTIME_HOURS))
        remaining = hours * 3600 - (dt_util.utcnow() - self._runtime_started_at).total_seconds()
        if remaining > 0:
            self._runtime_limit_timer = async_call_later(
                self.hass, remaining, self._max_runtime_reached
            )
            return
        self.master.set_state_silently(False)
        self.hass.async_create_task(self.async_master_changed(force=True))

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
        # Emergency mode: without a trustworthy room sensor keep the room at eco.
        use_eco = not self.comfort_mode or self.runtime[room.id].sensor_failed
        number = (self.eco if use_eco else self.comfort).get(room.id)
        return number.native_value if number else None

    def _away_target(self, room: Room) -> float | None:
        return self.away_temperature.native_value if self.away_temperature else None

    async def async_apply(self) -> None:
        """Send the right target temperature to every room thermostat."""
        async with self._lock:
            if not self.master_on or self.boost_active:
                return
            if self.away_on:
                if not self.config.get(CONF_ENABLE_AWAY_TARGET, True):
                    return
                target_fn = self._away_target
            elif self.config.get(CONF_ENABLE_MODE_APPLY, True):
                target_fn = self._room_target
            else:
                return
            for room in self.rooms:
                if not self.runtime[room.id].paused:
                    await self._apply_room(room, target_fn(room))

    async def _apply_room(self, room: Room, target: float | None) -> None:
        state = self.hass.states.get(room.climate)
        if state is None or state.state in _INVALID or target is None:
            return
        self._mark_own_change()
        attrs = state.attributes
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
        if state.state != HVACMode.HEAT or _as_float(attrs.get("temperature")) != target:
            await self._send(room, HVACMode.HEAT, target)

    async def async_master_changed(self, *, force: bool = False) -> None:
        """Master switch: heat or off for boiler and every room."""
        self._sync_runtime_limit()
        if not force and not self.config.get(CONF_ENABLE_MASTER, True):
            return
        heating_enabled = (
            bool(self.master and self.master.is_on) if force else self.master_on
        )
        if not heating_enabled and self.boost_active:
            await self.async_stop_boost(restore=False)
        mode = HVACMode.HEAT if heating_enabled else HVACMode.OFF
        self._mark_own_change()
        await self._set_boiler_mode(mode)
        for room in self.rooms:
            room_mode = HVACMode.OFF if self.runtime[room.id].paused else mode
            state = self.hass.states.get(room.climate)
            if state is not None and state.state not in _INVALID and state.state != room_mode:
                await self._send(room, room_mode, None)
        if self._settle_timer:
            self._settle_timer()
            self._settle_timer = None
        if mode == HVACMode.HEAT:
            self._settle_timer = async_call_later(
                self.hass,
                int(self.config.get(CONF_MASTER_SETTLE_SECONDS, MASTER_SETTLE_SECONDS)),
                self._after_master_on,
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
        room = next((r for r in self.rooms if r.sensor == event.data["entity_id"]), None)
        value = _state_float(event.data["new_state"])
        if room is not None and value is not None:
            rt = self.runtime[room.id]
            now = dt_util.utcnow()
            rt.readings.append((now, value))
            if rt.sensor_failed:
                self._diagnostics_tick(now)
            self._check_temperature_drop(room, now, value)
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
        if room is None or old is None or self.runtime[room.id].paused:
            return
        if self.boost_active:
            if not self.boost_selected(room) and new.state not in (HVACMode.OFF, *_INVALID):
                self.hass.async_create_task(
                    self._call("climate", "set_hvac_mode", entity_id, hvac_mode=HVACMode.OFF)
                )
            return
        self._sync_slider(room, old, new)

    def _sync_slider(self, room: Room, old: State, new: State) -> None:
        """A target changed on the room thermostat becomes the new comfort/eco value."""
        if (
            not self.config.get(CONF_ENABLE_SLIDER_SYNC, True)
            or self.away_on
            or time.monotonic() < self._suppress_until
        ):
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

    # ---------- boost ----------

    def _climate_snapshot(self, entity_id: str | None) -> dict[str, Any] | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None or state.state in _INVALID:
            return None
        return {"state": state.state, "temperature": _as_float(state.attributes.get("temperature"))}

    async def _set_climate(self, entity_id: str, mode: str, temperature: float | None) -> None:
        if (room := self.room_by_climate(entity_id)) is not None:
            if self.runtime[room.id].paused:
                mode, temperature = HVACMode.OFF, None
            await self._send(room, mode, temperature)
            return
        if self.boiler_entity is not None and entity_id == self.boiler_climate_id:
            await self.boiler_entity.async_set_hvac_mode(HVACMode(mode))
            if temperature is not None:
                await self.boiler_entity.async_set_temperature(temperature=temperature)
            return
        await self._call("climate", "set_hvac_mode", entity_id, hvac_mode=mode)
        if temperature is not None and mode != HVACMode.OFF:
            await self._call("climate", "set_temperature", entity_id, temperature=temperature)

    def _set_switch_silently(self, switch: AquecimentoSwitch | None, value: bool) -> None:
        if switch is not None and switch.is_on != value:
            switch.set_state_silently(value)

    async def async_start_boost(
        self, hours: float | None = None, temperature: float | None = None
    ) -> None:
        """Heat only the selected rooms to a boost temperature for a while."""
        selected = [r for r in self.rooms if self.boost_selected(r)]
        if not selected:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="boost_no_rooms"
            )
        hours = float(hours if hours is not None else self._number(self.boost_hours, 1))
        target = float(
            temperature if temperature is not None else self._number(self.boost_temperature, 23)
        )

        if not self.boost_active:
            self._boost_snapshot = {
                "master": self.master_on,
                "refs": {rid: s.is_on for rid, s in self.use_for_boiler.items()},
                "rooms": {r.climate: self._climate_snapshot(r.climate) for r in self.rooms},
                "boiler": self._climate_snapshot(self.boiler_climate_id),
            }
        self.boost_until = dt_util.utcnow() + timedelta(hours=hours)
        self._schedule_boost_end()
        self._mark_own_change()

        self._set_switch_silently(self.master, True)
        for room in self.rooms:
            self._set_switch_silently(self.use_for_boiler.get(room.id), self.boost_selected(room))
        self.notify_temperatures()

        for room in self.rooms:
            if self.boost_selected(room):
                await self._set_climate(room.climate, HVACMode.HEAT, target)
            else:
                await self._set_climate(room.climate, HVACMode.OFF, None)
        if self.boiler_climate_id:
            await self._set_climate(self.boiler_climate_id, HVACMode.HEAT, target)
        async_dispatcher_send(self.hass, self.signal_boost)

    async def async_stop_boost(self, restore: bool = True) -> None:
        """End the boost and put everything back as it was."""
        if self._boost_timer:
            self._boost_timer()
            self._boost_timer = None
        was_active = self.boost_active
        self.boost_until = None
        snapshot, self._boost_snapshot = self._boost_snapshot, None
        async_dispatcher_send(self.hass, self.signal_boost)
        if not was_active or not restore or not snapshot:
            return

        self._mark_own_change()
        self._set_switch_silently(self.master, bool(snapshot.get("master", True)))
        for room_id, value in (snapshot.get("refs") or {}).items():
            self._set_switch_silently(self.use_for_boiler.get(room_id), bool(value))
        self.notify_temperatures()

        if self.boiler_climate_id and (boiler := snapshot.get("boiler")):
            await self._set_climate(self.boiler_climate_id, boiler["state"], boiler["temperature"])
        for climate, saved in (snapshot.get("rooms") or {}).items():
            if saved:
                await self._set_climate(climate, saved["state"], saved["temperature"])
        if self.master_on:
            self.request_apply()
        else:
            await self.async_master_changed()

    def restore_boost(self, until: datetime | None, snapshot: dict[str, Any] | None) -> None:
        """Called by the boost switch after a restart."""
        self.boost_until = until
        self._boost_snapshot = snapshot

    def boost_snapshot(self) -> dict[str, Any] | None:
        return self._boost_snapshot

    def _schedule_boost_end(self) -> None:
        if self._boost_timer:
            self._boost_timer()
        if self.boost_until is not None:
            self._boost_timer = async_track_point_in_utc_time(
                self.hass, self._boost_finished, self.boost_until
            )

    @callback
    def _boost_finished(self, _now: datetime) -> None:
        self._boost_timer = None
        self.hass.async_create_task(self.async_stop_boost())

    @staticmethod
    def _number(entity: HelperNumber | None, default: float) -> float:
        value = entity.native_value if entity else None
        return float(value) if value is not None else default

    # ---------- presence ----------

    def _anyone_home(self) -> bool:
        return any(self.hass.states.is_state(p, STATE_HOME) for p in self.persons)

    def _start_away_timer(self) -> None:
        if (
            not self.config.get(CONF_ENABLE_PRESENCE, True)
            or self._away_timer
            or self.away_on
        ):
            return
        delay = int(self.config.get(CONF_AWAY_DELAY, DEFAULT_AWAY_DELAY)) * 60
        self._away_timer = async_call_later(self.hass, delay, self._away_timeout)

    @callback
    def _away_timeout(self, _now: datetime) -> None:
        self._away_timer = None
        if (
            self.config.get(CONF_ENABLE_PRESENCE, True)
            and self.away is not None
            and not self._anyone_home()
            and not self.away_on
        ):
            self.hass.async_create_task(self.away.async_turn_on())

    @callback
    def _on_person_change(self, event: Event[EventStateChangedData]) -> None:
        if not self.config.get(CONF_ENABLE_PRESENCE, True):
            return
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

    @callback
    def _on_schedule_change(self, event: Event[EventStateChangedData]) -> None:
        self._apply_schedule_state(event.data["new_state"])

    def _apply_schedule_state(self, state: State | None) -> None:
        if state is None or self.mode is None:
            return
        if state.state == STATE_ON:
            option = MODE_COMFORT
        elif state.state == STATE_OFF:
            option = MODE_ECO
        else:
            return
        if self.mode.current_option != option:
            self.hass.async_create_task(self.mode.async_select_option(option))

    # ---------- verified commands ----------

    async def _send(self, room: Room, hvac_mode: str | None, temperature: float | None) -> None:
        """Send a command to a room thermostat and check later that it was applied."""
        rt = self.runtime[room.id]
        desired = dict(rt.desired or {})
        if hvac_mode is not None:
            desired["hvac_mode"] = str(hvac_mode)
        if temperature is not None:
            desired["temperature"] = float(temperature)
        desired["attempts"] = 0
        rt.desired = desired
        await self._issue(room)

    async def _issue(self, room: Room) -> None:
        rt = self.runtime[room.id]
        desired = rt.desired
        state = self.hass.states.get(room.climate)
        if not desired or state is None or state.state in _INVALID:
            return
        self._mark_own_change()
        mode = desired.get("hvac_mode")
        if mode and state.state != mode:
            await self._call("climate", "set_hvac_mode", room.climate, hvac_mode=mode)
        target = desired.get("temperature")
        if target is not None and mode != HVACMode.OFF:
            if _as_float(state.attributes.get("temperature")) != target or state.state != mode:
                await self._call("climate", "set_temperature", room.climate, temperature=target)
        if rt.verify_unsub:
            rt.verify_unsub()
        rt.verify_unsub = async_call_later(
            self.hass,
            int(self.config.get(CONF_VERIFY_SECONDS, VERIFY_SECONDS)),
            partial(self._verify, room),
        )

    def _command_applied(self, room: Room) -> bool:
        desired = self.runtime[room.id].desired or {}
        state = self.hass.states.get(room.climate)
        if state is None or state.state in _INVALID:
            return False
        mode = desired.get("hvac_mode")
        if mode and state.state != mode:
            return False
        target = desired.get("temperature")
        if target is not None and mode != HVACMode.OFF:
            return _as_float(state.attributes.get("temperature")) == target
        return True

    @callback
    def _verify(self, room: Room, _now: datetime) -> None:
        rt = self.runtime[room.id]
        rt.verify_unsub = None
        if not rt.desired:
            return
        if self._command_applied(room):
            rt.desired = None
            return
        rt.desired["attempts"] += 1
        max_retries = int(self.config.get(CONF_VERIFY_RETRIES, MAX_RETRIES))
        if rt.desired["attempts"] <= max_retries:
            _LOGGER.info(
                "%s did not apply %s, resending (%s/%s)",
                room.climate, rt.desired, rt.desired["attempts"], max_retries,
            )
            self.hass.async_create_task(self._issue(room))
            return
        _LOGGER.warning("%s did not apply %s after %s retries", room.climate, rt.desired, max_retries)
        rt.command_failures += 1
        rt.desired = None
        async_dispatcher_send(self.hass, self.signal_diagnostics)

    # ---------- windows: pause and resume ----------

    @callback
    def _on_window_change(self, event: Event[EventStateChangedData]) -> None:
        if not self.config.get(CONF_ENABLE_WINDOWS, True):
            return
        room = next((r for r in self.rooms if event.data["entity_id"] in r.windows), None)
        if room is not None:
            self._schedule_contact_check(room)

    def _schedule_contact_check(self, room: Room) -> None:
        rt = self.runtime[room.id]
        if rt.contact_unsub:
            rt.contact_unsub()
        rt.contact_unsub = async_call_later(
            self.hass,
            int(self.config.get(CONF_WINDOW_CONTACT_SECONDS, WINDOW_CONTACT_SECONDS)),
            partial(self._contact_settled, room),
        )

    @callback
    def _contact_settled(self, room: Room, _now: datetime) -> None:
        rt = self.runtime[room.id]
        rt.contact_unsub = None
        is_open = any(self.hass.states.is_state(w, STATE_ON) for w in room.windows)
        if is_open and not rt.paused:
            self.hass.async_create_task(self._pause_room(room, "contact"))
        elif is_open and rt.pause_reason == "temperature":
            rt.pause_reason = "contact"
            async_dispatcher_send(self.hass, self.signal_diagnostics)
        elif not is_open and rt.paused and rt.pause_reason == "contact":
            self.hass.async_create_task(self._resume_room(room))

    @property
    def temperature_window_detection(self) -> bool:
        switch = self.window_temperature_detection
        return switch.is_on if switch else True

    def _check_temperature_drop(self, room: Room, now: datetime, value: float) -> None:
        rt = self.runtime[room.id]
        if (
            not self.config.get(CONF_ENABLE_WINDOWS, True)
            or rt.paused
            or not self.temperature_window_detection
            or not self.master_on
        ):
            return
        state = self.hass.states.get(room.climate)
        if state is None or state.state != HVACMode.HEAT:
            return
        drop_minutes = int(self.config.get(CONF_WINDOW_DROP_MINUTES, WINDOW_DROP_MINUTES))
        since = now - timedelta(minutes=drop_minutes)
        recent = [v for t, v in rt.readings if t >= since]
        drop_degrees = float(self.config.get(CONF_WINDOW_DROP_DEGREES, WINDOW_DROP_DEGREES))
        if recent and max(recent) - value >= drop_degrees:
            self.hass.async_create_task(self._pause_room(room, "temperature"))

    def _temperature_window_closed(self, room: Room, now: datetime) -> bool:
        rt = self.runtime[room.id]
        elapsed = now - (rt.paused_since or now)
        max_pause = int(
            self.config.get(CONF_WINDOW_MAX_PAUSE_MINUTES, WINDOW_MAX_PAUSE_MINUTES)
        )
        if elapsed >= timedelta(minutes=max_pause):
            return True
        min_pause = int(
            self.config.get(CONF_WINDOW_MIN_PAUSE_MINUTES, WINDOW_MIN_PAUSE_MINUTES)
        )
        if elapsed < timedelta(minutes=min_pause):
            return False
        drop_minutes = int(self.config.get(CONF_WINDOW_DROP_MINUTES, WINDOW_DROP_MINUTES))
        since = now - timedelta(minutes=drop_minutes)
        recent = [v for t, v in rt.readings if t >= since]
        # No longer falling: the last readings are not below the oldest recent one.
        return len(recent) >= 2 and recent[-1] >= recent[0] - 0.1

    async def _pause_room(self, room: Room, reason: str) -> None:
        if not self.config.get(CONF_ENABLE_WINDOWS, True):
            return
        rt = self.runtime[room.id]
        if rt.paused:
            return
        rt.paused, rt.pause_reason, rt.paused_since = True, reason, dt_util.utcnow()
        async_dispatcher_send(self.hass, self.signal_diagnostics)
        await self._send(room, HVACMode.OFF, None)
        if self.config.get(CONF_NOTIFY_WINDOWS, True):
            key = "window_drop" if reason == "temperature" else "window"
            await self._notify(self._msg("window_title"), self._msg(key, room=room.name))

    async def _resume_room(self, room: Room) -> None:
        rt = self.runtime[room.id]
        rt.paused, rt.pause_reason, rt.paused_since = False, None, None
        async_dispatcher_send(self.hass, self.signal_diagnostics)
        if not self.master_on:
            return
        if self.boost_active:
            if self.boost_selected(room):
                await self._send(room, HVACMode.HEAT, self._number(self.boost_temperature, 23))
            return
        await self._send(room, HVACMode.HEAT, None)
        self.request_apply()

    # ---------- diagnostics ----------

    def _sensor_age_hours(self, state: State | None) -> float | None:
        if state is None:
            return None
        last = getattr(state, "last_reported", None) or state.last_updated
        return (dt_util.utcnow() - last).total_seconds() / 3600

    @callback
    def _diagnostics_tick(self, now: datetime) -> None:
        now = dt_util.utcnow()
        changed = False
        for room in self.rooms:
            rt = self.runtime[room.id]
            state = self.hass.states.get(room.sensor)
            age = self._sensor_age_hours(state)
            rt.sensor_age_hours = round(age, 1) if age is not None else None
            failed = _state_float(state) is None or (age is not None and age >= SENSOR_STALE_HOURS)
            if failed != rt.sensor_failed:
                rt.sensor_failed = failed
                changed = True
                self.notify_temperatures()
                self.request_apply()
                if failed and self.config.get(CONF_NOTIFY_SENSOR_FAILURE, True):
                    self.hass.async_create_task(
                        self._notify(self._msg("problem_title"), self._msg("sensor_failed", room=room.name))
                    )

            not_heating = self._is_not_heating(room, now)
            if not_heating != rt.not_heating:
                rt.not_heating = not_heating
                changed = True
                if not_heating and self.config.get(CONF_NOTIFY_NOT_HEATING, True):
                    self.hass.async_create_task(
                        self._notify(
                            self._msg("problem_title"),
                            self._msg("not_heating", room=room.name, hours=NOT_HEATING_HOURS),
                        )
                    )

            if rt.paused and rt.pause_reason == "temperature" and self._temperature_window_closed(room, now):
                self.hass.async_create_task(self._resume_room(room))
        if changed:
            async_dispatcher_send(self.hass, self.signal_diagnostics)

    def _is_not_heating(self, room: Room, now: datetime) -> bool:
        rt = self.runtime[room.id]
        state = self.hass.states.get(room.climate)
        current = self.room_temperature(room)
        target = _as_float(state.attributes.get("temperature")) if state else None
        lagging = (
            self.master_on
            and not rt.paused
            and state is not None
            and state.state == HVACMode.HEAT
            and current is not None
            and target is not None
            and target - current >= NOT_HEATING_DELTA
        )
        if not lagging:
            rt.not_heating_since = None
            return False
        if rt.not_heating_since is None:
            rt.not_heating_since = now
        return now - rt.not_heating_since >= timedelta(hours=NOT_HEATING_HOURS)

    # ---------- batteries ----------

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
