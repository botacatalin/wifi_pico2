# Nodes Wi-Fi Provisioning Server

MicroPython firmware for provisioning a Raspberry Pi Pico 2 W onto a 2.4 GHz
Wi-Fi network, serving a local dashboard, and exchanging command/reply messages
with other enabled boards on the LAN.

## Project status

The core firmware is implemented and covered by a dependency-free host-side
test suite. The current version includes:

- complete first-boot provisioning with credential validation and persistence;
- captive-portal recovery and delayed setup-AP shutdown after success;
- a responsive five-page connected-device dashboard with health, messaging,
  network controls, and a low-distraction interface designed for long-running
  monitoring on desktop and phone screens;
- automatic discovery of modular Device Features from `plugins/`, including
  onboard LED and processor-temperature controls;
- optional, persistent UDP peer discovery, ping, and short message/reply flows;
- bounded HTTP requests, UDP packets, message history, retries, and timeouts;
- CYW43 power saving disabled by default for more reliable always-on HTTP and
  multi-board UDP communication.

The host suite currently contains 67 tests covering helpers, rendering,
provisioning transitions, AP shutdown scheduling, feature and messaging lifecycles, peer
discovery, retries, reply matching, deduplication, and Wi-Fi configuration.
Physical Pico 2 W verification is still required for radio behavior, especially
after changing MicroPython versions, routers, or Wi-Fi timing.

## How it works

On first boot, the board:

1. Creates the open `Nodes-Setup` Wi-Fi network.
2. Serves setup at `http://192.168.4.1/`.
3. Scans nearby 2.4 GHz networks.
4. Tests the selected SSID and password.
5. Saves credentials only after receiving a LAN IP address.
6. Restores the setup AP after the shared radio changes channel.
7. Keeps `Nodes-Setup` active and captive-portal routes in the completion flow
   until the Setup Complete page reaches the browser.
8. Shows Connected successfully, the assigned LAN address, and a 10-second
   countdown on the Setup Complete page.
9. Disables `Nodes-Setup` when the countdown reaches zero. The phone or computer
   can then reconnect to its previously saved network.
   If the result page is not reached, the AP remains available for up to two
   minutes so the browser can reconnect after the radio channel changes.
   The success page displays the remaining setup-AP time beneath the dashboard
   link. The board owns the shutdown timer; JavaScript only displays it.

The connecting page uses bounded status requests and continues retrying
automatically if browser access is interrupted. As soon as the restored setup
AP reports success, the browser navigates directly to Setup Complete.
Receiving the connecting page also starts the radio work immediately; the
configured start delay remains only as a fallback for clients that do not
follow the redirect.

The board must join the selected network before it can know whether the
credentials succeeded. This can briefly disconnect the browser because AP and
station mode share one radio. When the phone reconnects to the restored setup
AP, `/` and captive-portal probes return Setup Complete. The ten-second AP
shutdown timer starts only after that page has been delivered.

Restoring `Nodes-Setup` after a successful connection is required for reliable
result delivery. The browser is still using `192.168.4.1`, and it does not know
the newly assigned LAN address yet. Without the restored setup AP, the Pico
would know that provisioning succeeded but could not send the LAN address or
Setup Complete page back to that browser.

The successful browser flow is therefore:

1. The Pico joins the selected network and confirms its LAN IP.
2. The Pico saves the credentials and restores `Nodes-Setup` on the radio's new
   channel.
3. The browser reconnects to `Nodes-Setup`; automatic polling or a captive
   portal probe reaches the Pico again.
4. The browser goes directly to Setup Complete. No manual result screen or
   **Check connection** action is required.
5. Setup Complete shows the connected network, LAN address, dashboard link, and
   10-second countdown.
6. At zero, the Pico disables `Nodes-Setup`. The phone or computer may reconnect
   to its previously saved network automatically, or the user can select it.

On later boots, saved credentials are tried first. If the connection fails, the
board returns to setup mode.

