"""Temperature sliders: comfort and eco per room, away temperature."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquecimentoConfigEntry
from .const import (
    DEFAULT_AWAY,
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
    away = TemperatureNumber(controller, "away_temperature", DEFAULT_AWAY, "mdi:home-export-outline")
    controller.away_temperature = away
    entities: list[TemperatureNumber] = [away]
    for room in controller.rooms:
        comfort = TemperatureNumber(controller, "comfort", DEFAULT_COMFORT, "mdi:sofa", room)
        eco = TemperatureNumber(controller, "eco", DEFAULT_ECO, "mdi:leaf", room)
        controller.comfort[room.id] = comfort
        controller.eco[room.id] = eco
        entities += [comfort, eco]
    async_add_entities(entities)


class TemperatureNumber(AquecimentoEntity, RestoreNumber):
    """A restorable temperature setting."""

    _attr_native_min_value = MIN_TEMP
    _attr_native_max_value = MAX_TEMP
    _attr_native_step = TEMP_STEP
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        controller: HeatingController,
        key: str,
        default: float,
        icon: str,
        room: Room | None = None,
    ) -> None:
        super().__init__(controller, key, room)
        self._attr_icon = icon
        self._attr_native_value = default

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
        self.controller.request_apply()
