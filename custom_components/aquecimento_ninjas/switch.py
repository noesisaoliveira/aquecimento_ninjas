"""Switches: master on/off, away mode, boost and per-room options."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

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
    boost = BoostSwitch(controller)
    window_temp = AquecimentoSwitch(
        controller, "window_temperature_detection", True, "mdi:window-open-variant", lambda: None
    )
    controller.master, controller.away, controller.boost_switch = master, away, boost
    controller.window_temperature_detection = window_temp
    entities: list[SwitchEntity] = [master, away, boost, window_temp]

    for index, room in enumerate(controller.rooms):
        use = AquecimentoSwitch(
            controller, "use_for_boiler", index == 0, "mdi:home-thermometer",
            controller.notify_temperatures, room,
        )
        boost_room = AquecimentoSwitch(
            controller, "boost_room", True, "mdi:fire", lambda: None, room
        )
        controller.use_for_boiler[room.id] = use
        controller.boost_rooms[room.id] = boost_room
        entities += [use, boost_room]

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
        self._key = key
        self._attr_icon = icon
        self._attr_is_on = default
        self._on_change = on_change

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in (STATE_ON, STATE_OFF):
            self._attr_is_on = last.state == STATE_ON
        if self._key == "master":
            data = await self.async_get_last_extra_data()
            if data is not None:
                stored = data.as_dict()
                started_value = stored.get("runtime_started_at")
                started = dt_util.parse_datetime(started_value) if started_value else None
                self.controller.restore_runtime_state(
                    started, bool(stored.get("runtime_warning_sent", False))
                )

    @property
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        if self._key != "master":
            return None
        started = self.controller.max_runtime_started_at
        return _MasterData(
            started.isoformat() if started is not None else None,
            self.controller.max_runtime_warning_sent,
        )

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

    @callback
    def set_state_silently(self, value: bool) -> None:
        """Change the state without running the controller callback (used by boost)."""
        self._attr_is_on = value
        if self.hass is not None:
            self.async_write_ha_state()


class _BoostData(ExtraStoredData):
    def __init__(self, until: str | None, snapshot: dict[str, Any] | None) -> None:
        self.until = until
        self.snapshot = snapshot

    def as_dict(self) -> dict[str, Any]:
        return {"until": self.until, "snapshot": self.snapshot}


class _MasterData(ExtraStoredData):
    def __init__(self, started_at: str | None, warning_sent: bool) -> None:
        self.started_at = started_at
        self.warning_sent = warning_sent

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime_started_at": self.started_at,
            "runtime_warning_sent": self.warning_sent,
        }


class BoostSwitch(AquecimentoEntity, SwitchEntity, RestoreEntity):
    """On = boost running. Turning on uses the boost duration and temperature settings."""

    _attr_icon = "mdi:fire-circle"

    def __init__(self, controller: HeatingController) -> None:
        super().__init__(controller, "boost")

    @property
    def is_on(self) -> bool:
        return self.controller.boost_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        until = self.controller.boost_until
        return {"ends_at": until.isoformat() if until else None}

    @property
    def extra_restore_state_data(self) -> _BoostData:
        until = self.controller.boost_until
        return _BoostData(until.isoformat() if until else None, self.controller.boost_snapshot())

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (data := await self.async_get_last_extra_data()) is not None:
            stored = data.as_dict()
            until = dt_util.parse_datetime(stored["until"]) if stored.get("until") else None
            if until is not None:
                self.controller.restore_boost(until, stored.get("snapshot"))
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_boost, self.async_write_ha_state
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_start_boost()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_stop_boost()