The connected dashboard has five pages:

- **Overview:** system status.
  Processor temperatures at or above 85°C are marked critical.
- **Nodes:** communication-plugin controls, local board/group identity,
  discovered boards with IP addresses, and command/reply messages.
- **Network:** saved-network controls.
- **Device Features:** automatically discovered, drop-in board controls.
- **About:** project summary, external README, `nodes.ro@proton.me` contact, and
  GNU GPL v2 license information.

The dashboard uses a neutral surface, restrained green status accents, compact
device/network badges, and clear card hierarchy so it remains comfortable to
scan over long sessions. On narrow screens the sidebar becomes a compact
five-tab navigation bar; metrics and discovered-device cards collapse to a
single column. Critical temperature and destructive network actions retain
distinct warning colors. The interface uses no external fonts, scripts, or
image assets, so it remains self-contained on the Pico filesystem.

**Forget network** removes the saved credentials without interrupting the
current session. Setup mode returns after restart.

## Device Features

See [`README_ADD_PLUGINS.md`](README_ADD_PLUGINS.md) for the concise feature
interface and copy-and-paste installation guide.

At startup, `FeatureManager` scans each subfolder in `plugins/`. A valid feature
is listed automatically on the **Device Features** page; no central import,
route, or dashboard template needs to be edited. The bundled `onboard_led` feature uses
MicroPython's `Pin("LED", Pin.OUT)` mapping and provides a button that toggles
the Pico 2 W's built-in LED. The bundled `processor_temperature` feature reads
the RP2350 internal temperature sensor independently of the Overview page.

There is no configured feature count limit. The practical limit is the Pico's
available flash and RAM, so features should keep imports, state, and rendered
HTML compact.

To install a feature, copy its complete folder into `plugins/` and restart the
board. Folder names use lowercase letters, numbers, and underscores and must
start with a letter. Each folder contains an `__init__.py` and a `feature.py`.
Its class must inherit the versioned
`DeviceFeature` interface and its module must expose `create_feature()`.
`feature_id` may contain lowercase letters, numbers, and hyphens, and must be
unique:

```python
from plugins import DeviceFeature


class ExampleFeature(DeviceFeature):
    feature_id = "example"
    name = "Example"
    description = "What this feature controls."
    # sensor, actuator, or integration
    feature_type = "sensor"
    # True when the user must connect a sensor, relay, or other component.
    requires_external_hardware = True
    # Public values advertised during discovery and returned by read().
    exposed_fields = ("temperature_c", "connected")

    def render(self, message=""):
        return "<header>...</header>"

    def read(self):
        return {"temperature_c": 23.4, "connected": True}

    # Actuators override this. The inherited implementation rejects actions.
    def handle_action(self, action, form):
        return "Action completed."


def create_feature():
    return ExampleFeature()
```

Forms post to `/features/<feature_id>/<action>`. The interface supplies no-op
`update()` and `close()` lifecycle methods that features may override. A feature
owns its hardware imports, state, templates, and actions and should escape every
dynamic value it places in HTML. Features are executable firmware code, so
install them only from sources you trust.

The Device Features page marks every feature as either **Built-in hardware** or
**External hardware required**. Omitting `requires_external_hardware` defaults
to built-in for compatibility, but new features should declare it explicitly.
The onboard LED and processor-temperature features use hardware built into every
Pico 2 W and are marked accordingly. External sensor features should set the
flag to `True` and document their wiring and power requirements in their own
folder.

Features are also classified as **Sensor**, **Actuator**, or **Integration**.
An actuator such as the LED changes hardware through `handle_action()` and
shares its current state through `read()`. A sensor reads its attached hardware
and returns one or more named values. `exposed_fields` declares those names and
`read()` returns a compact dictionary with exactly the same keys. Field names
use lowercase letters, numbers, and underscores. Values may be strings,
numbers, booleans, or `None`. The manager validates and normalizes this output
centrally before it is shared, and the communication layer enforces the
configured payload limit.

