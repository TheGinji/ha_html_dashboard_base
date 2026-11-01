"""Constanten voor Dashboard Base."""

DOMAIN = "html_dashboard_base"

CONF_TITLE = "title"
CONF_ENTITIES = "entities"
CONF_HTML = "html"

DEFAULT_TITLE = "Dashboard"
DEFAULT_ICON = "mdi:view-dashboard-outline"

PANEL_URL = "html-dashboard-base"
PANEL_ELEMENT = "html-dashboard-base-panel"
STATIC_URL = "/html_dashboard_base_static"

DATA_DIR = "html_dashboard_base"
HTML_FILE = "dashboard.html"
MAX_HTML_BYTES = 2_000_000

ALLOWED_DOMAINS = frozenset(
    {
        "button", "climate", "cover", "fan", "humidifier", "input_boolean",
        "input_button", "input_number", "input_select", "light",
        "media_player", "number", "scene", "script", "select", "switch",
        "vacuum", "water_heater",
    }
)
BLOCKED_TARGET_KEYS = frozenset({"device_id", "area_id", "floor_id", "label_id"})
