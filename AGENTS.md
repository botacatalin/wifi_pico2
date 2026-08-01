# AGENTS.md

## Project overview

This repository contains firmware for the **Raspberry Pi Pico 2 W**, the Pico 2
board with built-in wireless networking. It runs directly on the board under
MicroPython, provides a lightweight HTTP server, provisions the board onto a
2.4 GHz Wi-Fi network, and then serves a small device-status interface on the
LAN.

The application has two main runtime modes plus a completion transition:

- **Setup mode:** creates the open `Nodes-Setup` access point, scans nearby
  networks, accepts credentials, tests the connection, and saves credentials
  only after the station receives an IP address.
- **Completion transition:** after a successful connection, restores and keeps
  `Nodes-Setup` active, serves Setup Complete from result and captive-portal
  routes, and starts the short AP shutdown timer only after that page is sent.
- **Device mode:** uses saved credentials at startup and serves the dashboard
  over the LAN. If the saved connection fails, the board returns to setup mode.

The two packages have intentionally separate responsibilities:

- `network_setup/` is a self-contained Wi-Fi provisioning component. It owns
  Wi-Fi discovery, AP/STA management, credential persistence, and all pages
  used while configuring a network. It is expected to be reused later on
  another board, so keep device-dashboard behavior out of this package and
  avoid unnecessary dependencies on the current application.
- `device_dashboard/` is the product-specific interface used after the Pico 2 W
  has connected to Wi-Fi. It owns dashboard pages, metrics, errors, and styles.
- `peer_communication/` owns the optional local UDP discovery and bounded
  command/reply protocol without depending on either UI package.
- `plugins/` owns the versioned drop-in sensor, actuator, and integration
  interface, discovery manager, and self-contained hardware plugins.
- `shared_web/` provides reusable bounded HTTP, form, escaping, and template
  helpers without depending on application configuration or either UI package.
- `app.py` is the integration layer between those components. It selects setup
  or device mode, dispatches their routes, and coordinates the transition from
  successful provisioning to the connected dashboard.

The target is the physical Pico 2 W wireless board, not a desktop Python
environment or a non-wireless Pico 2. Prefer simple, allocation-conscious
MicroPython-compatible code over desktop-Python abstractions or dependencies.

## Current project status

- The provisioning, captive-portal recovery, saved-credential startup,
  dashboard, and optional peer-communication flows are implemented.
- The connected dashboard currently has Overview, Nodes, Network,
  Device Features, and About pages. Its visual system uses calm neutral surfaces,
  restrained green status accents, responsive cards, and compact five-tab
  navigation on narrow screens. It is self-contained and loads no external
  visual assets.
- The dependency-free host suite currently contains 93 tests. It covers HTTP
  helpers, rendering, provisioning transitions, AP shutdown scheduling,
  feature discovery and remote reads, messaging lifecycle and transport
  behavior, and Wi-Fi configuration.
- Host validation does not replace physical Pico 2 W verification. Radio and
  captive-portal behavior must still be checked on hardware after networking,
  timing, or MicroPython-version changes.

## Repository map

- `main.py` is the MicroPython boot entry point and synchronous server loop.
- `app.py` owns application state, background transitions, route tables, and
  request dispatch for setup and device modes.
- `config.py` contains device identity, network settings, timeouts, request
  limits, and route constants.
- `shared_web/template.py` implements the small file-based template language.
- `app_logging.py` contains the application-configured logging helper.
- `network_setup/wifi.py` wraps reusable AP/STA radio setup, scanning, and
  connection behavior.
- `network_setup/credentials.py` manages `wifi_credentials.json` using a
  temporary file during updates.
- `network_setup/pages.py` renders provisioning pages from
  `network_setup/templates/`.
- `shared_web/http.py` parses bounded HTTP requests and writes socket responses.
- `device_dashboard/pages.py` renders dashboard and error pages from
  `device_dashboard/templates/`.
- `peer_communication/plugin.py` owns messaging enablement and saved state;
  `peer_communication/peer.py` owns UDP discovery and command/reply transport.
