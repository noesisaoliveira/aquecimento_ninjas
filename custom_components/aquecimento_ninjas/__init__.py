"""Aquecimento Ninjas: per-room heating with Better Thermostat."""

from __future__ import annotations

import importlib
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CREATE_DASHBOARD,
    CONF_REGENERATE_DASHBOARD,
    DOMAIN,
    PLATFORMS,
)
from .controller import HeatingController
from .dashboard import (
    async_remove_dashboard,
    async_setup_dashboard,
    async_unload_dashboard,
)

_LOGGER = logging.getLogger(__name__)

type AquecimentoConfigEntry = ConfigEntry[HeatingController]

SERVICE_CREATE_DASHBOARD = "create_dashboard"
SERVICE_START_BOOST = "start_boost"
SERVICE_STOP_BOOST = "stop_boost"


def _import_platforms() -> None:
    for platform in PLATFORMS:
        importlib.import_module(f".{platform.value}", __package__)


async def async_setup_entry(hass: HomeAssistant, entry: AquecimentoConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    await hass.async_add_import_executor_job(_import_platforms)
    force_dashboard = False
    if entry.options.get(CONF_REGENERATE_DASHBOARD):
        force_dashboard = True
        options = dict(entry.options)
        options.pop(CONF_REGENERATE_DASHBOARD)
        hass.config_entries.async_update_entry(entry, options=options)

    controller = HeatingController(hass, entry)
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_stale_entities(hass, entry, controller)

    controller.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    if controller.config.get(CONF_CREATE_DASHBOARD, True):
        await async_setup_dashboard(hass, entry, force=force_dashboard)

    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AquecimentoConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.async_stop()
        async_unload_dashboard(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: AquecimentoConfigEntry) -> None:
    """Delete the generated dashboard when the integration is removed."""
    await async_remove_dashboard(hass)


async def _async_update_listener(hass: HomeAssistant, entry: AquecimentoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _remove_stale_entities(
    hass: HomeAssistant, entry: ConfigEntry, controller: HeatingController
) -> None:
    """Remove entities of rooms that no longer exist."""
    registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id not in controller.unique_ids:
            registry.async_remove(reg_entry.entity_id)


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_CREATE_DASHBOARD):
        return

    def _loaded() -> list[AquecimentoConfigEntry]:
        return [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]

    def _float(value: object) -> float | None:
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    async def _create_dashboard(call: ServiceCall) -> None:
        for entry in _loaded():
            await async_setup_dashboard(hass, entry, force=True)

    async def _start_boost(call: ServiceCall) -> None:
        for entry in _loaded():
            await entry.runtime_data.async_start_boost(
                _float(call.data.get("hours")), _float(call.data.get("temperature"))
            )

    async def _stop_boost(call: ServiceCall) -> None:
        for entry in _loaded():
            await entry.runtime_data.async_stop_boost()

    hass.services.async_register(DOMAIN, SERVICE_CREATE_DASHBOARD, _create_dashboard)
    hass.services.async_register(DOMAIN, SERVICE_START_BOOST, _start_boost)
    hass.services.async_register(DOMAIN, SERVICE_STOP_BOOST, _stop_boost)
