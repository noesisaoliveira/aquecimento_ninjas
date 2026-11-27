"""Per-room status: window open (paused), sensor problem, not heating."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquecimentoConfigEntry
from .const import NOT_HEATING_DELTA, NOT_HEATING_HOURS
from .controller import HeatingController, Room, RoomRuntime
from .entity import AquecimentoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquecimentoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    c = entry.runtime_data
    entities: list[RoomStatusSensor] = []
    for room in c.rooms:
        entities += [
            RoomStatusSensor(
                c, room, "window_open", BinarySensorDeviceClass.WINDOW,
                lambda rt: rt.paused,
                lambda rt: {"reason": rt.pause_reason, "since": rt.paused_since},
                diagnostic=False,
            ),
            RoomStatusSensor(
                c, room, "sensor_problem", BinarySensorDeviceClass.PROBLEM,
                lambda rt: rt.sensor_failed,
                lambda rt: {
                    "hours_since_update": rt.sensor_age_hours,
                    "limit_hours": c.sensor_stale_hours,
                    "emergency_mode": rt.sensor_failed,
                },
            ),
            RoomStatusSensor(
                c, room, "not_heating", BinarySensorDeviceClass.PROBLEM,
                lambda rt: rt.not_heating,
                lambda rt: {
                    "lagging_since": rt.not_heating_since,
                    "limit": f">= {NOT_HEATING_DELTA} °C for {NOT_HEATING_HOURS} h",
                    "command_failures": rt.command_failures,
                },
            ),
        ]
    async_add_entities(entities)


class RoomStatusSensor(AquecimentoEntity, BinarySensorEntity):
    """Reads one flag of the room runtime state."""

    def __init__(
        self,
        controller: HeatingController,
        room: Room,
        key: str,
        device_class: BinarySensorDeviceClass,
        value: Callable[[RoomRuntime], bool],
        attributes: Callable[[RoomRuntime], dict[str, Any]],
        diagnostic: bool = True,
    ) -> None:
        super().__init__(controller, key, room)
        self._runtime = controller.runtime[room.id]
        self._value = value
        self._attributes = attributes
        self._attr_device_class = device_class
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        return self._value(self._runtime)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._attributes(self._runtime)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_diagnostics, self.async_write_ha_state
            )
        )