- `peer_communication/vocabulary.json` owns editable ping display text only;
  wire command names and protocol behavior remain in Python.
- `plugins/interface.py` defines the required device-feature API;
  `plugins/manager.py` validates, discovers, and owns installed plugins.
- Each feature folder owns a `vocabulary.json` containing only its editable
  name, description, and field labels.
- Each UI component owns its stylesheet.
- `README.md` is the user-facing installation, behavior, and troubleshooting
  guide; update it when visible behavior, configuration, or routes change.

## Architecture and behavior

- The server is deliberately synchronous and handles one socket at a time.
- `App.provisioned` selects the active route table.
- `App.awaiting_setup_result` temporarily overrides captive-portal routes after
  provisioning so a client returning to the restored AP receives Setup Complete
  instead of the dashboard or a not-found response.
- Keep `network_setup/` and `device_dashboard/` logically independent. Shared
  orchestration belongs in `app.py`; neither package should import the other.
- Keep board-specific values configurable. Reusable provisioning code should
  receive collaborators or read configuration rather than depend on dashboard
  details, hard-coded application state, or a particular future board layout.
- Files under `network_setup/templates/` belong only to the provisioning flow.
  Files under `device_dashboard/templates/` belong only to the dashboard.
- `App.update()` advances deferred connection work and shuts down the temporary
  setup AP after successful provisioning.
- A successful connection first receives the long `AP_RESULT_TIMEOUT_MS`
  recovery window. Delivering Setup Complete replaces it with
  `AP_SHUTDOWN_DELAY_MS`; repeated captive probes must not reset that deadline.
- The Pico uses one CYW43 radio for both AP and station interfaces. Changes to
  STA state can briefly disrupt the setup AP, so preserve the existing timing
  and deferred-result flow unless the full provisioning sequence is retested.
- Captive-portal probe paths are configured in `CAPTIVE_PORTAL_ROUTES`.
- HTTP request headers and bodies are bounded by values in `config.py`.
- Templates support value substitution (`{{ VALUE }}`), component inclusion
  (`{{> component.html}}`), and conditional inclusion
  (`{{? VALUE > component.html}}`). Includes resolve relative to the current
  template.

## Development guidelines

- Target current Raspberry Pi Pico 2 W-compatible MicroPython, not CPython.
  Code may use the board's built-in CYW43 wireless interface through
  MicroPython's `network` module. Do not introduce libraries or language
  features without confirming MicroPython and Pico 2 W support.
- Keep the project dependency-free unless a new dependency is explicitly
  required and suitable for the board's storage and memory limits.
- Favor short-lived objects, explicit cleanup, and the existing `gc.collect()`
  boundaries in request and connection paths.
- Use `time.ticks_ms()` and `time.ticks_diff()` for elapsed-time calculations;
  raw subtraction is unsafe when MicroPython tick counters wrap.
- Keep route paths centralized in `config.py`, and register behavior in the
  correct setup/device route table in `app.py`.
- When extending provisioning, change `network_setup/` and expose a small API
  for `app.py` to call. When adding connected-device data or dashboard UI,
  change `device_dashboard/` and pass the required values from `app.py`.
- Do not move dashboard routes, data rendering, or device controls into
  `network_setup/`. Do not move scanning, credentials, setup AP behavior, or
  provisioning pages into `device_dashboard/`.
- Escape all dynamic text inserted into HTML with `html_escape()`. Template
  substitution does not escape values automatically.
- Treat SSIDs, passwords, request bodies, and headers as untrusted input.
- Never log Wi-Fi passwords or return them in pages or API responses.
- Do not commit `wifi_credentials.json` or `wifi_credentials.tmp`; they contain
  runtime secrets in plain text.
- Preserve request-size limits, socket timeouts, `Connection: close`, and the
  partial-write handling in `write_all()`.
