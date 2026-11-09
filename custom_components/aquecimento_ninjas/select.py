"""House-wide Conforto / Eco selector."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import AquecimentoConfigEntry
from .const import MODE_COMFORT, MODE_ECO
from .controller import HeatingController
from .entity import AquecimentoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquecimentoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    controller.mode = ModeSelect(controller)
    async_add_entities([controller.mode])


class ModeSelect(AquecimentoEntity, SelectEntity, RestoreEntity):
    """Chooses whether every room uses its comfort or eco temperature."""

    _attr_options = [MODE_ECO, MODE_COMFORT]
    _attr_icon = "mdi:thermostat"

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "mode")
        self._attr_current_option = MODE_ECO

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self._attr_options:
            self._attr_current_option = last.state

    async def async_select_option(self, option: str) -> None:
        if option == self._attr_current_option:
            return
        self._attr_current_option = option
        self.async_write_ha_state()
        self.controller.request_apply()
