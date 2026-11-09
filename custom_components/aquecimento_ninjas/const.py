"""Constants for Aquecimento Ninjas."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "aquecimento_ninjas"
VERSION = "1.0.1"
DOCS_URL = "https://github.com/noesisaoliveira/aquecimento_ninjas"

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.CLIMATE,
]

BETTER_THERMOSTAT_DOMAIN = "better_thermostat"
MAX_VALVES = 5

CONF_BOILER_MODE = "boiler_mode"
CONF_BOILER_CLIMATE = "boiler_climate"
CONF_BOILER_SWITCH = "boiler_switch"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_MIN_CYCLE = "min_cycle"

CONF_ROOMS = "rooms"
CONF_ROOM_ID = "id"
CONF_ROOM_NAME = "room_name"
CONF_ROOM_CLIMATE = "climate"
CONF_ROOM_VALVES = "valves"
CONF_ROOM_SENSOR = "sensor"
CONF_ROOM_BATTERIES = "batteries"
CONF_ROOM_WINDOWS = "windows"
CONF_ADD_ANOTHER = "add_another"

CONF_PERSONS = "persons"
CONF_AWAY_DELAY = "away_delay"
CONF_NOTIFY = "notify_service"
CONF_NOTIFY_WINDOWS = "notify_windows"
CONF_NOTIFY_BATTERY = "notify_battery"
CONF_BATTERY_THRESHOLD = "battery_threshold"

CONF_CREATE_DASHBOARD = "create_dashboard"
CONF_DASHBOARD_TITLE = "dashboard_title"
CONF_REGENERATE_DASHBOARD = "regenerate_dashboard"

BOILER_EXISTING = "existing"
BOILER_CREATE = "create"

MODE_ECO = "eco"
MODE_COMFORT = "comfort"

DEFAULT_NAME = "Aquecimento"
DEFAULT_COMFORT = 20.0
DEFAULT_ECO = 17.0
DEFAULT_AWAY = 15.0
DEFAULT_COLD_TOLERANCE = 0.3
DEFAULT_HOT_TOLERANCE = 0.0
DEFAULT_MIN_CYCLE = 5
DEFAULT_AWAY_DELAY = 30
DEFAULT_BATTERY_THRESHOLD = 20
DEFAULT_BOILER_TARGET = 20.0

MIN_TEMP = 5.0
MAX_TEMP = 30.0
TEMP_STEP = 0.5

DASHBOARD_URL = "aquecimento-ninjas"
DASHBOARD_ID = "aquecimento_ninjas"

APPLY_INTERVAL_MINUTES = 30
SUPPRESS_SECONDS = 10
MASTER_SETTLE_SECONDS = 5

SIGNAL_TEMPERATURES = f"{DOMAIN}_temperatures"
SIGNAL_STATS = f"{DOMAIN}_stats"
