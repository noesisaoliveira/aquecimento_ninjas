"""Constants for Aquecimento Ninjas."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "aquecimento_ninjas"
VERSION = "1.3.1"
DOCS_URL = "https://github.com/noesisaoliveira/aquecimento_ninjas"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
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
CONF_NOTIFY_SENSOR_FAILURE = "notify_sensor_failure"
CONF_NOTIFY_NOT_HEATING = "notify_not_heating"
CONF_BATTERY_THRESHOLD = "battery_threshold"
CONF_ENABLE_MODE_APPLY = "enable_mode_apply"
CONF_ENABLE_SLIDER_SYNC = "enable_slider_sync"
CONF_ENABLE_PRESENCE = "enable_presence"
CONF_ENABLE_AWAY_TARGET = "enable_away_target"
CONF_ENABLE_MASTER = "enable_master"
CONF_ENABLE_WINDOWS = "enable_windows"
CONF_APPLY_INTERVAL = "apply_interval"
CONF_MASTER_SETTLE_SECONDS = "master_settle_seconds"
CONF_MAX_RUNTIME_HOURS = "max_runtime_hours"
CONF_NOTIFY_RUNTIME_WARNING = "notify_runtime_warning"
CONF_VERIFY_SECONDS = "verify_seconds"
CONF_VERIFY_RETRIES = "verify_retries"
CONF_BATTERY_CHECK_HOUR = "battery_check_hour"
CONF_BATTERY_CHECK_MINUTE = "battery_check_minute"
CONF_WINDOW_CONTACT_SECONDS = "window_contact_seconds"
CONF_WINDOW_DROP_DEGREES = "window_drop_degrees"
CONF_WINDOW_DROP_MINUTES = "window_drop_minutes"
CONF_WINDOW_MIN_PAUSE_MINUTES = "window_min_pause_minutes"
CONF_WINDOW_MAX_PAUSE_MINUTES = "window_max_pause_minutes"

CONF_CREATE_DASHBOARD = "create_dashboard"
CONF_DASHBOARD_TITLE = "dashboard_title"
CONF_DASHBOARD_STYLE = "dashboard_style"
CONF_REGENERATE_DASHBOARD = "regenerate_dashboard"

STYLE_AUTO = "auto"
STYLE_ENHANCED = "enhanced"
STYLE_STANDARD = "standard"

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
DEFAULT_BATTERY_CHECK_HOUR = 9
DEFAULT_BATTERY_CHECK_MINUTE = 0
DEFAULT_MAX_RUNTIME_HOURS = 0.0
DEFAULT_BOILER_TARGET = 20.0
DEFAULT_BOOST_HOURS = 1.0
DEFAULT_BOOST_TEMPERATURE = 23.0

MIN_TEMP = 5.0
MAX_TEMP = 30.0
TEMP_STEP = 0.5

DASHBOARD_URL = "aquecimento-ninjas"
DASHBOARD_ID = "aquecimento_ninjas"

APPLY_INTERVAL_MINUTES = 30
SUPPRESS_SECONDS = 10
MASTER_SETTLE_SECONDS = 5
RUNTIME_WARNING_MINUTES = 10

# Verified commands: check the thermostat accepted it, resend otherwise.
VERIFY_SECONDS = 90
MAX_RETRIES = 3

# Windows: contact debounce, and open window detected from a fast temperature drop.
WINDOW_CONTACT_SECONDS = 10
WINDOW_DROP_DEGREES = 1.0
WINDOW_DROP_MINUTES = 5
WINDOW_MIN_PAUSE_MINUTES = 15
WINDOW_MAX_PAUSE_MINUTES = 60

# Diagnostics
SENSOR_STALE_HOURS = 3
NOT_HEATING_DELTA = 1.0
NOT_HEATING_HOURS = 2

SIGNAL_TEMPERATURES = f"{DOMAIN}_temperatures"
SIGNAL_STATS = f"{DOMAIN}_stats"
SIGNAL_BOOST = f"{DOMAIN}_boost"
SIGNAL_DIAGNOSTICS = f"{DOMAIN}_diagnostics"
