# Nodes Wi-Fi Provisioning Server

MicroPython firmware for provisioning a Raspberry Pi Pico 2 W onto a 2.4 GHz
Wi-Fi network and serving a small dashboard on the local network.

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

The connected dashboard has two pages:

- **Overview:** project resources.
- **Network:** server uptime, approximate RP2350 temperature, and saved-network
  controls. Temperatures at or above 85°C are marked critical.

**Forget network** removes the saved credentials without interrupting the
current session. Setup mode returns after restart.

## Installation

1. Install current Pico 2 W-compatible MicroPython firmware.
2. Copy all project files to the board, preserving the `network_setup/`,
   `shared_web/`, and `device_dashboard/` directories.
3. Power-cycle the board.

MicroPython runs `main.py` automatically. Do not copy or commit
`wifi_credentials.json`; it contains the Wi-Fi password in plain text.

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
| `GET` | `/` | Overview dashboard |
| `GET` | `/network` | System and saved-network information |
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
CONNECTION_PAGE_SETTLE_MS = 250
CONNECTION_POLL_INTERVAL_MS = 1000
CONNECTION_REQUEST_TIMEOUT_MS = 16000
AP_SHUTDOWN_DELAY_MS = 10000
AP_RESULT_TIMEOUT_MS = 120000
PROCESSOR_TEMPERATURE_CRITICAL_C = 85
DASHBOARD_BACKGROUND_COLOR = "#ECFAEF"
DASHBOARD_ACCENT_COLOR = "#4F772D"
```

The setup AP is intentionally open. `DEVICE_NAME` is used in pages, the startup
banner, and log prefixes.

## Project layout

```text
main.py                    Startup and synchronous server loop
app.py                     Application state and route dispatch
config.py                  Identity, networking, limits, and routes
utils.py                   Application-configured logging compatibility helper
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
  style.css                Dashboard responsive styles
  templates/               Overview, Network, navigation, and components
```

`network_setup/` is the reusable provisioning component, `shared_web/` provides
dependency-free HTTP and rendering primitives, and `device_dashboard/` owns
the connected product interface. `app.py` injects configuration and coordinates
the transition between provisioning and dashboard modes. Neither UI package
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
- Check the password and router security mode.
- Move the board closer to the access point.
- Power-cycle the board to test credentials from a clean radio state.

## Limitations

- One HTTP request is processed at a time.
- Dashboard addresses come from DHCP.
- mDNS, static LAN IPs, OTA updates, TLS, and dashboard authentication are not
  implemented.
- Processor temperature is an approximate internal reading, not ambient
  temperature.
