"""Creates the Aquecimento Ninjas dashboard (views 'Heating' and 'Charts').

Uses Home Assistant's internal Lovelace storage classes; if they change in a future
release the integration keeps working and only the dashboard creation is skipped.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DASHBOARD_TITLE,
    DASHBOARD_ID,
    DASHBOARD_URL,
    DOCS_URL,
    DOMAIN,
)
from .controller import HeatingController

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:radiator"

TEXTS: dict[str, dict[str, str]] = {
    "pt": {
        "heating": "Aquecimento",
        "charts": "Gráficos",
        "mode_presence": "Modo e presença",
        "temperatures": "Temperaturas conforto / eco",
        "room_sensors": "Sensores de divisão",
        "use_for_boiler": "Usar na caldeira",
        "boiler_reads": "Temperatura lida pela caldeira",
        "boiler": "Caldeira",
        "batteries_windows": "Válvulas - bateria e janelas",
        "docs": "Documentação",
        "current": "🌡️ Temperaturas atuais",
        "boiler_today": "📊 Caldeira - estatísticas hoje",
        "last_reading": "⏱️ Última leitura dos sensores",
        "balance": "⚖️ Equilíbrio entre divisões",
        "rooms_24h": "🎯 Divisões - temperatura e objetivo (24h)",
        "boiler_24h": "🔥 Caldeira - temperatura e objetivo (24h)",
        "sensors_24h": "🌡️ Sensores de divisão (24h)",
        "weekly": "📈 Temperaturas - média semanal",
        "boiler_hours": "⏱️ Caldeira - horas ligada por dia (7 dias)",
        "battery_7d": "🔋 Bateria das válvulas (7 dias)",
        "average": "Média",
    },
    "en": {
        "heating": "Heating",
        "charts": "Charts",
        "mode_presence": "Mode and presence",
        "temperatures": "Comfort / eco temperatures",
        "room_sensors": "Room sensors",
        "use_for_boiler": "Use for boiler",
        "boiler_reads": "Temperature read by the boiler",
        "boiler": "Boiler",
        "batteries_windows": "Valves - battery and windows",
        "docs": "Documentation",
        "current": "🌡️ Current temperatures",
        "boiler_today": "📊 Boiler - today",
        "last_reading": "⏱️ Last sensor reading",
        "balance": "⚖️ Balance between rooms",
        "rooms_24h": "🎯 Rooms - temperature and target (24h)",
        "boiler_24h": "🔥 Boiler - temperature and target (24h)",
        "sensors_24h": "🌡️ Room sensors (24h)",
        "weekly": "📈 Temperatures - weekly average",
        "boiler_hours": "⏱️ Boiler - hours on per day (7 days)",
        "battery_7d": "🔋 Valve batteries (7 days)",
        "average": "Average",
    },
}


def _lovelace_dashboards(hass: HomeAssistant) -> dict[str, Any] | None:
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        data: Any = hass.data.get(LOVELACE_DATA)
    except ImportError:
        data = hass.data.get("lovelace")
    if data is None:
        return None
    if isinstance(data, dict):
        return data.get("dashboards")
    return getattr(data, "dashboards", None)


def _storage(hass: HomeAssistant, title: str) -> Any:
    from homeassistant.components.lovelace.dashboard import LovelaceStorage

    return LovelaceStorage(
        hass,
        {
            "id": DASHBOARD_ID,
            "url_path": DASHBOARD_URL,
            "title": title,
            "icon": ICON,
            "show_in_sidebar": True,
            "require_admin": False,
            "mode": "storage",
        },
    )


async def async_setup_dashboard(hass: HomeAssistant, entry: Any, force: bool = False) -> None:
    """Register the dashboard panel and write its config if missing (or forced)."""
    controller: HeatingController = entry.runtime_data
    title = controller.config.get(CONF_DASHBOARD_TITLE) or controller.config.get(CONF_NAME)
    try:
        dashboards = _lovelace_dashboards(hass)
        if dashboards is None:
            _LOGGER.warning("Lovelace is not loaded; dashboard not created")
            return
        storage = dashboards.get(DASHBOARD_URL)
        if storage is None:
            storage = _storage(hass, title)
            dashboards[DASHBOARD_URL] = storage
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            frontend_url_path=DASHBOARD_URL,
            sidebar_title=title,
            sidebar_icon=ICON,
            require_admin=False,
            config={"mode": "storage"},
            update=True,
        )
        try:
            existing = await storage.async_load(False)
        except Exception:  # noqa: BLE001 - ConfigNotFound when nothing saved yet
            existing = None
        if force or not existing:
            await storage.async_save(build_dashboard(hass, controller))
    except Exception:  # noqa: BLE001 - internal Lovelace API may change
        _LOGGER.exception(
            "Could not create the dashboard. The heating control keeps working; "
            "see the documentation to create it manually"
        )


@callback
def async_unload_dashboard(hass: HomeAssistant) -> None:
    """Remove the panel from the sidebar (config stays stored)."""
    try:
        frontend.async_remove_panel(hass, DASHBOARD_URL, warn_if_unknown=False)
        dashboards = _lovelace_dashboards(hass)
        if dashboards is not None:
            dashboards.pop(DASHBOARD_URL, None)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Dashboard panel was not registered")


async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Delete the stored dashboard config."""
    try:
        async_unload_dashboard(hass)
        await _storage(hass, DOMAIN).async_delete()
    except Exception:  # noqa: BLE001
        _LOGGER.debug("No dashboard to delete")


# ---------- dashboard content ----------


