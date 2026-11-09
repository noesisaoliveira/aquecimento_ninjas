"""Sensors: boiler reference temperature, house statistics and boiler usage."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AquecimentoConfigEntry
from .controller import HeatingController
from .entity import AquecimentoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquecimentoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    c = entry.runtime_data

    def _temps() -> list[float]:
        return c.room_temperatures()

    def _avg() -> float | None:
        t = _temps()
        return round(sum(t) / len(t), 1) if t else None

    def _spread() -> float | None:
        t = _temps()
        return round(max(t) - min(t), 1) if len(t) > 1 else None

    async_add_entities(
        [
            ReferenceSensor(c),
            TemperatureSensor(c, "average_temperature", "mdi:home-thermometer-outline", _avg),
            TemperatureSensor(
                c, "minimum_temperature", "mdi:thermometer-chevron-down",
                lambda: min(_temps()) if _temps() else None,
            ),
            TemperatureSensor(
                c, "maximum_temperature", "mdi:thermometer-chevron-up",
                lambda: max(_temps()) if _temps() else None,
            ),
            TemperatureSensor(
                c, "temperature_spread", "mdi:arrow-expand-vertical", _spread, is_delta=True
            ),
            BoilerOnTimeSensor(c),
            BoilerCyclesSensor(c),
            BoilerAverageCycleSensor(c),
        ]
    )


class _TemperatureBase(AquecimentoEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_temperatures, self._handle_update
            )
        )
        self._handle_update()

    @callback
    def _handle_update(self) -> None:
        self._refresh()
        if self.hass is not None:
            self.async_write_ha_state()

    def _refresh(self) -> None:
        raise NotImplementedError


class ReferenceSensor(_TemperatureBase):
    """Average of the rooms selected with 'use for boiler'; the boiler reads this."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_icon = "mdi:home-thermometer"

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "reference_temperature")

    def _refresh(self) -> None:
        value, rooms = self.controller.reference()
        self._attr_native_value = value
        self._attr_extra_state_attributes = {"rooms": ", ".join(rooms)}


class TemperatureSensor(_TemperatureBase):
    """House temperature statistic."""

    def __init__(
        self,
        controller: HeatingController,
        key: str,
        icon: str,
        compute: Callable[[], float | None],
        is_delta: bool = False,
    ) -> None:
        super().__init__(controller, key)
        self._attr_icon = icon
        self._compute = compute
        if not is_delta:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE

    def _refresh(self) -> None:
        self._attr_native_value = self._compute()


class _StatsBase(AquecimentoEntity, RestoreSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        last_data = await self.async_get_last_sensor_data()
        if (
            last_state is not None
            and last_data is not None
            and last_data.native_value is not None
            and dt_util.as_local(last_state.last_updated).date() == dt_util.now().date()
        ):
            self._restore(last_data.native_value)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.controller.signal_stats, self._handle_update)
        )
        self._handle_update()

    def _restore(self, value: Any) -> None:
        """Restore today's value after a restart."""

    @callback
    def _handle_update(self) -> None:
        self._attr_native_value = self._value()
        self.async_write_ha_state()

    def _value(self) -> float | int:
        raise NotImplementedError


class BoilerOnTimeSensor(_StatsBase):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:clock-outline"

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "boiler_on_time")

    def _restore(self, value: Any) -> None:
        try:
            self.controller.stats.on_seconds = float(value) * 3600
        except (TypeError, ValueError):
            pass

    def _value(self) -> float:
        return self.controller.stats.on_hours


class BoilerCyclesSensor(_StatsBase):
    _attr_icon = "mdi:sync"

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "boiler_cycles")

    def _restore(self, value: Any) -> None:
        try:
            self.controller.stats.cycles = int(float(value))
        except (TypeError, ValueError):
            pass

    def _value(self) -> int:
        return self.controller.stats.cycles


class BoilerAverageCycleSensor(_StatsBase):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:timer-outline"

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "boiler_average_cycle")

    def _value(self) -> float:
        return self.controller.stats.average_cycle_minutes
