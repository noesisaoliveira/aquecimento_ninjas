"""Creates the Aquecimento Ninjas dashboard.

Two layouts:
- enhanced: Mushroom cards (+ ApexCharts, mini-graph and Scheduler cards when installed)
- standard: only built-in Home Assistant cards

Uses Home Assistant's internal Lovelace storage classes; if they change in a future
release the integration keeps working and only the dashboard creation is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DASHBOARD_STYLE,
    CONF_DASHBOARD_TITLE,
    CONF_SCHEDULE_ENTITY,
    CONF_SCHEDULER_TYPE,
    DASHBOARD_ID,
    DASHBOARD_URL,
    DOCS_URL,
    DOMAIN,
    SCHEDULER_CARD,
    SCHEDULER_ENTITY,
    STYLE_AUTO,
    STYLE_STANDARD,
)
from .controller import HeatingController, Room

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:radiator"

CARD_RESOURCES = {
    "mushroom": "mushroom",
    "apexcharts": "apexcharts-card",
    "mini_graph": "mini-graph-card",
    "scheduler": "scheduler-card",
}

TEXTS: dict[str, dict[str, str]] = {
    "pt": {
        "heating": "Aquecimento",
        "schedule": "Horário",
        "maintenance": "Manutenção",
        "charts": "Gráficos",
        "boiler": "Caldeira",
        "boiler_reads": "Temperatura lida pela caldeira",
        "mode_presence": "Modo e presença",
        "heating_on": "Aquecimento ligado",
        "away": "Ausente",
        "mode": "Modo",
        "away_temp": "Temp. ausente",
        "boost": "Boost",
        "boost_on": "Boost ativo",
        "boost_off": "Boost desligado",
        "ends_at": "Termina às",
        "left": "faltam",
        "no_boost": "Sem boost em curso",
        "duration": "Duração (h)",
        "temperature": "Temperatura",
        "start_boost": "Iniciar boost",
        "start_boost_sub": "Liga o aquecimento · só divisões selecionadas",
        "stop_boost": "Parar boost",
        "stop_boost_sub": "Repõe o estado anterior",
        "half_hour": "30 min",
        "one_hour": "1 hora",
        "two_hours": "2 horas",
        "room_temp": "Temperatura",
        "use_for_boiler": "Usar na caldeira",
        "comfort": "Conforto",
        "eco": "Eco",
        "docs": "Documentação",
        "docs_sub": "Abrir no GitHub",
        "weekly_schedule": "Horário semanal",
        "valves": "Válvulas - bateria e janelas",
        "window_open": "Janela aberta",
        "window_closed": "Janela fechada",
        "summary": "Resumo",
        "current": "Temperaturas atuais",
        "balance": "Equilíbrio e leituras",
        "spread": "Mais quente ↔ mais fria",
        "last_reading": "Última leitura dos sensores",
        "history": "Histórico",
        "rooms_temp_24h": "Divisões - temperatura (24h)",
        "rooms_24h": "Divisões - temperatura e objetivo (24h)",
        "boiler_24h": "Caldeira - temperatura e objetivo (24h)",
        "sensors_24h": "Sensores de divisão (24h)",
        "weekly": "Temperaturas - média semanal",
        "boiler_hours": "Caldeira - horas ligada por dia (7 dias)",
        "battery_7d": "Bateria das válvulas (7 dias)",
        "average": "Média",
        "hours_on": "Horas ligada",
        "room_sensors": "Sensores de divisão",
        "temperatures": "Temperaturas conforto / eco",
        "diagnostics": "Diagnóstico",
        "window_temp": "Detetar janela pela queda de temperatura",
        "all_ok": "Tudo OK",
        "paused": "Em pausa (janela)",
        "sensor_problem": "Sensor sem dados · modo de emergência",
        "not_heating": "Não chega à temperatura",
        "emergency": "Emergência - ligar caldeira",
        "emergency_btn": "Ligar caldeira (pede PIN)",
    },
    "en": {
        "heating": "Heating",
        "schedule": "Schedule",
        "maintenance": "Maintenance",
        "charts": "Charts",
        "boiler": "Boiler",
        "boiler_reads": "Temperature read by the boiler",
        "mode_presence": "Mode and presence",
        "heating_on": "Heating on",
        "away": "Away",
        "mode": "Mode",
        "away_temp": "Away temp.",
        "boost": "Boost",
        "boost_on": "Boost active",
        "boost_off": "Boost off",
        "ends_at": "Ends at",
        "left": "left",
        "no_boost": "No boost running",
        "duration": "Duration (h)",
        "temperature": "Temperature",
        "start_boost": "Start boost",
        "start_boost_sub": "Turns heating on · selected rooms only",
        "stop_boost": "Stop boost",
        "stop_boost_sub": "Restores the previous state",
        "half_hour": "30 min",
        "one_hour": "1 hour",
        "two_hours": "2 hours",
        "room_temp": "Temperature",
        "use_for_boiler": "Use for boiler",
        "comfort": "Comfort",
        "eco": "Eco",
        "docs": "Documentation",
        "docs_sub": "Open on GitHub",
        "weekly_schedule": "Weekly schedule",
        "valves": "Valves - battery and windows",
        "window_open": "Window open",
        "window_closed": "Window closed",
        "summary": "Summary",
        "current": "Current temperatures",
        "balance": "Balance and readings",
        "spread": "Warmest ↔ coldest",
        "last_reading": "Last sensor reading",
        "history": "History",
        "rooms_temp_24h": "Rooms - temperature (24h)",
        "rooms_24h": "Rooms - temperature and target (24h)",
        "boiler_24h": "Boiler - temperature and target (24h)",
        "sensors_24h": "Room sensors (24h)",
        "weekly": "Temperatures - weekly average",
        "boiler_hours": "Boiler - hours on per day (7 days)",
        "battery_7d": "Valve batteries (7 days)",
        "average": "Average",
        "hours_on": "Hours on",
        "room_sensors": "Room sensors",
        "temperatures": "Comfort / eco temperatures",
        "diagnostics": "Diagnostics",
        "window_temp": "Detect window by temperature drop",
        "all_ok": "All OK",
        "paused": "Paused (window)",
        "sensor_problem": "Sensor not reporting · emergency mode",
        "not_heating": "Not reaching target",
        "emergency": "Emergency - boiler on",
        "emergency_btn": "Boiler on (asks for PIN)",
    },
}


# ---------- Lovelace plumbing ----------


def _lovelace_data(hass: HomeAssistant) -> Any:
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        return hass.data.get(LOVELACE_DATA)
    except ImportError:
        return hass.data.get("lovelace")


def _lovelace_dashboards(hass: HomeAssistant) -> dict[str, Any] | None:
    data = _lovelace_data(hass)
    if data is None:
        return None
    if isinstance(data, dict):
        return data.get("dashboards")
    return getattr(data, "dashboards", None)


async def _installed_cards(hass: HomeAssistant) -> set[str]:
    """Which optional custom cards are registered as Lovelace resources."""
    try:
        data = _lovelace_data(hass)
        resources = data.get("resources") if isinstance(data, dict) else getattr(data, "resources", None)
        if resources is None:
            return set()
        if hasattr(resources, "async_get_info"):
            await resources.async_get_info()
        urls = " ".join(str(item.get("url", "")) for item in resources.async_items())
    except Exception:  # noqa: BLE001 - internal API
        return set()
    cards = {name for name, marker in CARD_RESOURCES.items() if marker in urls}
    if "scheduler" in cards and "scheduler" not in hass.config.components:
        cards.discard("scheduler")
    return cards


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
            cards = await _installed_cards(hass)
            await storage.async_save(build_dashboard(hass, controller, cards))
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


# ---------- entity ids ----------


@dataclass
class Ids:
    """Entity ids used on the dashboard."""

    master: str | None = None
    away: str | None = None
    mode: str | None = None
    away_temp: str | None = None
    boost: str | None = None
    boost_end: str | None = None
    boost_hours: str | None = None
    boost_temp: str | None = None
    reference: str | None = None
    average: str | None = None
    minimum: str | None = None
    maximum: str | None = None
    spread: str | None = None
    on_time: str | None = None
    cycles: str | None = None
    avg_cycle: str | None = None
    boiler: str | None = None
    window_temp: str | None = None
    emergency: str | None = None
    comfort: dict[str, str | None] = field(default_factory=dict)
    eco: dict[str, str | None] = field(default_factory=dict)
    use_for_boiler: dict[str, str | None] = field(default_factory=dict)
    boost_room: dict[str, str | None] = field(default_factory=dict)
    window_open: dict[str, str | None] = field(default_factory=dict)
    sensor_problem: dict[str, str | None] = field(default_factory=dict)
    not_heating: dict[str, str | None] = field(default_factory=dict)


def _ids(hass: HomeAssistant, c: HeatingController) -> Ids:
    registry = er.async_get(hass)
    entry_id = c.entry.entry_id

    def eid(domain: str, key: str, room_id: str | None = None) -> str | None:
        uid = f"{entry_id}_{room_id}_{key}" if room_id else f"{entry_id}_{key}"
        return registry.async_get_entity_id(domain, DOMAIN, uid)

    ids = Ids(
        master=eid("switch", "master"),
        away=eid("switch", "away"),
        mode=eid("select", "mode"),
        away_temp=eid("number", "away_temperature"),
        boost=eid("switch", "boost"),
        boost_end=eid("sensor", "boost_end"),
        boost_hours=eid("number", "boost_hours"),
        boost_temp=eid("number", "boost_temperature"),
        reference=eid("sensor", "reference_temperature"),
        average=eid("sensor", "average_temperature"),
        minimum=eid("sensor", "minimum_temperature"),
        maximum=eid("sensor", "maximum_temperature"),
        spread=eid("sensor", "temperature_spread"),
        on_time=eid("sensor", "boiler_on_time"),
        cycles=eid("sensor", "boiler_cycles"),
        avg_cycle=eid("sensor", "boiler_average_cycle"),
        boiler=c.boiler_climate_id or eid("climate", "boiler"),
        window_temp=eid("switch", "window_temperature_detection"),
        emergency=eid("alarm_control_panel", "emergency") if c.emergency_pin else None,
    )
    for room in c.rooms:
        ids.comfort[room.id] = eid("number", "comfort", room.id)
        ids.eco[room.id] = eid("number", "eco", room.id)
        ids.use_for_boiler[room.id] = eid("switch", "use_for_boiler", room.id)
        ids.boost_room[room.id] = eid("switch", "boost_room", room.id)
        ids.window_open[room.id] = eid("binary_sensor", "window_open", room.id)
        ids.sensor_problem[room.id] = eid("binary_sensor", "sensor_problem", room.id)
        ids.not_heating[room.id] = eid("binary_sensor", "not_heating", room.id)
    return ids


def build_dashboard(
    hass: HomeAssistant, c: HeatingController, cards: set[str]
) -> dict[str, Any]:
    """Build the dashboard config for the configured rooms."""
    style = c.config.get(CONF_DASHBOARD_STYLE, STYLE_AUTO)
    ids = _ids(hass, c)
    t = TEXTS[c.lang]
    if style == STYLE_STANDARD or (style == STYLE_AUTO and "mushroom" not in cards):
        views = _standard_views(c, ids, t)
    else:
        views = _enhanced_views(c, ids, t, cards)
    if c.config.get(CONF_SCHEDULER_TYPE, SCHEDULER_CARD) == SCHEDULER_ENTITY:
        schedule_entity = c.config.get(CONF_SCHEDULE_ENTITY)
        if schedule_entity:
            views.insert(1, _schedule_entity_view(schedule_entity, t))
    return {"title": t["heating"], "views": views}


# ---------- helpers ----------


def _clean(items: list[Any]) -> list[Any]:
    return [i for i in items if i]


def _entities(title: str, entities: list[Any], **extra: Any) -> dict[str, Any]:
    return {"type": "entities", "title": title, "entities": _clean(entities), **extra}


def _history(title: str, entities: list[dict[str, Any]], hours: int) -> dict[str, Any]:
    return {
        "type": "history-graph",
        "title": title,
        "hours_to_show": hours,
        "entities": [e for e in entities if e.get("entity")],
    }


def _statistics(title: str, entities: list[Any], period: str, chart: str, stat: str) -> dict[str, Any]:
    return {
        "type": "statistics-graph",
        "title": title,
        "days_to_show": 7,
        "period": period,
        "chart_type": chart,
        "stat_types": [stat],
        "entities": _clean(entities),
    }


def _heading(text: str, icon: str, **extra: Any) -> dict[str, Any]:
    return {"type": "heading", "heading": text, "icon": icon, **extra}


def _section(cards: list[Any], span: int | None = None) -> dict[str, Any]:
    section: dict[str, Any] = {"type": "grid", "cards": _clean(cards)}
    if span:
        section["column_span"] = span
    return section


def _view(title: str, path: str, icon: str, sections: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "title": title,
        "path": path,
        "icon": icon,
        "type": "sections",
        "max_columns": 4,
        "sections": sections,
        **extra,
    }


def _room_icon(index: int) -> str:
    return "mdi:sofa" if index == 0 else "mdi:bed"


def _room_sensors(c: HeatingController, t: dict[str, str], ids: Ids) -> list[dict[str, Any]]:
    sensors = [{"entity": r.sensor, "name": r.name} for r in c.rooms]
    if ids.average:
        sensors.append({"entity": ids.average, "name": t["average"]})
    return sensors


def _common_charts(c: HeatingController, ids: Ids, t: dict[str, str]) -> list[dict[str, Any]]:
    charts = [
        _history(t["rooms_24h"], [{"entity": r.climate, "name": r.name} for r in c.rooms], 24)
    ]
    if ids.boiler:
        charts.append(_history(t["boiler_24h"], [{"entity": ids.boiler, "name": t["boiler"]}], 24))
    return charts


def _weekly_charts(c: HeatingController, ids: Ids, t: dict[str, str]) -> list[dict[str, Any]]:
    charts = [_statistics(t["weekly"], _room_sensors(c, t, ids), "hour", "line", "mean")]
    if ids.on_time:
        charts.append(
            _statistics(
                t["boiler_hours"], [{"entity": ids.on_time, "name": t["hours_on"]}],
                "day", "bar", "max",
            )
        )
    batteries = [{"entity": b} for r in c.rooms for b in r.batteries]
    if batteries:
        charts.append(_history(t["battery_7d"], batteries, 168))
    return charts


# ---------- standard layout (built-in cards only) ----------


def _standard_views(c: HeatingController, ids: Ids, t: dict[str, str]) -> list[dict[str, Any]]:
    sliders: list[str | None] = []
    sensor_tiles: list[dict[str, Any]] = []
    thermostats: list[dict[str, Any]] = []
    for room in c.rooms:
        sliders += [ids.comfort[room.id], ids.eco[room.id]]
        sensor_tiles += [
            {"type": "tile", "entity": room.sensor, "name": room.name},
            {
                "type": "tile",
                "entity": ids.use_for_boiler[room.id],
                "name": t["use_for_boiler"],
                "tap_action": {"action": "toggle"},
            },
        ]
        thermostats.append(
            {
                "type": "thermostat",
                "entity": room.climate,
                "name": room.name,
                "grid_options": {"columns": 6, "rows": 3},
            }
        )
    valves = [{"entity": e} for r in c.rooms for e in r.batteries + r.windows]

    heating_cards: list[Any] = [
        _entities(
            t["mode_presence"],
            [ids.master, ids.mode, ids.away, ids.away_temp, *c.persons],
            show_header_toggle=False,
        ),
        _entities(
            t["boost"],
            [ids.boost, ids.boost_end, ids.boost_hours, ids.boost_temp,
             *[ids.boost_room[r.id] for r in c.rooms]],
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
            "entity": ids.reference,
            "name": t["boiler_reads"],
            "state_content": ["state", "rooms"],
            "grid_options": {"columns": 12, "rows": 1},
        },
    ]
    if ids.boiler:
        heating_cards.append({"type": "thermostat", "entity": ids.boiler, "name": t["boiler"]})
    heating_cards += thermostats
    heating_cards.append(_diagnostics_entities(c, ids, t))
    if ids.emergency:
        heating_cards.append(
            {
                "type": "alarm-panel",
                "entity": ids.emergency,
                "name": t["emergency_btn"],
                "states": ["arm_away"],
            }
        )
    if valves:
        heating_cards.append(_entities(t["valves"], valves))
    heating_cards.append(_docs_button(t))

    room_sensors = [{"entity": r.sensor, "name": r.name} for r in c.rooms]
    summary = [
        _entities(
            t["current"],
            room_sensors + [{"type": "divider"}, ids.average, ids.minimum, ids.maximum, ids.reference],
        ),
        _entities(t["summary"], [ids.on_time, ids.cycles, ids.avg_cycle]),
        _entities(
            t["last_reading"], [{**s, "secondary_info": "last-updated"} for s in room_sensors]
        ),
        _entities(t["balance"], [ids.spread]),
    ]
    graphs = (
        _common_charts(c, ids, t)
        + [_history(t["sensors_24h"], _room_sensors(c, t, ids), 24)]
        + _weekly_charts(c, ids, t)
    )
    return [
        _view(t["heating"], "heating", ICON, [_section(heating_cards, 4)]),
        _view(
            t["charts"], "charts", "mdi:chart-line",
            [_section(summary), _section(graphs, 3)],
        ),
    ]


def _docs_button(t: dict[str, str]) -> dict[str, Any]:
    return {
        "type": "button",
        "name": t["docs"],
        "icon": "mdi:book-open-variant",
        "tap_action": {"action": "url", "url_path": DOCS_URL},
        "grid_options": {"columns": 12, "rows": 1},
    }


def _diagnostics_entities(c: HeatingController, ids: Ids, t: dict[str, str]) -> dict[str, Any]:
    rows: list[Any] = [ids.window_temp]
    for room in c.rooms:
        rows += [
            {"type": "section", "label": room.name},
            ids.window_open[room.id],
            ids.sensor_problem[room.id],
            ids.not_heating[room.id],
        ]
    return _entities(t["diagnostics"], rows, show_header_toggle=False)


# ---------- enhanced layout (Mushroom & friends) ----------


def _chip(entity: str | None, icon: str, color: str, toggle: bool = False) -> dict[str, Any] | None:
    if not entity:
        return None
    chip: dict[str, Any] = {"type": "entity", "entity": entity, "icon": icon, "icon_color": color}
    if toggle:
        chip["tap_action"] = {"action": "toggle"}
    return chip


def _m_entity(entity: str | None, name: str, icon: str, color: str, **extra: Any) -> dict[str, Any] | None:
    if not entity:
        return None
    card: dict[str, Any] = {
        "type": "custom:mushroom-entity-card",
        "entity": entity,
        "icon": icon,
        "icon_color": color,
        **extra,
    }
    if name:
        card["name"] = name
    return card


def _m_toggle(entity: str | None, name: str, icon: str, color: str, **extra: Any) -> dict[str, Any] | None:
    return _m_entity(entity, name, icon, color, tap_action={"action": "toggle"}, **extra)


def _m_number(entity: str | None, name: str, icon: str, color: str) -> dict[str, Any] | None:
    if not entity:
        return None
    return {
        "type": "custom:mushroom-number-card",
        "entity": entity,
        "name": name,
        "icon": icon,
        "icon_color": color,
        "display_mode": "buttons",
    }


def _m_climate(entity: str | None, name: str) -> dict[str, Any] | None:
    if not entity:
        return None
    return {
        "type": "custom:mushroom-climate-card",
        "entity": entity,
        "name": name,
        "show_temperature_control": True,
        "collapsible_controls": False,
        "layout": "horizontal",
    }


def _m_action(primary: str, icon: str, color: str, service: str, data: dict[str, Any] | None = None,
              secondary: str | None = None, columns: int = 12, vertical: bool = False) -> dict[str, Any]:
    action: dict[str, Any] = {"action": "perform-action", "perform_action": service}
    if data:
        action["data"] = data
    card: dict[str, Any] = {
        "type": "custom:mushroom-template-card",
        "primary": primary,
        "icon": icon,
        "icon_color": color,
        "tap_action": action,
        "grid_options": {"columns": columns},
    }
    if secondary:
        card["secondary"] = secondary
    if vertical:
        card["layout"] = "vertical"
    return card


def _enhanced_views(
    c: HeatingController, ids: Ids, t: dict[str, str], cards: set[str]
) -> list[dict[str, Any]]:
    views = [_enhanced_heating(c, ids, t)]
    if (
        "scheduler" in cards
        and ids.mode
        and c.config.get(CONF_SCHEDULER_TYPE, SCHEDULER_CARD) == SCHEDULER_CARD
    ):
        views.append(_schedule_view(ids, t))
    views.append(_maintenance_view(c, ids, t))
    views.append(_enhanced_charts(c, ids, t, cards))
    return views


def _enhanced_heating(c: HeatingController, ids: Ids, t: dict[str, str]) -> dict[str, Any]:
    header = _section(
        [
            {"type": "heading", "heading": t["heating"], "heading_style": "title", "icon": ICON},
            {
                "type": "custom:mushroom-chips-card",
                "alignment": "start",
                "chips": _clean(
                    [
                        _chip(ids.master, "mdi:power", "orange", toggle=True),
                        _chip(ids.mode, "mdi:tune-variant", "purple"),
                        _chip(ids.away, "mdi:home-export-outline", "blue", toggle=True),
                        _chip(ids.boiler, "mdi:fire", "red"),
                        _chip(ids.boost, "mdi:fire-circle", "red", toggle=True),
                        _chip(ids.average, "mdi:home-thermometer", "green"),
                    ]
                ),
            },
        ],
        4,
    )

    boiler = _section(
        [
            _heading(t["boiler"], "mdi:fire"),
            _m_climate(ids.boiler, t["boiler"]),
            {
                "type": "custom:mushroom-template-card",
                "entity": ids.reference,
                "primary": t["boiler_reads"],
                "secondary": (
                    f"{{{{ states('{ids.reference}') }}}}°C · "
                    f"{{{{ state_attr('{ids.reference}', 'rooms') }}}}"
                ),
                "icon": "mdi:thermometer-auto",
                "icon_color": "orange",
                "layout": "horizontal",
                "grid_options": {"columns": 12},
            },
        ]
    )

    presence = _section(
        [
            _heading(t["mode_presence"], "mdi:account-clock"),
            _m_toggle(ids.master, t["heating_on"], "mdi:power", "orange", grid_options={"columns": 12}),
            _m_toggle(ids.away, t["away"], "mdi:home-export-outline", "blue", grid_options={"columns": 12}),
            {
                "type": "custom:mushroom-select-card",
                "entity": ids.mode,
                "name": t["mode"],
                "icon": "mdi:tune-variant",
                "icon_color": "purple",
            }
            if ids.mode
            else None,
            _m_number(ids.away_temp, t["away_temp"], "mdi:snowflake-thermometer", "blue"),
            *[
                _m_entity(p, "", "mdi:account", "teal", grid_options={"columns": 6})
                for p in c.persons
            ],
        ]
    )

    sections = [header, boiler, presence, _boost_section(c, ids, t)]
    for index, room in enumerate(c.rooms):
        icon = _room_icon(index)
        sections.append(
            _section(
                [
                    _heading(room.name, icon),
                    _m_climate(room.climate, room.name),
                    _m_entity(room.sensor, t["room_temp"], "mdi:thermometer", "red"),
                    _m_toggle(ids.use_for_boiler[room.id], t["use_for_boiler"], ICON, "orange"),
                    _m_number(ids.comfort[room.id], t["comfort"], "mdi:sun-thermometer", "orange"),
                    _m_number(ids.eco[room.id], t["eco"], "mdi:leaf", "green"),
                ]
            )
        )
    sections.append(
        _section(
            [
                _heading(t["docs"], "mdi:book-open-variant"),
                {
                    "type": "custom:mushroom-template-card",
                    "primary": t["docs"],
                    "secondary": t["docs_sub"],
                    "icon": "mdi:book-open-variant",
                    "icon_color": "blue",
                    "tap_action": {"action": "url", "url_path": DOCS_URL},
                    "grid_options": {"columns": 12},
                },
            ],
            2,
        )
    )
    return _view(t["heating"], "heating", ICON, sections, dense_section_placement=True)


def _boost_section(c: HeatingController, ids: Ids, t: dict[str, str]) -> dict[str, Any]:
    boost, end = ids.boost, ids.boost_end
    service = f"{DOMAIN}.start_boost"
    columns = max(3, 12 // max(1, len(c.rooms)))
    status = (
        {
            "type": "custom:mushroom-template-card",
            "entity": boost,
            "primary": (
                f"{{{{ '{t['boost_on']}' if is_state('{boost}', 'on') else '{t['boost_off']}' }}}}"
            ),
            "secondary": (
                f"{{% if is_state('{boost}', 'on') and states('{end}') not in ['unknown', 'unavailable'] %}}"
                f"{t['ends_at']} {{{{ as_local(as_datetime(states('{end}'))).strftime('%H:%M') }}}} · "
                f"{t['left']} {{{{ ((as_datetime(states('{end}')) - now()).total_seconds() / 60) | round(0) | int }}}} min"
                f"{{% else %}}{t['no_boost']}{{% endif %}}"
            ),
            "icon": "mdi:fire-circle",
            "icon_color": f"{{{{ 'red' if is_state('{boost}', 'on') else 'disabled' }}}}",
            "tap_action": {"action": "toggle"},
            "grid_options": {"columns": 12},
        }
        if boost and end
        else None
    )
    return _section(
        [
            _heading(t["boost"], "mdi:fire-circle"),
            status,
            *[
                _m_toggle(
                    ids.boost_room[room.id], room.name, _room_icon(i), "red",
                    layout="vertical", secondary_info="none", grid_options={"columns": columns},
                )
                for i, room in enumerate(c.rooms)
            ],
            _m_number(ids.boost_hours, t["duration"], "mdi:timer-outline", "orange"),
            _m_number(ids.boost_temp, t["temperature"], "mdi:thermometer-plus", "red"),
            _m_action(t["start_boost"], "mdi:fire", "red", service, secondary=t["start_boost_sub"]),
            _m_action(t["half_hour"], "mdi:timer-outline", "orange", service, {"hours": 0.5}, columns=4, vertical=True),
            _m_action(t["one_hour"], "mdi:timer-outline", "orange", service, {"hours": 1}, columns=4, vertical=True),
            _m_action(t["two_hours"], "mdi:timer-outline", "orange", service, {"hours": 2}, columns=4, vertical=True),
            _m_action(
                t["stop_boost"], "mdi:fire-off", "blue", f"{DOMAIN}.stop_boost",
                secondary=t["stop_boost_sub"],
            ),
        ]
    )


def _schedule_view(ids: Ids, t: dict[str, str]) -> dict[str, Any]:
    return _view(
        t["schedule"], "schedule", "mdi:calendar-clock",
        [
            _section(
                [
                    _heading(t["weekly_schedule"], "mdi:calendar-clock"),
                    {
                        "type": "custom:scheduler-card",
                        "title": False,
                        "include": [ids.mode],
                        "exclude": [],
                        "discover_existing": False,
                        "show_header_toggle": False,
                        "time_step": 5,
                    },
                ],
                4,
            )
        ],
    )


def _schedule_entity_view(entity_id: str, t: dict[str, str]) -> dict[str, Any]:
    return _view(
        t["schedule"], "schedule", "mdi:calendar-clock",
        [
            _section(
                [
                    _heading(t["weekly_schedule"], "mdi:calendar-clock"),
                    {
                        "type": "tile",
                        "entity": entity_id,
                        "name": t["schedule"],
                        "tap_action": {"action": "more-info"},
                    },
                ],
                4,
            )
        ],
    )


def _valve_card(room: Room, t: dict[str, str]) -> dict[str, Any]:
    batteries = ", ".join(f"states('{b}')" for b in room.batteries)
    windows = ", ".join(f"'{w}'" for w in room.windows)
    battery_txt = (
        f"🔋 {{{{ [{batteries}] | map('int', 0) | map('string') | join('% / ') }}}}%"
        if room.batteries
        else ""
    )
    window_txt = (
        f"{{{{ '{t['window_open']}' if [{windows}] | select('is_state', 'on') | list | count > 0 "
        f"else '{t['window_closed']}' }}}}"
        if room.windows
        else ""
    )
    open_test = f"[{windows}] | select('is_state', 'on') | list | count > 0" if room.windows else "false"
    low_test = (
        f"[{batteries}] | map('int', 100) | min < 20" if room.batteries else "false"
    )
    return {
        "type": "custom:mushroom-template-card",
        "primary": room.name,
        "secondary": " · ".join(x for x in (battery_txt, window_txt) if x),
        "icon": "mdi:valve",
        "icon_color": (
            f"{{{{ 'red' if {open_test} else ('orange' if {low_test} else 'green') }}}}"
        ),
        "entity": (room.batteries or room.windows or [room.climate])[0],
        "grid_options": {"columns": 12},
    }


def _status_card(room: Room, ids: Ids, t: dict[str, str]) -> dict[str, Any]:
    win, sensor, heating = ids.window_open[room.id], ids.sensor_problem[room.id], ids.not_heating[room.id]
    checks = [(win, t["paused"]), (sensor, t["sensor_problem"]), (heating, t["not_heating"])]
    parts = " ".join(
        f"{{% if is_state('{e}', 'on') %}}{{% set ns.l = ns.l + ['{label}'] %}}{{% endif %}}"
        for e, label in checks
        if e
    )
    any_on = " or ".join(f"is_state('{e}', 'on')" for e, _ in checks if e) or "false"
    return {
        "type": "custom:mushroom-template-card",
        "primary": room.name,
        "secondary": (
            f"{{% set ns = namespace(l=[]) %}}{parts}"
            f"{{{{ ns.l | join(' · ') if ns.l else '{t['all_ok']}' }}}}"
        ),
        "icon": "mdi:stethoscope",
        "icon_color": f"{{{{ 'red' if {any_on} else 'green' }}}}",
        "entity": heating or room.climate,
        "grid_options": {"columns": 12},
    }


def _maintenance_view(c: HeatingController, ids: Ids, t: dict[str, str]) -> dict[str, Any]:
    sections = [
        _section(
            [
                _heading(t["diagnostics"], "mdi:stethoscope"),
                _m_toggle(ids.window_temp, t["window_temp"], "mdi:window-open-variant", "blue",
                          grid_options={"columns": 12}),
                *[_status_card(r, ids, t) for r in c.rooms],
            ],
            2,
        )
    ]
    if any(r.batteries or r.windows for r in c.rooms):
        sections.append(
            _section(
                [_heading(t["valves"], "mdi:valve")]
                + [_valve_card(r, t) for r in c.rooms if r.batteries or r.windows],
                2,
            )
        )
    if ids.emergency:
        sections.append(
            _section(
                [
                    _heading(t["emergency"], "mdi:fire-alert"),
                    {
                        "type": "custom:mushroom-alarm-control-panel-card",
                        "entity": ids.emergency,
                        "name": t["emergency_btn"],
                        "states": ["armed_away"],
                        "grid_options": {"columns": 12},
                    },
                ],
                2,
            )
        )
    return _view(t["maintenance"], "maintenance", "mdi:wrench", sections)


def _enhanced_charts(
    c: HeatingController, ids: Ids, t: dict[str, str], cards: set[str]
) -> dict[str, Any]:
    summary = _section(
        [
            _heading(t["summary"], "mdi:chart-box-outline"),
            {
                "type": "custom:mushroom-chips-card",
                "alignment": "start",
                "chips": _clean(
                    [
                        _chip(ids.average, "mdi:home-thermometer", "green"),
                        _chip(ids.minimum, "mdi:thermometer-low", "blue"),
                        _chip(ids.maximum, "mdi:thermometer-high", "red"),
                        _chip(ids.reference, "mdi:fire", "orange"),
                        _chip(ids.on_time, "mdi:timer-outline", "orange"),
                        _chip(ids.cycles, "mdi:sync", "purple"),
                        _chip(ids.avg_cycle, "mdi:timer-sand", "purple"),
                    ]
                ),
            },
        ],
        4,
    )
    current = _section(
        [_heading(t["current"], "mdi:thermometer")]
        + [
            _m_entity(r.sensor, r.name, _room_icon(i), "red")
            for i, r in enumerate(c.rooms)
        ]
    )
    balance = _section(
        [
            _heading(t["balance"], "mdi:scale-balance"),
            _m_entity(ids.spread, t["spread"], "mdi:arrow-expand-vertical", "blue"),
            _entities(
                t["last_reading"],
                [{"entity": r.sensor, "name": r.name, "secondary_info": "last-updated"} for r in c.rooms],
            ),
        ]
    )

    history: list[Any] = [_heading(t["history"], "mdi:chart-line")]
    if "apexcharts" in cards:
        history.append(
            {
                "type": "custom:apexcharts-card",
                "header": {
                    "show": True,
                    "title": t["rooms_temp_24h"],
                    "show_states": True,
                    "colorize_states": True,
                },
                "graph_span": "24h",
                "span": {"end": "minute"},
                "chart_type": "line",
                "apex_config": {"chart": {"height": 260}, "stroke": {"curve": "smooth"}},
                "series": [
                    {
                        "entity": r.climate,
                        "name": r.name,
                        "attribute": "current_temperature",
                        "stroke_width": 2,
                    }
                    for r in c.rooms
                ],
            }
        )
    history += _common_charts(c, ids, t)
    sensors = _room_sensors(c, t, ids)
    if "mini_graph" in cards:
        history.append(
            {
                "type": "custom:mini-graph-card",
                "name": t["sensors_24h"],
                "hours_to_show": 24,
                "points_per_hour": 4,
                "line_width": 2,
                "smoothing": True,
                "show": {"legend": True, "fill": False, "points": False},
                "entities": sensors,
            }
        )
    else:
        history.append(_history(t["sensors_24h"], sensors, 24))
    history += _weekly_charts(c, ids, t)

    return _view(
        t["charts"], "charts", "mdi:chart-line",
        [summary, current, balance, _section(history, 2)],
    )
