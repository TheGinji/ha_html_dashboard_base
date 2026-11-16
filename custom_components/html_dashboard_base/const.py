"""Constanten voor Dashboard Base."""

DOMAIN = "html_dashboard_base"

CONF_TITLE = "title"
CONF_ENTITIES = "entities"
CONF_HTML = "html"
CONF_HTML_NAME = "html_name"
CONF_REMOVE_HTML = "remove_html"
CONF_DASHBOARD_ID = "dashboard_id"
CONF_PANEL_URL = "panel_url"

MAX_DASHBOARDS = 5

# Waarden van de eerste (enige) instelling uit versie 0.1.x. Die blijven behouden,
# zodat het bestand en het adres van het paneel niet veranderen.
LEGACY_DASHBOARD_ID = "dashboard"
LEGACY_PANEL_URL = "html-dashboard-base"

DEFAULT_TITLE = "Dashboard"
DEFAULT_ICON = "mdi:view-dashboard-outline"

PANEL_ELEMENT = "html-dashboard-base-panel"
STATIC_URL = "/html_dashboard_base_static"

DATA_DIR = "html_dashboard_base"
MAX_HTML_BYTES = 2_000_000

# Gedeelde voorkeuren (sharedPrefs): één klein JSON-object per dashboard, in .storage van Home Assistant.
PREFS_STORE_KEY = f"{DOMAIN}.prefs"
PREFS_STORE_VERSION = 1
MAX_PREFS_CHARS = 8000
DATA_PREFS = f"{DOMAIN}_prefs"

ALLOWED_DOMAINS = frozenset(
    {
        "button", "climate", "cover", "fan", "humidifier", "input_boolean",
        "input_button", "input_number", "input_select", "light",
        "media_player", "number", "scene", "script", "select", "switch",
        "vacuum", "water_heater",
    }
)
BLOCKED_TARGET_KEYS = frozenset({"device_id", "area_id", "floor_id", "label_id"})