- Keep HTML/CSS compact and usable on phone-sized captive-portal browsers.
- Every drop-in device feature must inherit `DeviceFeature`, use the current API
  version, declare `exposed_fields`, implement `render()` and a matching
  dictionary-returning `read()`, expose `create_feature()`, and include a
  display-only `vocabulary.json` loaded through `load_vocabulary()`.
  Hardware access, templates, actions, and optional lifecycle overrides belong
  inside that feature's folder.
- Keep functional identifiers and behavior in Python: `feature_id`,
  `feature_type`, `requires_external_hardware`, `exposed_fields`,
  `remote_operations`, field validation, and peer wire commands must not be
  moved into vocabulary JSON. Editing display text must not change protocol or
  hardware behavior.
- Keep the connected dashboard comfortable for sustained viewing: preserve
  readable contrast, quiet neutral surfaces, restrained accent use, obvious
  warning states, and clear information hierarchy. Avoid animation, visual
  clutter, or decorative assets that increase transfer or rendering cost.
- Preserve the responsive dashboard behavior: desktop sidebar navigation
  becomes a compact five-tab bar on narrow screens, while metric and peer-card
  grids collapse to one column. Verify both layouts when changing templates or
  styles.
- The dashboard must remain self-contained. Do not add web fonts, CDN assets,
  external UI libraries, or required internet-hosted scripts.
- Preserve package directories and their `__init__.py` files because the full
  tree is copied directly to the Pico filesystem.

## Making changes

When changing network behavior, follow the complete state transition:

1. Startup attempts credentials through `main.py`.
2. Setup routes schedule and report connection work through `app.py`.
3. `network_setup/wifi.py` resets STA state and interprets CYW43 status codes.
4. Credentials are persisted only after a confirmed connection and LAN IP.
5. Successful provisioning sets `App.awaiting_setup_result` and restores the
   setup AP before returning to the request loop.
6. `/connection-result`, `/`, or a captive-portal probe delivers Setup Complete.
7. The short countdown starts only after the complete success response is
   written; at expiry `App.update()` disables the setup AP.

When changing a page, inspect both the page renderer and its master/component
templates. Keep visual rules in the stylesheet owned by the relevant component
rather than inline styles. If adding or renaming a template placeholder, update
the matching value map in the relevant `pages.py` module.

When preparing `network_setup/` for another board, preserve its public concepts
(`WiFi`, `CredentialStore`, and provisioning page functions) where practical.
Isolate hardware differences behind the Wi-Fi implementation or injected
collaborators instead of coupling reusable setup pages and credential logic to
the dashboard server.

## Validation

The dependency-free host-side test suite covers HTTP helpers, rendering,
provisioning transitions, captive-portal recovery, and AP shutdown scheduling.
Before finishing a change, run:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q .
git diff --check
```

`compileall` checks syntax only; it does not prove MicroPython compatibility or
exercise the Pico 2 W's CYW43 wireless hardware through the `network` module.
Ignore generated `__pycache__/` artifacts and do not include them in commits.

For HTTP, template, or utility changes, use small CPython tests with fake socket
or Wi-Fi objects where practical. For network lifecycle changes, verify on a
Pico 2 W:

- first boot exposes `Nodes-Setup` and `http://192.168.4.1/`;
- scanning and rescan work with 2.4 GHz networks;
- wrong credentials return a useful error and do not replace saved credentials;
- correct credentials restore `Nodes-Setup`, show Setup Complete and the LAN IP,
  and survive a restart;
- the 10-second countdown begins after Setup Complete is delivered, and the
  setup AP turns off when it expires;
- `/health` returns `OK` in both modes;
- forgetting Wi-Fi deletes saved credentials and setup returns after restart.

Use plain `http://` for device checks; this project does not implement TLS.

## Scope and hygiene

- Keep changes focused and preserve unrelated work in the working tree.
- Do not commit generated bytecode, IDE files, virtual environments, or runtime
  credential files.
- Avoid broad refactors in timing-sensitive Wi-Fi code unless requested.
- If behavior differs between CPython and MicroPython, the Pico 2 W behavior is
  authoritative and the difference should be documented.
