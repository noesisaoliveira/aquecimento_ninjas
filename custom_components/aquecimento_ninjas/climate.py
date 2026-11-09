"""Optional boiler thermostat created by the integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_ON, UnitOfTemperature
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import AquecimentoConfigEntry
from .const import (
    CONF_COLD_TOLERANCE,
    CONF_HOT_TOLERANCE,
    CONF_MIN_CYCLE,
    DEFAULT_BOILER_TARGET,
    DEFAULT_COLD_TOLERANCE,
    DEFAULT_HOT_TOLERANCE,
    DEFAULT_MIN_CYCLE,
    MAX_TEMP,
    MIN_TEMP,
)
from .controller import HeatingController
from .entity import AquecimentoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquecimentoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    if not controller.creates_boiler or not controller.boiler_switch_id:
        return
    controller.boiler_entity = BoilerThermostat(controller)
    async_add_entities([controller.boiler_entity])


class BoilerThermostat(AquecimentoEntity, ClimateEntity, RestoreEntity):
    """On/off boiler control using the reference temperature of the selected rooms."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.1
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_icon = "mdi:water-boiler"

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "boiler")
        self._heater = controller.boiler_switch_id
        cfg = controller.config
        self._cold = float(cfg.get(CONF_COLD_TOLERANCE, DEFAULT_COLD_TOLERANCE))
        self._hot = float(cfg.get(CONF_HOT_TOLERANCE, DEFAULT_HOT_TOLERANCE))
        self._min_cycle = timedelta(minutes=float(cfg.get(CONF_MIN_CYCLE, DEFAULT_MIN_CYCLE)))
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_target_temperature = DEFAULT_BOILER_TARGET

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            if last.state in (HVACMode.HEAT, HVACMode.OFF):
                self._attr_hvac_mode = HVACMode(last.state)
            if (target := last.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(target)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_temperatures, self._schedule_control
            )
        )
        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._heater], self._on_heater_change)
        )
        self.async_on_remove(
            async_track_time_interval(self.hass, self._on_tick, timedelta(minutes=1))
        )
        self._schedule_control()

    @property
    def current_temperature(self) -> float | None:
        return self.controller.reference()[0]

    @property
    def _heater_on(self) -> bool:
        return self.hass.states.is_state(self._heater, STATE_ON)

    @property
    def hvac_action(self) -> HVACAction:
        if self._attr_hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.HEATING if self._heater_on else HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"rooms": ", ".join(self.controller.reference()[1])}

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT and not self.controller.master_on:
            hvac_mode = HVACMode.OFF
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        await self._async_control()

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (target := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._attr_target_temperature = float(target)
        self.async_write_ha_state()
        await self._async_control()

    @callback
    def _schedule_control(self) -> None:
        self.hass.async_create_task(self._async_control())
        self.async_write_ha_state()

    @callback
    def _on_heater_change(self, event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    @callback
    def _on_tick(self, _now: datetime) -> None:
        self._schedule_control()

    def _cycle_elapsed(self) -> bool:
        state = self.hass.states.get(self._heater)
        if state is None:
            return True
        return dt_util.utcnow() - state.last_changed >= self._min_cycle

    async def _switch(self, on: bool) -> None:
        await self.hass.services.async_call(
            "homeassistant",
            "turn_on" if on else "turn_off",
            {"entity_id": self._heater},
            blocking=True,
        )

    async def _async_control(self) -> None:
        heater_on = self._heater_on
        if self._attr_hvac_mode == HVACMode.OFF:
            if heater_on:
                await self._switch(False)
            return
        current = self.current_temperature
        target = self._attr_target_temperature
        if current is None or target is None or not self._cycle_elapsed():
            return
        if heater_on and current >= target + self._hot:
            await self._switch(False)
        elif not heater_on and current <= target - self._cold:
            await self._switch(True)
