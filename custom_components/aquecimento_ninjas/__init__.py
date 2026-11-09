"""Aquecimento Ninjas: per-room heating with Better Thermostat."""

from __future__ import annotations

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


async def async_setup_entry(hass: HomeAssistant, entry: AquecimentoConfigEntry) -> bool:
    """Set up the integration from a config entry."""
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

    async def _create_dashboard(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is ConfigEntryState.LOADED:
                await async_setup_dashboard(hass, entry, force=True)

    hass.services.async_register(DOMAIN, SERVICE_CREATE_DASHBOARD, _create_dashboard)