Every compatible feature implements `read()`. Peer discovery automatically
advertises its feature ID and exposed field names, so Nodes shows what
each remote board provides and uses those IDs as query suggestions. Select a
discovered board and feature, then choose **Read value**. The receiving board
resolves the requested `feature_id` locally and returns its current value.
Missing, failed, mismatched, and oversized outputs produce bounded error
replies without exposing feature internals.

## Messaging

The optional communication plugin lets connected Pico 2 W boards discover one
another and exchange short command/reply messages on the local network. It is
disabled by default and runs only in device mode after Wi-Fi has a usable LAN
address.

### Enable messaging

Messaging enablement is controlled from the Nodes page. Select **Enable** to
start discovery and command handling, or **Disable** to close the UDP socket and
hide the board from its peers. The choice is saved in
`communication_plugin.json` and restored after restart. The plugin starts only
after the board receives a LAN address.

When enabled, the plugin card identifies the local board and group below its
status text, for example:

```text
Board ID nodes-75833497    Group name nodes-local
```

The node suffix is derived from the board's hardware ID unless
`COMMUNICATION_NODE_NAME` is configured. `COMMUNICATION_GROUP_NAME` is a
discovery group, not a password. Boards only see and communicate with enabled
boards using the same group name and UDP port.

### Discover boards

Each enabled board calculates the subnet-directed broadcast address from its
station IP and netmask, then broadcasts a small UDP discovery packet
periodically. This avoids CYW43 routing failures that can occur with the global
`255.255.255.255` address. A board that receives the packet replies directly,
and both boards add one another to their available-device lists. Inactive
boards expire from the list after the configured timeout. A temporary broadcast
failure is retried at the next normal interval instead of on every server-loop
iteration.

Discovery updates automatically. Discovered-device cards and the target
selector show both node name and LAN IP address. **Refresh devices** broadcasts
immediately and reloads the current server-rendered list without showing a
success notice. For discovery to work, the boards must:

- Be connected to the same local Wi-Fi network.
- Use the same `COMMUNICATION_GROUP_NAME` and `COMMUNICATION_PORT`.
- Have the communication plugin enabled.
- Be on a network that permits UDP broadcast and client-to-client traffic.

Guest-network or access-point client isolation can prevent discovery even when
both boards are connected successfully.

### Send messages and receive replies

The Discover section places Refresh devices below the Enabled status.
Discovered boards appear as selectable cards showing node name and IP
address. The separate Conversation section appears below the device list.
Select a board, type into the composer below the chat window, and press
**Send**. The chat keeps the eight most recent sent and received messages in
RAM and timestamps them using the viewing browser's local clock. Select
**Clear conversation** to remove that local history without
affecting discovered devices or the other board. History is also cleared when
the plugin stops or the board restarts. While the Nodes page is open, it
checks for conversation changes once per second and reloads automatically when
a message arrives, so received messages do not require a manual refresh.

Select **Ping** beside Send to test the selected board without entering a
message. The receiver automatically returns `Ping ACK from <board-id>.` A
`message` receiver currently echoes the original payload in its reply; this is
the feature point for future message-processing behavior. Successful message
echoes and Ping ACKs appear inside the chat window, replacing its “No messages
yet” state. On the sender, the request uses the sent-message color and the
reply uses the received-message color. The receiving board records the inverse:
the incoming request followed by its automatic Ping ACK or echoed-message
reply. Locally sent bubbles are labeled **This Device**; received bubbles show
the remote board ID. Retries reuse cached replies and do not duplicate chat
entries. Only failures are shown as page notices.

Features can also be queried from this page. The requester sends the
selected feature ID, and the current remote result appears in the conversation,
for example `Onboard LED: state=on` or
`Processor Temperature: temperature_c=42.0`.

