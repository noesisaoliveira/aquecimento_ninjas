"""Switches: master on/off, away mode and 'use for boiler' per room."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import AquecimentoConfigEntry
from .controller import HeatingController, Room
from .entity import AquecimentoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquecimentoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data

    master = AquecimentoSwitch(
        controller, "master", True, "mdi:power",
        lambda: hass.async_create_task(controller.async_master_changed()),
    )
    away = AquecimentoSwitch(
        controller, "away", False, "mdi:home-export-outline", controller.request_apply
    )
    controller.master, controller.away = master, away
    entities: list[AquecimentoSwitch] = [master, away]

    for index, room in enumerate(controller.rooms):
        switch = AquecimentoSwitch(
            controller, "use_for_boiler", index == 0, "mdi:home-thermometer",
            controller.notify_temperatures, room,
        )
        controller.use_for_boiler[room.id] = switch
        entities.append(switch)

    async_add_entities(entities)


class AquecimentoSwitch(AquecimentoEntity, SwitchEntity, RestoreEntity):
    """A restorable helper switch that notifies the controller on change."""

    def __init__(
        self,
        controller: HeatingController,
        key: str,
        default: bool,
        icon: str,
        on_change: Callable[[], Any],
        room: Room | None = None,
    ) -> None:
        super().__init__(controller, key, room)
        self._attr_icon = icon
        self._attr_is_on = default
        self._on_change = on_change

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in (STATE_ON, STATE_OFF):
            self._attr_is_on = last.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

    async def _set(self, value: bool) -> None:
        if self._attr_is_on == value:
            return
        self._attr_is_on = value
        self.async_write_ha_state()
        self._on_change()
