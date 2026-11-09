"""Config flow (installation wizard) and options flow for Aquecimento Ninjas."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.util import slugify

from .const import (
    BETTER_THERMOSTAT_DOMAIN,
    BOILER_CREATE,
    BOILER_EXISTING,
    CONF_ADD_ANOTHER,
    CONF_AWAY_DELAY,
    CONF_BATTERY_THRESHOLD,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_MODE,
    CONF_BOILER_SWITCH,
    CONF_COLD_TOLERANCE,
    CONF_CREATE_DASHBOARD,
    CONF_DASHBOARD_TITLE,
    CONF_HOT_TOLERANCE,
    CONF_MIN_CYCLE,
    CONF_NOTIFY,
    CONF_NOTIFY_BATTERY,
    CONF_NOTIFY_WINDOWS,
    CONF_PERSONS,
    CONF_REGENERATE_DASHBOARD,
    CONF_ROOM_BATTERIES,
    CONF_ROOM_CLIMATE,
    CONF_ROOM_ID,
    CONF_ROOM_NAME,
    CONF_ROOM_SENSOR,
    CONF_ROOM_VALVES,
    CONF_ROOM_WINDOWS,
    CONF_ROOMS,
    DEFAULT_AWAY_DELAY,
    DEFAULT_BATTERY_THRESHOLD,
    DEFAULT_COLD_TOLERANCE,
    DEFAULT_HOT_TOLERANCE,
    DEFAULT_MIN_CYCLE,
    DEFAULT_NAME,
    DOMAIN,
    MAX_VALVES,
)


def merged_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return the effective configuration (options override data)."""
    return {**entry.data, **entry.options}


def _entity_selector(
    domain: str | list[str],
    *,
    multiple: bool = False,
    integration: str | None = None,
    device_class: str | None = None,
) -> selector.EntitySelector:
    config: dict[str, Any] = {"domain": domain, "multiple": multiple}
    if integration:
        config["integration"] = integration
    if device_class:
        config["device_class"] = device_class
    return selector.EntitySelector(selector.EntitySelectorConfig(**config))


def _number_selector(
    minimum: float, maximum: float, step: float, unit: str
) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _suggested(defaults: dict[str, Any], key: str) -> dict[str, Any]:
    value = defaults.get(key)
    return {"suggested_value": value} if value not in (None, "", []) else {}


# ---------- schemas ----------


def _user_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(
                CONF_BOILER_MODE, default=defaults.get(CONF_BOILER_MODE, BOILER_EXISTING)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[BOILER_EXISTING, BOILER_CREATE],
                    translation_key=CONF_BOILER_MODE,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
    )


def _boiler_schema(mode: str, defaults: dict[str, Any]) -> vol.Schema:
    switch_selector = _entity_selector(["switch", "input_boolean"])
    if mode == BOILER_EXISTING:
        return vol.Schema(
            {
                vol.Required(
                    CONF_BOILER_CLIMATE, description=_suggested(defaults, CONF_BOILER_CLIMATE)
                ): _entity_selector("climate"),
                vol.Optional(
                    CONF_BOILER_SWITCH, description=_suggested(defaults, CONF_BOILER_SWITCH)
                ): switch_selector,
            }
        )
    return vol.Schema(
        {
            vol.Required(
                CONF_BOILER_SWITCH, description=_suggested(defaults, CONF_BOILER_SWITCH)
            ): switch_selector,
            vol.Required(
                CONF_COLD_TOLERANCE,
                default=defaults.get(CONF_COLD_TOLERANCE, DEFAULT_COLD_TOLERANCE),
            ): _number_selector(0, 2, 0.1, "°C"),
            vol.Required(
                CONF_HOT_TOLERANCE,
                default=defaults.get(CONF_HOT_TOLERANCE, DEFAULT_HOT_TOLERANCE),
            ): _number_selector(0, 2, 0.1, "°C"),
            vol.Required(
                CONF_MIN_CYCLE, default=defaults.get(CONF_MIN_CYCLE, DEFAULT_MIN_CYCLE)
            ): _number_selector(0, 30, 1, "min"),
        }
    )


def _room_schema(defaults: dict[str, Any], add_another: bool) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ROOM_NAME, description=_suggested(defaults, CONF_ROOM_NAME)): str,
            vol.Required(
                CONF_ROOM_CLIMATE, description=_suggested(defaults, CONF_ROOM_CLIMATE)
            ): _entity_selector("climate", integration=BETTER_THERMOSTAT_DOMAIN),
            vol.Required(
                CONF_ROOM_VALVES, description=_suggested(defaults, CONF_ROOM_VALVES)
            ): _entity_selector("climate", multiple=True),
            vol.Required(
                CONF_ROOM_SENSOR, description=_suggested(defaults, CONF_ROOM_SENSOR)
            ): _entity_selector("sensor", device_class="temperature"),
            vol.Optional(
                CONF_ROOM_BATTERIES, description=_suggested(defaults, CONF_ROOM_BATTERIES)
            ): _entity_selector("sensor", multiple=True, device_class="battery"),
            vol.Optional(
                CONF_ROOM_WINDOWS, description=_suggested(defaults, CONF_ROOM_WINDOWS)
            ): _entity_selector("binary_sensor", multiple=True),
            vol.Required(CONF_ADD_ANOTHER, default=add_another): bool,
        }
    )