Application packets use the same `message_type` for a request and its response:
`message` for text delivery, `ping` for availability checks, and `feature_read`
for an exact read-only feature query whose payload is the feature ID. `kind`
distinguishes `request`, successful `reply`, and rejected `error` packets. A
separate `command` field and boolean `reply` field are not used.

Message request:

```json
{
  "message_type": "message",
  "kind": "request",
  "request_id": "nodes-75833497-1",
  "node_name": "nodes-75833497",
  "group_name": "nodes-local",
  "payload": "Hello"
}
```

Successful response:

```json
{
  "message_type": "message",
  "kind": "reply",
  "request_id": "nodes-75833497-1",
  "node_name": "nodes-91ab2041",
  "group_name": "nodes-local",
  "payload": "Hello"
}
```

A rejected request returns the same structure with `kind: "error"` and an
explanation in `payload`. This means the target received the request but could
not accept it. It differs from a timeout, where no matching response arrived.
Ping uses the same fields with `message_type: "ping"`. Feature reads use
`message_type: "feature_read"` and return the display value in `payload`.

Matching the message type, request ID, sender name, and source IP address
prevents an unrelated response from completing the request.

Commands retry with the same request ID during the bounded reply window. The
receiver remembers a small number of recent IDs, so a retried command returns
its previous reply without executing twice. Successful requests and replies are
shown in the conversation, while failures appear as Messages-page notices.
Request IDs include a per-plugin-session value so disabling, re-enabling, or
restarting a sender does not collide with an ID still cached by another board.
Deduplication keys also include the message type.

Selecting a peer for a command gives it a fresh 30-second liveness window. A
temporary ping or message timeout therefore does not immediately remove a
device whose previous discovery record was already near expiry. UDP send errors
are retried inside the three-second reply window; normal discovery ultimately
decides whether the peer remains available.

### Runtime and security

Messaging shares the existing single-core application loop. The discovery
socket is non-blocking and each update handles a bounded number of packets so
normal HTTP serving can continue. Sending a command waits for its reply for up
to `COMMUNICATION_REPLY_TIMEOUT_MS`, during which the synchronous HTTP server
cannot serve another request.

Discovery and message packets are plain-text UDP with no authentication or
encryption. Use messaging only on a trusted LAN; a matching group name provides
separation between board groups but is not a security boundary.

## Installation

1. Install current Pico 2 W-compatible MicroPython firmware.
2. Copy all project files to the board, preserving the `network_setup/`,
   `shared_web/`, `device_dashboard/`, `peer_communication/`, and `plugins/`
   directories.
3. Power-cycle the board.

MicroPython runs `main.py` automatically. Do not copy or commit
`wifi_credentials.json`; it contains the Wi-Fi password in plain text.
The dashboard creates `communication_plugin.json` when its communication toggle
is changed; this runtime state file does not need to be copied between boards.

## First-time setup

1. Connect a phone or computer to `Nodes-Setup`.
2. Open `http://192.168.4.1/` if setup does not open automatically.
3. Select a 2.4 GHz network, enter its password, and press **Connect**.
4. Keep the page open while the setup network briefly changes channel.
5. Wait for Setup Complete and note the displayed LAN address.
6. Let the 10-second countdown reach zero so `Nodes-Setup` is disabled.
7. Allow the phone or computer to reconnect automatically, or select the normal
   LAN manually, then open the displayed address with `http://`.

The dashboard IP is assigned by the router through DHCP and may change.

## Routes

### Setup mode

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | Wi-Fi setup page |
| `GET` | `/rescan` | Scan again |
| `POST` | `/connect` | Submit credentials |
| `GET` | `/connection-result` | Show success or failure |
| `GET` | `/connection-status` | Poll connection state |
| `GET` | `/health` | Return `OK` |
| `GET` | `/setup.css` | Provisioning stylesheet |
| `GET` | `/style.css` | Error-page and dashboard stylesheet |

Common captive-portal probe routes also display setup.