def build_dashboard(hass: HomeAssistant, c: HeatingController) -> dict[str, Any]:
    """Build the dashboard config for the configured rooms."""
    t = TEXTS[c.lang]
    registry = er.async_get(hass)
    entry_id = c.entry.entry_id

    def eid(domain: str, key: str, room_id: str | None = None) -> str | None:
        uid = f"{entry_id}_{room_id}_{key}" if room_id else f"{entry_id}_{key}"
        return registry.async_get_entity_id(domain, DOMAIN, uid)

    master = eid("switch", "master")
    away = eid("switch", "away")
    mode = eid("select", "mode")
    away_temp = eid("number", "away_temperature")
    reference = eid("sensor", "reference_temperature")
    average = eid("sensor", "average_temperature")
    minimum = eid("sensor", "minimum_temperature")
    maximum = eid("sensor", "maximum_temperature")
    spread = eid("sensor", "temperature_spread")
    on_time = eid("sensor", "boiler_on_time")
    cycles = eid("sensor", "boiler_cycles")
    avg_cycle = eid("sensor", "boiler_average_cycle")
    boiler = c.boiler_climate_id or eid("climate", "boiler")

    sliders: list[str | None] = []
    sensor_tiles: list[dict[str, Any]] = []
    room_thermostats: list[dict[str, Any]] = []
    batteries: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    for room in c.rooms:
        sliders += [eid("number", "comfort", room.id), eid("number", "eco", room.id)]
        sensor_tiles += [
            {"type": "tile", "entity": room.sensor, "name": room.name},
            {
                "type": "tile",
                "entity": eid("switch", "use_for_boiler", room.id),
                "name": t["use_for_boiler"],
                "tap_action": {"action": "toggle"},
            },
        ]
        room_thermostats.append(
            {
                "type": "thermostat",
                "entity": room.climate,
                "name": room.name,
                "grid_options": {"columns": 6, "rows": 3},
            }
        )
        batteries += [{"entity": b} for b in room.batteries]
        windows += [{"entity": w} for w in room.windows]

    heating_cards: list[dict[str, Any]] = [
        _entities(
            t["mode_presence"],
            [master, mode, away, away_temp] + [p for p in c.persons],
            show_header_toggle=False,
        ),
        _entities(t["temperatures"], sliders),
        {
            "type": "grid",
            "title": t["room_sensors"],
            "columns": 2,
            "square": False,
            "cards": sensor_tiles,
        },
        {
            "type": "tile",
            "entity": reference,
            "name": t["boiler_reads"],
            "state_content": ["state", "rooms"],
            "grid_options": {"columns": 12, "rows": 1},
        },
    ]
    if boiler:
        heating_cards.append({"type": "thermostat", "entity": boiler, "name": t["boiler"]})
    heating_cards += room_thermostats
    if batteries or windows:
        heating_cards.append(_entities(t["batteries_windows"], batteries + windows))
    heating_cards.append(
        {
            "type": "button",
            "name": t["docs"],
            "icon": "mdi:book-open-variant",
            "tap_action": {"action": "url", "url_path": DOCS_URL},
            "grid_options": {"columns": 12, "rows": 1},
        }
    )

    room_sensors = [{"entity": r.sensor, "name": r.name} for r in c.rooms]
    summary_cards = [
        _entities(
            t["current"],
            room_sensors + [{"type": "divider"}, average, minimum, maximum, reference],
        ),
        _entities(t["boiler_today"], [on_time, cycles, avg_cycle]),
        _entities(
            t["last_reading"],
            [{**s, "secondary_info": "last-updated"} for s in room_sensors],
        ),
        _entities(t["balance"], [spread]),
    ]
    graph_cards: list[dict[str, Any]] = [
        _history(t["rooms_24h"], [{"entity": r.climate, "name": r.name} for r in c.rooms], 24),
    ]
    if boiler:
        graph_cards.append(_history(t["boiler_24h"], [{"entity": boiler, "name": t["boiler"]}], 24))
    with_average = room_sensors + ([{"entity": average, "name": t["average"]}] if average else [])
    graph_cards += [
        _history(t["sensors_24h"], with_average, 24),
        {
            "type": "statistics-graph",
            "title": t["weekly"],
            "days_to_show": 7,
            "period": "hour",
            "chart_type": "line",
            "stat_types": ["mean"],
            "entities": with_average,
        },
    ]
    if on_time:
        graph_cards.append(
            {
                "type": "statistics-graph",
                "title": t["boiler_hours"],
                "days_to_show": 7,
                "period": "day",
                "chart_type": "bar",
                "stat_types": ["max"],
                "entities": [on_time],
            }
        )
    if batteries:
        graph_cards.append(_history(t["battery_7d"], batteries, 168))

    return {
        "title": t["heating"],
        "views": [
            {
                "title": t["heating"],
                "path": "heating",
                "icon": ICON,
                "type": "sections",
                "max_columns": 5,
                "sections": [{"type": "grid", "column_span": 5, "cards": heating_cards}],
            },
            {
                "title": t["charts"],
                "path": "charts",
                "icon": "mdi:chart-line",
                "type": "sections",
                "max_columns": 4,
                "sections": [
                    {"type": "grid", "cards": summary_cards},
                    {"type": "grid", "column_span": 3, "cards": graph_cards},
                ],
            },
        ],
    }


def _entities(title: str, entities: list[Any], **extra: Any) -> dict[str, Any]:
    return {
        "type": "entities",
        "title": title,
        "entities": [e for e in entities if e],
        **extra,
    }


def _history(title: str, entities: list[dict[str, Any]], hours: int) -> dict[str, Any]:
    return {
        "type": "history-graph",
        "title": title,
        "hours_to_show": hours,
        "entities": [e for e in entities if e.get("entity")],
    }