def _presence_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_PERSONS, description=_suggested(defaults, CONF_PERSONS)
            ): _entity_selector("person", multiple=True),
            vol.Required(
                CONF_AWAY_DELAY, default=defaults.get(CONF_AWAY_DELAY, DEFAULT_AWAY_DELAY)
            ): _number_selector(0, 240, 1, "min"),
            vol.Optional(CONF_NOTIFY, description=_suggested(defaults, CONF_NOTIFY)): str,
            vol.Required(
                CONF_NOTIFY_WINDOWS, default=defaults.get(CONF_NOTIFY_WINDOWS, True)
            ): bool,
            vol.Required(
                CONF_NOTIFY_BATTERY, default=defaults.get(CONF_NOTIFY_BATTERY, True)
            ): bool,
            vol.Required(
                CONF_BATTERY_THRESHOLD,
                default=defaults.get(CONF_BATTERY_THRESHOLD, DEFAULT_BATTERY_THRESHOLD),
            ): _number_selector(5, 50, 1, "%"),
        }
    )


def _dashboard_schema(defaults: dict[str, Any], with_regenerate: bool) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_CREATE_DASHBOARD, default=defaults.get(CONF_CREATE_DASHBOARD, True)
        ): bool,
        vol.Required(
            CONF_DASHBOARD_TITLE,
            default=defaults.get(CONF_DASHBOARD_TITLE, defaults.get(CONF_NAME, DEFAULT_NAME)),
        ): str,
    }
    if with_regenerate:
        schema[vol.Required(CONF_REGENERATE_DASHBOARD, default=False)] = bool
    return vol.Schema(schema)


# ---------- validation ----------


def _platform_of(hass: HomeAssistant, entity_id: str) -> str | None:
    entry = er.async_get(hass).async_get(entity_id)
    return entry.platform if entry else None


