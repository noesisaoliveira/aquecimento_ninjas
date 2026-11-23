"""Emergency heating: fires the boiler without sensors, protected by a PIN."""

from __future__ import annotations

from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import AquecimentoConfigEntry
from .controller import HeatingController
from .entity import AquecimentoEntity

try:
    from homeassistant.components.alarm_control_panel import AlarmControlPanelState
except ImportError:  # Home Assistant before 2025.11
    AlarmControlPanelState = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquecimentoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([EmergencyHeating(entry.runtime_data)])


class EmergencyHeating(AquecimentoEntity, AlarmControlPanelEntity, RestoreEntity):
    """Armed = boiler forced on. Arming asks for the PIN set in the configuration."""

    _attr_icon = "mdi:fire-alert"
    _attr_code_format = CodeFormat.NUMBER
    _attr_code_arm_required = True
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "emergency")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "armed_away":
            until = dt_util.parse_datetime(last.attributes.get("until") or "")
            if until is not None:
                self.controller.restore_emergency(until)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_emergency, self._changed
            )
        )

    @callback
    def _changed(self) -> None:
        self.async_write_ha_state()

    if AlarmControlPanelState is not None:

        @property
        def alarm_state(self) -> AlarmControlPanelState:
            return (
                AlarmControlPanelState.ARMED_AWAY
                if self.controller.emergency_active
                else AlarmControlPanelState.DISARMED
            )

    else:

        @property
        def state(self) -> str:
            return "armed_away" if self.controller.emergency_active else "disarmed"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        until = self.controller.emergency_until
        return {"until": until.isoformat() if until else None}

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        self.controller.check_emergency_pin(code)
        await self.controller.async_start_emergency()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        # Stopping the boiler never needs the PIN.
        await self.controller.async_stop_emergency()
