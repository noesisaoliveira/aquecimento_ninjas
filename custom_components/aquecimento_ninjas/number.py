"""Sliders: comfort and eco per room, away temperature, boost duration and temperature."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquecimentoConfigEntry
from .const import (
    DEFAULT_AWAY,
    DEFAULT_BOOST_HOURS,
    DEFAULT_BOOST_TEMPERATURE,
    DEFAULT_COMFORT,
    DEFAULT_ECO,
    MAX_TEMP,
    MIN_TEMP,
    TEMP_STEP,
)
from .controller import HeatingController, Room
from .entity import AquecimentoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquecimentoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    away = HelperNumber(controller, "away_temperature", DEFAULT_AWAY, "mdi:home-export-outline")
    boost_hours = HelperNumber(
        controller, "boost_hours", DEFAULT_BOOST_HOURS, "mdi:timer-outline",
        minimum=0.5, maximum=6, step=0.5, unit=UnitOfTime.HOURS, apply=False,
    )
    boost_temp = HelperNumber(
        controller, "boost_temperature", DEFAULT_BOOST_TEMPERATURE, "mdi:thermometer-plus",
        minimum=16, maximum=MAX_TEMP, apply=False,
    )
    controller.away_temperature = away
    controller.boost_hours, controller.boost_temperature = boost_hours, boost_temp
    entities: list[HelperNumber] = [away, boost_hours, boost_temp]
    for room in controller.rooms:
        comfort = HelperNumber(controller, "comfort", DEFAULT_COMFORT, "mdi:sun-thermometer", room=room)
        eco = HelperNumber(controller, "eco", DEFAULT_ECO, "mdi:leaf", room=room)
        controller.comfort[room.id] = comfort
        controller.eco[room.id] = eco
        entities += [comfort, eco]
    async_add_entities(entities)


class HelperNumber(AquecimentoEntity, RestoreNumber):
    """A restorable setting; temperature by default."""

    def __init__(
        self,
        controller: HeatingController,
        key: str,
        default: float,
        icon: str,
        *,
        room: Room | None = None,
        minimum: float = MIN_TEMP,
        maximum: float = MAX_TEMP,
        step: float = TEMP_STEP,
        unit: str = UnitOfTemperature.CELSIUS,
        apply: bool = True,
    ) -> None:
        super().__init__(controller, key, room)
        self._attr_icon = icon
        self._attr_native_value = default
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        if unit == UnitOfTemperature.CELSIUS:
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = NumberMode.BOX
        self._apply = apply

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value

    async def async_set_native_value(self, value: float) -> None:
        if value == self._attr_native_value:
            return
        self._attr_native_value = value
        self.async_write_ha_state()
        if self._apply:
            self.controller.request_apply()