def _validate_boiler(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    climate = user_input.get(CONF_BOILER_CLIMATE)
    if climate and _platform_of(hass, climate) == BETTER_THERMOSTAT_DOMAIN:
        errors[CONF_BOILER_CLIMATE] = "boiler_is_room"
    return errors


def _validate_room(
    hass: HomeAssistant, user_input: dict[str, Any], rooms: list[dict[str, Any]]
) -> dict[str, str]:
    errors: dict[str, str] = {}
    valves = user_input.get(CONF_ROOM_VALVES) or []
    if not valves:
        errors[CONF_ROOM_VALVES] = "no_valves"
    elif sum(len(r[CONF_ROOM_VALVES]) for r in rooms) + len(valves) > MAX_VALVES:
        errors["base"] = "too_many_valves"
    if any(v in r[CONF_ROOM_VALVES] for r in rooms for v in valves):
        errors[CONF_ROOM_VALVES] = "valve_in_use"
    name = user_input[CONF_ROOM_NAME].strip()
    if not name or any(r[CONF_ROOM_NAME].lower() == name.lower() for r in rooms):
        errors[CONF_ROOM_NAME] = "duplicate_room"
    climate = user_input[CONF_ROOM_CLIMATE]
    if any(r[CONF_ROOM_CLIMATE] == climate for r in rooms):
        errors[CONF_ROOM_CLIMATE] = "climate_in_use"
    elif _platform_of(hass, climate) not in (None, BETTER_THERMOSTAT_DOMAIN):
        errors[CONF_ROOM_CLIMATE] = "not_better_thermostat"
    return errors


def _validate_notify(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    service = (user_input.get(CONF_NOTIFY) or "").strip()
    if not service:
        return {}
    name = service.removeprefix("notify.")
    if not hass.services.has_service("notify", name):
        return {CONF_NOTIFY: "notify_not_found"}
    user_input[CONF_NOTIFY] = f"notify.{name}"
    return {}


def _build_room(
    user_input: dict[str, Any], rooms: list[dict[str, Any]], keep_id: str | None
) -> dict[str, Any]:
    room_id = keep_id or slugify(user_input[CONF_ROOM_NAME]) or "room"
    used = {r[CONF_ROOM_ID] for r in rooms}
    base, index = room_id, 2
    while room_id in used:
        room_id = f"{base}_{index}"
        index += 1
    return {
        CONF_ROOM_ID: room_id,
        CONF_ROOM_NAME: user_input[CONF_ROOM_NAME].strip(),
        CONF_ROOM_CLIMATE: user_input[CONF_ROOM_CLIMATE],
        CONF_ROOM_VALVES: list(user_input.get(CONF_ROOM_VALVES) or []),
        CONF_ROOM_SENSOR: user_input[CONF_ROOM_SENSOR],
        CONF_ROOM_BATTERIES: list(user_input.get(CONF_ROOM_BATTERIES) or []),
        CONF_ROOM_WINDOWS: list(user_input.get(CONF_ROOM_WINDOWS) or []),
    }


def _room_placeholders(rooms: list[dict[str, Any]]) -> dict[str, str]:
    used = sum(len(r[CONF_ROOM_VALVES]) for r in rooms)
    return {
        "room_number": str(len(rooms) + 1),
        "valves_used": str(used),
        "valves_max": str(MAX_VALVES),
    }


def _valves_left(rooms: list[dict[str, Any]]) -> int:
    return MAX_VALVES - sum(len(r[CONF_ROOM_VALVES]) for r in rooms)


# ---------- config flow ----------


class AquecimentoNinjasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Installation wizard."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._rooms: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AquecimentoNinjasOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if BETTER_THERMOSTAT_DOMAIN not in self.hass.config.components:
            return self.async_abort(reason="better_thermostat_missing")
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_boiler()
        return self.async_show_form(step_id="user", data_schema=_user_schema(self._data))

    async def async_step_boiler(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        mode = self._data[CONF_BOILER_MODE]
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_boiler(self.hass, user_input)
            if not errors:
                self._data.update(user_input)
                return await self.async_step_room()
        return self.async_show_form(
            step_id="boiler",
            data_schema=_boiler_schema(mode, user_input or self._data),
            errors=errors,
        )

    async def async_step_room(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_room(self.hass, user_input, self._rooms)
            if not errors:
                self._rooms.append(_build_room(user_input, self._rooms, None))
                if user_input[CONF_ADD_ANOTHER] and _valves_left(self._rooms) > 0:
                    return self.async_show_form(
                        step_id="room",
                        data_schema=_room_schema({}, add_another=False),
                        description_placeholders=_room_placeholders(self._rooms),
                    )
                return await self.async_step_presence()
        return self.async_show_form(
            step_id="room",
            data_schema=_room_schema(user_input or {}, add_another=False),
            errors=errors,
            description_placeholders=_room_placeholders(self._rooms),
        )

    async def async_step_presence(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_notify(self.hass, user_input)
            if not errors:
                self._data.update(user_input)
                return await self.async_step_dashboard()
        return self.async_show_form(
            step_id="presence",
            data_schema=_presence_schema(user_input or self._data),
            errors=errors,
        )

    async def async_step_dashboard(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            self._data[CONF_ROOMS] = self._rooms
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return self.async_show_form(
            step_id="dashboard", data_schema=_dashboard_schema(self._data, False)
        )


# ---------- options flow ----------


class AquecimentoNinjasOptionsFlow(OptionsFlow):
    """Change the configuration after installation."""

    def __init__(self) -> None:
        self._rooms: list[dict[str, Any]] = []
        self._old_rooms: list[dict[str, Any]] = []

    @property
    def _config(self) -> dict[str, Any]:
        return merged_config(self.config_entry)

    def _save(self, changes: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **changes})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["presence", "boiler", "rooms", "dashboard"]
        )

    async def async_step_presence(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_notify(self.hass, user_input)
            if not errors:
                user_input.setdefault(CONF_PERSONS, [])
                user_input.setdefault(CONF_NOTIFY, "")
                return self._save(user_input)
        return self.async_show_form(
            step_id="presence",
            data_schema=_presence_schema(user_input or self._config),
            errors=errors,
        )

    async def async_step_boiler(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        mode = self._config[CONF_BOILER_MODE]
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_boiler(self.hass, user_input)
            if not errors:
                user_input.setdefault(CONF_BOILER_SWITCH, None)
                return self._save({**user_input, CONF_REGENERATE_DASHBOARD: True})
        return self.async_show_form(
            step_id="boiler",
            data_schema=_boiler_schema(mode, user_input or self._config),
            errors=errors,
        )

    async def async_step_rooms(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._old_rooms = list(self._config.get(CONF_ROOMS, []))
        self._rooms = []
        return await self.async_step_room()

    async def async_step_room(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        index = len(self._rooms)
        old = self._old_rooms[index] if index < len(self._old_rooms) else None
        if user_input is not None:
            errors = _validate_room(self.hass, user_input, self._rooms)
            if not errors:
                keep_id = old[CONF_ROOM_ID] if old else None
                self._rooms.append(_build_room(user_input, self._rooms, keep_id))
                if not (user_input[CONF_ADD_ANOTHER] and _valves_left(self._rooms) > 0):
                    return self._save(
                        {CONF_ROOMS: self._rooms, CONF_REGENERATE_DASHBOARD: True}
                    )
                index = len(self._rooms)
                old = self._old_rooms[index] if index < len(self._old_rooms) else None
                user_input = None
        defaults = user_input or old or {}
        more = index + 1 < len(self._old_rooms)
        return self.async_show_form(
            step_id="room",
            data_schema=_room_schema(defaults, add_another=more),
            errors=errors,
            description_placeholders=_room_placeholders(self._rooms),
        )

    async def async_step_dashboard(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(user_input)
        return self.async_show_form(
            step_id="dashboard", data_schema=_dashboard_schema(self._config, True)
        )
