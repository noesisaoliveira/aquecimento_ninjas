"""Shared entity base for Aquecimento Ninjas."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOCS_URL, DOMAIN, VERSION
from .controller import HeatingController, Room


class AquecimentoEntity:
    """Mixin: unique id, translated name and the shared device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: HeatingController, key: str, room: Room | None = None) -> None:
        self.controller = controller
        entry_id = controller.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{room.id}_{key}" if room else f"{entry_id}_{key}"
        self._attr_translation_key = key
        if room is not None:
            self._attr_translation_placeholders = {"room": room.name}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=controller.config.get(CONF_NAME, "Aquecimento Ninjas"),
            manufacturer="Aquecimento Ninjas",
            model="Heating controller",
            sw_version=VERSION,
            configuration_url=DOCS_URL,
            entry_type=DeviceEntryType.SERVICE,
        )
        controller.unique_ids.add(self._attr_unique_id)