### Device mode

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/` | System overview |
| `GET` | `/nodes` | Device discovery and command/reply messaging |
| `GET` | `/network` | Saved-network information |
| `GET` | `/features` | List installed Device Features |
| `GET` | `/features/<feature-id>` | Display one feature |
| `POST` | `/features/<feature-id>/<action>` | Run an feature action |
| `GET` | `/about` | Project, contact, documentation, and license information |
| `POST` | `/communication/toggle` | Enable or disable messaging |
| `POST` | `/communication/refresh` | Broadcast device discovery now |
| `POST` | `/communication/clear` | Clear this board's in-memory conversation history |
| `POST` | `/communication/command` | Send a command to a discovered device |
| `POST` | `/forget-wifi` | Delete saved credentials |
| `GET` | `/connect` | Provisioning success page |
| `GET` | `/connection-result` | Completed connection result |
| `GET` | `/connection-status` | Completed connection state |
| `GET` | `/README.md` | This README |
| `GET` | `/health` | Return `OK` |
| `GET` | `/setup.css` | Provisioning-success stylesheet |
| `GET` | `/style.css` | Dashboard stylesheet |

Unknown routes return `404 Not Found`.

## Configuration

Settings are in `config.py`. Current identity and setup defaults are:

```python
DEVICE_NAME = "Nodes"
AP_SSID = "Nodes-Setup"
AP_IP = "192.168.4.1"
HTTP_PORT = 80
STATIC_CACHE_SECONDS = 3600
CONNECT_TIMEOUT_MS = 12000
WIFI_POWER_MANAGEMENT = 0xA11140
CONNECTION_PAGE_SETTLE_MS = 250
CONNECTION_POLL_INTERVAL_MS = 1000
CONNECTION_REQUEST_TIMEOUT_MS = 16000
AP_SHUTDOWN_DELAY_MS = 10000
AP_RESULT_TIMEOUT_MS = 120000
PROCESSOR_TEMPERATURE_CRITICAL_C = 85
DASHBOARD_BACKGROUND_COLOR = "#ECFAEF"
DASHBOARD_ACCENT_COLOR = "#4F772D"
COMMUNICATION_NODE_NAME = ""
COMMUNICATION_ENABLED_DEFAULT = False
COMMUNICATION_STATE_FILE = "communication_plugin.json"
COMMUNICATION_STATE_TEMP_FILE = "communication_plugin.tmp"
COMMUNICATION_GROUP_NAME = "nodes-local"
COMMUNICATION_PORT = 4242
COMMUNICATION_DISCOVERY_INTERVAL_MS = 5000
COMMUNICATION_PEER_EXPIRY_MS = 30000
COMMUNICATION_REPLY_TIMEOUT_MS = 3000
COMMUNICATION_RETRY_INTERVAL_MS = 500
COMMUNICATION_MAX_PACKET_BYTES = 512
COMMUNICATION_MAX_PAYLOAD_BYTES = 160
```

The setup AP is intentionally open. `DEVICE_NAME` is used in pages, the startup
banner, and log prefixes.

## Project layout

```text
main.py                    Startup and synchronous server loop
app.py                     Application state and route dispatch
config.py                  Identity, networking, limits, and routes
app_logging.py             Application-configured logging helper
shared_web/
  http.py                  Bounded HTTP parsing, responses, and server socket
  forms.py                 URL and form decoding
  html.py                  HTML escaping
  template.py              Lightweight component template renderer
network_setup/
  credentials.py           Credential persistence
  pages.py                 Provisioning page rendering
  wifi.py                  AP, scan, and station management
  networks.py              Network sorting and signal presentation
  style.css                Provisioning-only responsive styles
  templates/               Setup-only templates
device_dashboard/
  metrics.py               Uptime and processor temperature
  pages.py                 Dashboard and error rendering
  style.css                Responsive dashboard visual system and states
  templates/               Overview, Nodes, Device Features, Network, and components
