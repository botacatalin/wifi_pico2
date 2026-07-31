# config.py

# =========================================================
# Device identity
# =========================================================

DEVICE_NAME = "Nodes"

# =========================================================
# Setup access point
# =========================================================

AP_SSID = "Nodes-Setup"
AP_OPEN = True

# Keep the RP2 AP default because its DHCP server uses the 192.168.4.x subnet.
AP_IP = "192.168.4.1"
AP_NETMASK = "255.255.255.0"
AP_GATEWAY = AP_IP
AP_DNS = AP_IP

# =========================================================
# Persistent Wi-Fi configuration
# =========================================================

WIFI_CREDENTIALS_FILE = "wifi_credentials.json"
WIFI_CREDENTIALS_TEMP_FILE = "wifi_credentials.tmp"

# =========================================================
# HTTP server
# =========================================================

SERVER_BIND_IP = "0.0.0.0"
HTTP_PORT = 80

MAX_HEADER_BYTES = 4096
MAX_BODY_BYTES = 2048

SOCKET_TIMEOUT_SECONDS = 5
SERVER_ACCEPT_TIMEOUT_SECONDS = 1
STATIC_CACHE_SECONDS = 3600

# =========================================================
# Optional communication plugin
# =========================================================

# Leave this empty to derive a short, unique name from the board ID.
COMMUNICATION_NODE_NAME = ""
COMMUNICATION_ENABLED_DEFAULT = False
COMMUNICATION_STATE_FILE = "communication_plugin.json"
COMMUNICATION_STATE_TEMP_FILE = "communication_plugin.tmp"
COMMUNICATION_PORT = 4242
COMMUNICATION_DISCOVERY_INTERVAL_MS = 5000
COMMUNICATION_PEER_EXPIRY_MS = 30000
COMMUNICATION_REPLY_TIMEOUT_MS = 3000
COMMUNICATION_RETRY_INTERVAL_MS = 500
COMMUNICATION_MAX_PACKET_BYTES = 512
COMMUNICATION_MAX_PAYLOAD_BYTES = 160
# Only boards with the same group name discover and communicate with each other.
# The group name is sent in plain text and is not a password.
COMMUNICATION_GROUP_NAME = "nodes-local"

# =========================================================
# Wi-Fi timing
# =========================================================

CONNECT_TIMEOUT_MS = 12000
CONNECT_STATUS_GRACE_MS = 1500
CONNECTION_START_DELAY_MS = 1500
CONNECTION_PAGE_SETTLE_MS = 250
CONNECTION_POLL_INTERVAL_MS = 1000
# Keep one status request alive for the complete synchronous connection window.
# This avoids filling the small socket backlog with abandoned polling requests.
CONNECTION_REQUEST_TIMEOUT_MS = 16000
AP_SHUTDOWN_DELAY_MS = 10000
AP_RESULT_TIMEOUT_MS = 120000

# Dashboard thresholds
PROCESSOR_TEMPERATURE_CRITICAL_C = 85

# Dashboard theme
DASHBOARD_BACKGROUND_COLOR = "#ECFAEF"
DASHBOARD_ACCENT_COLOR = "#4F772D"

# =========================================================
# Routes
# =========================================================

ROUTE_HOME = "/"
ROUTE_ABOUT = "/about"
ROUTE_CONNECT = "/connect"
ROUTE_CONNECTION_RESULT = "/connection-result"
ROUTE_CONNECTION_STATUS = "/connection-status"
ROUTE_FORGET_WIFI = "/forget-wifi"
ROUTE_RESCAN = "/rescan"
ROUTE_HEALTH = "/health"
ROUTE_MESSAGES = "/messages"
ROUTE_NETWORK = "/network"
ROUTE_STYLE = "/style.css"
ROUTE_SETUP_STYLE = "/setup.css"
ROUTE_README = "/README.md"
ROUTE_COMMUNICATION_TOGGLE = "/communication/toggle"
ROUTE_COMMUNICATION_REFRESH = "/communication/refresh"
ROUTE_CLEAR_CONVERSATION = "/communication/clear"
ROUTE_SEND_COMMAND = "/communication/command"

CAPTIVE_PORTAL_ROUTES = (
    "/",
    "/generate_204",
    "/gen_204",
    "/hotspot-detect.html",
    "/ncsi.txt",
    "/connecttest.txt",
    "/redirect",
)