peer_communication/
  peer.py                   Bounded UDP discovery and command/reply protocol
  plugin.py                 Enable/disable lifecycle and state persistence
plugins/
  interface.py              Versioned feature contract and lifecycle defaults
  manager.py                Feature discovery and shared lifecycle
  onboard_led/              Self-contained onboard LED feature and template
  processor_temperature/    Self-contained processor-temperature feature
```

`network_setup/` is the reusable provisioning component, `shared_web/` provides
dependency-free HTTP and rendering primitives, and `device_dashboard/` owns
the connected product interface. `peer_communication/` owns optional local
device discovery and messaging. `app.py` injects configuration and coordinates
the transition between provisioning and dashboard modes. `plugins/` contains
self-contained Device Features loaded by convention. Neither UI package
imports the application's root `config.py` or the other UI package; both may
use the dependency-free helpers in `shared_web/`.

`WiFi`, `CredentialStore`, the page renderers, `read_request()`, and
`create_server()` accept configuration through constructor or function
arguments. This allows the packages to be copied to another MicroPython project
without recreating this application's global configuration module.

Templates support values (`{{ VALUE }}`), includes (`{{> component.html}}`),
and conditional includes (`{{? VALUE > component.html}}`).

## Credentials and security

- Credentials are saved only after a successful connection.
- Failed attempts do not replace working credentials.
- Updates use `wifi_credentials.tmp` before replacing
  `wifi_credentials.json`.
- Credentials are stored as plain-text JSON.
- Setup and dashboard traffic use HTTP without authentication or TLS.
- Keep the device on a trusted LAN and do not expose it to the internet.

## Troubleshooting

### The connecting page stops updating

The Pico 2 W uses one radio for setup AP and station modes. Joining the router
can briefly disconnect `Nodes-Setup`. Reconnect to `Nodes-Setup`, reopen
`http://192.168.4.1/` if the page does not resume automatically. A confirmed
connection returns Setup Complete; its countdown starts only after that page
is delivered.

### The dashboard does not open

- Reconnect the browser to the same LAN as the board.
- Use the LAN IP printed in the serial log.
- Use `http://`, not `https://`.
- Test `http://<device-ip>/health`; it should return `OK`.
- Avoid guest networks that isolate devices from each other.

### Wi-Fi connection fails

- Use a 2.4 GHz network; Pico 2 W does not support 5 GHz Wi-Fi.
- The default configuration disables CYW43 power saving because this board is
  an always-on HTTP and UDP server. Set `WIFI_POWER_MANAGEMENT = None` to keep
  the firmware default if lower power use matters more than responsiveness.
- Check the password and router security mode.
- Move the board closer to the access point.
- Power-cycle the board to test credentials from a clean radio state.

### Boards do not appear in Nodes

- Enable the communication plugin on every board.
- Confirm that all boards show the same group name and use the same UDP port.
- Confirm that every board is connected to the same local network.
- Select **Refresh devices**, then reload Nodes if necessary.
- If refresh reports that discovery is unavailable, confirm the station still
  has a valid LAN IP and netmask.
- Disable guest-network or wireless-client isolation on the router.
- Remember that inactive peers expire from the list after 30 seconds by
  default.

### A message times out

- Confirm the target still appears with its current IP address.
- Check that both boards run the same protocol version; the current format uses
  `message_type`, `kind`, `request_id`, `node_name`, `group_name`, and `payload`.
- Keep payloads within `COMMUNICATION_MAX_PAYLOAD_BYTES`.
- Check for packet loss or client isolation on the Wi-Fi network.

## Limitations

- One HTTP request is processed at a time.
- Sending a peer command can occupy that request loop for up to the configured
  three-second reply timeout.
- Dashboard addresses come from DHCP.
- mDNS, static LAN IPs, OTA updates, TLS, and dashboard authentication are not
  implemented.
- Processor temperature is an approximate internal reading, not ambient
  temperature.
