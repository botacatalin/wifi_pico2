# app.py

import gc
import json
import time

from config import (
    AP_SHUTDOWN_DELAY_MS,
    AP_RESULT_TIMEOUT_MS,
    AP_IP,
    AP_SSID,
    CAPTIVE_PORTAL_ROUTES,
    CONNECTION_START_DELAY_MS,
    CONNECTION_PAGE_SETTLE_MS,
    CONNECTION_POLL_INTERVAL_MS,
    CONNECTION_REQUEST_TIMEOUT_MS,
    CONNECT_TIMEOUT_MS,
    DASHBOARD_ACCENT_COLOR,
    DASHBOARD_BACKGROUND_COLOR,
    DEVICE_NAME,
    MAX_BODY_BYTES,
    MAX_HEADER_BYTES,
    COMMUNICATION_MAX_PAYLOAD_BYTES,
    PROCESSOR_TEMPERATURE_CRITICAL_C,
    ROUTE_ABOUT,
    ROUTE_FEATURES,
    ROUTE_CLEAR_CONVERSATION,
    ROUTE_COMMUNICATION_TOGGLE,
    ROUTE_COMMUNICATION_REFRESH,
    ROUTE_CONNECT,
    ROUTE_CONNECTION_RESULT,
    ROUTE_CONNECTION_STATUS,
    ROUTE_FORGET_WIFI,
    ROUTE_HEALTH,
    ROUTE_HOME,
    ROUTE_NODES,
    ROUTE_MESSAGE_REVISION,
    ROUTE_NETWORK,
    ROUTE_README,
    ROUTE_RESCAN,
    ROUTE_SETUP_STYLE,
    ROUTE_SEND_COMMAND,
    ROUTE_STYLE,
    SOCKET_TIMEOUT_SECONDS,
    STATIC_CACHE_SECONDS,
    WIFI_CREDENTIALS_FILE,
    WIFI_CREDENTIALS_TEMP_FILE,
)

from shared_web import (
    parse_form,
    read_request,
    send_html,
    send_redirect,
    send_response,
    send_text,
)

from network_setup.pages import (
    connection_pending_page,
    provisioning_page,
    provisioning_success_page,
)

from network_setup.credentials import CredentialStore

from device_dashboard.pages import (
    device_page,
    error_page,
)
from device_dashboard.metrics import ServerMetrics

from app_logging import log


class App:

    def __init__(
        self,
        wifi,
        credential_store=None,
        provisioned=False,
        connected_ssid="",
        communication_plugin=None,
        feature_manager=None,
    ):
        self.wifi = wifi
        self.credential_store = (
            credential_store
            if credential_store is not None
            else CredentialStore(
                path=WIFI_CREDENTIALS_FILE,
                temporary_path=WIFI_CREDENTIALS_TEMP_FILE,
                logger=log,
            )
        )
        self.provisioned = provisioned
        self.device_ip = wifi.station_ip() if provisioned else ""
        self.connected_ssid = connected_ssid
        self.communication_plugin = communication_plugin
        self.feature_manager = feature_manager
        self.feature_notice = None
        self.server_message = ""
        self.server_message_page = None
        self.connection_state = "connected" if provisioned else "idle"
        self.connection_error = ""
        self.pending_connection = None
        self.pending_connection_at = None
        self.awaiting_setup_result = False
        self.server_metrics = ServerMetrics(
            PROCESSOR_TEMPERATURE_CRITICAL_C,
            temperature_reader=(
                self._processor_temperature_c
                if self.feature_manager is not None else None
            ),
        )

        self.ap_shutdown_at = None

        self.setup_routes = {
            ("GET", ROUTE_RESCAN): self._route_rescan,
            ("POST", ROUTE_CONNECT): self._route_connect,
            ("GET", ROUTE_CONNECTION_STATUS): self._route_connection_status,
            ("GET", ROUTE_CONNECTION_RESULT): self._route_connection_result,
            ("GET", ROUTE_HEALTH): self._route_health,
            ("GET", ROUTE_SETUP_STYLE): self._route_setup_style,
            ("GET", ROUTE_STYLE): self._route_style,
        }

        self.device_routes = {
            ("GET", ROUTE_HOME): self._route_device_home,
            ("GET", ROUTE_NODES): self._route_nodes,
            ("GET", ROUTE_NETWORK): self._route_network,
            ("GET", ROUTE_ABOUT): self._route_about,
            ("GET", ROUTE_FEATURES): self._route_features,
            ("GET", ROUTE_CONNECT): self._route_provisioning_success,
            ("GET", ROUTE_CONNECTION_STATUS): self._route_connection_status,
            ("GET", ROUTE_CONNECTION_RESULT): self._route_connection_result,
            ("POST", ROUTE_FORGET_WIFI): self._route_forget_wifi,
            ("GET", ROUTE_HEALTH): self._route_health,
            ("GET", ROUTE_SETUP_STYLE): self._route_setup_style,
            ("GET", ROUTE_STYLE): self._route_style,
            ("GET", ROUTE_README): self._route_readme,
            ("GET", ROUTE_MESSAGE_REVISION): self._route_message_revision,
            ("POST", ROUTE_COMMUNICATION_TOGGLE): self._route_communication_toggle,
            ("POST", ROUTE_COMMUNICATION_REFRESH): self._route_communication_refresh,
            ("POST", ROUTE_CLEAR_CONVERSATION): self._route_clear_conversation,
            ("POST", ROUTE_SEND_COMMAND): self._route_send_command,
        }

        if self.communication_plugin is not None:
            self.communication_plugin.set_network_ready(self.provisioned)

    # =====================================================
    # Background tasks
    # =====================================================

    def _processor_temperature_c(self):
        ok, values = self.feature_manager.read_values(
            "processor-temperature"
        )
        if not ok:
            return None
        value = values.get("temperature_c")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        return None

    def update(self):
        """
        Disable the temporary setup access point after
        the successful setup page has been delivered.
        """

        self.server_metrics.update()
        current_tick = time.ticks_ms()

        if self.provisioned and self.communication_plugin is not None:
            try:
                self.communication_plugin.update()
            except Exception as exc:
                log("Communication update failed: %s" % exc)

        if self.provisioned and self.feature_manager is not None:
            self.feature_manager.update()

        if self.pending_connection is not None:
            if time.ticks_diff(
                current_tick,
                self.pending_connection_at,
            ) >= 0:
                self._run_pending_connection()

        if self.ap_shutdown_at is not None:
            if time.ticks_diff(
                current_tick,
                self.ap_shutdown_at,
            ) >= 0:
                self.wifi.stop_setup_ap()
                self.ap_shutdown_at = None
                self.awaiting_setup_result = False

    # =====================================================
    # Client handling
    # =====================================================

    def handle_client(
        self,
        client,
        address,
    ):
        try:
            # Responses are deliberately split into a header write and a body
            # write. Disable Nagle where supported so the small header is not
            # held while TCP waits for an acknowledgement before sending the
            # page body. Older MicroPython builds may omit these constants.
            try:
                import socket
                client.setsockopt(
                    socket.IPPROTO_TCP,
                    socket.TCP_NODELAY,
                    1,
                )
            except Exception:
                pass

            client.settimeout(
                SOCKET_TIMEOUT_SECONDS
            )

            request = read_request(
                client,
                max_header_bytes=MAX_HEADER_BYTES,
                max_body_bytes=MAX_BODY_BYTES,
            )

            log(
                "%s %s from %s"
                % (
                    request.method,
                    request.path,
                    address,
                )
            )

            if self.provisioned:
                self._dispatch_device_route(
                    client,
                    request,
                )
            else:
                self._dispatch_setup_route(
                    client,
                    request,
                )

        except ValueError as exc:
            log(
                "Bad request: %s"
                % exc
            )

            try:
                send_html(
                    client,
                    error_page(str(exc)),
                    status="400 Bad Request",
                )
            except Exception:
                pass

        except Exception as exc:
            log(
                "Client error: %s"
                % exc
            )

        finally:
            try:
                client.close()
            except Exception:
                pass

            gc.collect()

    # =====================================================
    # Route dispatch
    # =====================================================

    def _dispatch_setup_route(
        self,
        client,
        request,
    ):
        route_key = (
            request.method,
            request.path,
        )

        handler = self.setup_routes.get(
            route_key
        )

        if handler is not None:
            handler(
                client,
                request,
            )

            return

        if (
            request.method == "GET"
            and request.path
            in CAPTIVE_PORTAL_ROUTES
        ):
            self._route_setup_home(
                client,
                request,
            )

            return

        self._send_not_found(
            client,
            "The requested setup page was not found.",
        )

    def _dispatch_device_route(
        self,
        client,
        request,
    ):
        # After provisioning, keep captive-portal navigation in the setup
        # completion flow until that page has actually reached the browser.
        # Phones commonly issue one of these probes after reconnecting to the
        # restored setup AP on its new radio channel.
        if (
            self.awaiting_setup_result
            and request.method == "GET"
            and request.path in CAPTIVE_PORTAL_ROUTES
        ):
            self._route_provisioning_success(
                client,
                request,
            )
            return

        route_key = (
            request.method,
            request.path,
        )

        handler = self.device_routes.get(
            route_key
        )

        if handler is None:
            if self._dispatch_feature_route(client, request):
                return
            self._send_not_found(
                client,
                "The requested device page was not found.",
            )

            return

        handler(
            client,
            request,
        )

    # =====================================================
    # Shared routes
    # =====================================================

    def _route_health(
        self,
        client,
        request,
    ):
        send_text(
            client,
            "OK",
        )

    def _route_style(
        self,
        client,
        request,
    ):
        self._send_file(
            client,
            "device_dashboard/style.css",
            "text/css; charset=utf-8",
            "Stylesheet not found.",
            cache_control="public, max-age=%d" % STATIC_CACHE_SECONDS,
        )

    def _route_setup_style(
        self,
        client,
        request,
    ):
        self._send_file(
            client,
            "network_setup/style.css",
            "text/css; charset=utf-8",
            "Stylesheet not found.",
            cache_control="public, max-age=%d" % STATIC_CACHE_SECONDS,
        )

    def _route_readme(
        self,
        client,
        request,
    ):
        self._send_file(
            client,
            "README.md",
            "text/markdown; charset=utf-8",
            "README.md not found.",
        )

    def _send_file(
        self,
        client,
        path,
        content_type,
        missing_message,
        cache_control="no-store",
    ):
        try:
            with open(path, "rb") as file:
                body = file.read()
        except OSError:
            send_text(
                client,
                missing_message,
                status="404 Not Found",
            )
            return

        send_response(
            client,
            body,
            content_type=content_type,
            cache_control=cache_control,
        )

    # =====================================================
    # Setup routes
    # =====================================================

    def _route_setup_home(
        self,
        client,
        request,
    ):
        self._show_setup_page(
            client
        )

    def _route_rescan(
        self,
        client,
        request,
    ):
        self._show_setup_page(
            client,
            force_scan=True,
        )

    def _route_connect(
        self,
        client,
        request,
    ):
        self._connect_to_wifi(
            client,
            request.body,
        )

    def _show_setup_page(
        self,
        client,
        force_scan=False,
        message="",
    ):
        if not message and self.connection_error:
            message = self.connection_error
            self.connection_error = ""

        networks = self.wifi.scan(
            force=force_scan
        )

        send_html(
            client,
            provisioning_page(
                networks=networks,
                message=message,
                device_name=DEVICE_NAME,
            ),
        )

    def _connect_to_wifi(
        self,
        client,
        body,
    ):
        form = parse_form(body)

        ssid = form.get(
            "ssid",
            "",
        ).strip()

        password = form.get(
            "wifi_key",
            "",
        )

        if not ssid:
            self._show_setup_page(
                client,
                message="Please select a Wi-Fi network.",
            )
            return

        if self.pending_connection is not None:
            send_redirect(
                client,
                ROUTE_CONNECTION_RESULT,
                status="303 See Other",
            )
            return

        self.pending_connection = (ssid, password)
        self.pending_connection_at = time.ticks_add(
            time.ticks_ms(),
            # Fallback for clients that do not follow the redirect. A client
            # that receives /connection-result starts the work immediately
            # after that page has been written to its socket.
            CONNECTION_START_DELAY_MS,
        )
        self.connection_state = "connecting"
        self.connection_error = ""

        form = None
        gc.collect()

        send_redirect(
            client,
            ROUTE_CONNECTION_RESULT,
            status="303 See Other",
        )

    def _run_pending_connection(self):
        ssid, password = self.pending_connection
        self.pending_connection = None
        self.pending_connection_at = None

        connected, ip, message = self.wifi.connect(
            ssid,
            password,
        )

        if not connected:
            password = None
            gc.collect()
            self.connection_state = "failed"
            self.connection_error = message

            # A station connection attempt can disturb AP_IF because both
            # interfaces share one radio. Re-apply the setup AP configuration
            # so the browser has a reliable page to return to.
            try:
                self.wifi.start_setup_ap()
            except Exception as exc:
                log("Could not restore setup access point: %s" % exc)

            return

        saved = self.credential_store.save(ssid, password)
        password = None
        gc.collect()

        self.provisioned = True
        self.device_ip = ip
        self.connected_ssid = ssid
        self.connection_state = "connected"
        self.awaiting_setup_result = True

        if self.communication_plugin is not None:
            self.communication_plugin.set_network_ready(True)

        # Keep the AP available for recovery if the browser loses association
        # while the shared radio changes channel. Delivering the success page
        # replaces this fallback with the normal short shutdown delay.
        self._schedule_ap_shutdown(AP_RESULT_TIMEOUT_MS)

        if not saved:
            self.server_message = (
                "Connected, but the Wi-Fi password could not be saved."
            )
            self.server_message_page = "overview"

        log("Setup completed.")

        log(
            "Device page: http://%s/"
            % ip
        )

    def _route_connection_status(
        self,
        client,
        request,
    ):
        send_response(
            client,
            json.dumps({
                "state": self.connection_state,
                "ip": self.device_ip,
            }),
            content_type="application/json; charset=utf-8",
        )

    def _route_connection_result(
        self,
        client,
        request,
    ):
        if self.connection_state == "connected":
            self._route_provisioning_success(client, request)
            return

        if self.connection_state == "failed":
            self._show_setup_page(client)
            return

        pending_ssid = (
            self.pending_connection[0]
            if self.pending_connection is not None
            else ""
        )

        send_html(
            client,
            connection_pending_page(
                pending_ssid,
                setup_ssid=AP_SSID,
                setup_ip=AP_IP,
                status_route=ROUTE_CONNECTION_STATUS,
                result_route=ROUTE_CONNECTION_RESULT,
                connect_timeout_seconds=(CONNECT_TIMEOUT_MS + 999) // 1000,
                poll_interval_ms=CONNECTION_POLL_INTERVAL_MS,
                request_timeout_ms=CONNECTION_REQUEST_TIMEOUT_MS,
            ),
            status="202 Accepted",
        )

        # The browser now has the complete progress page, so the radio can
        # change channel after a short transmission-settle window. App.update()
        # runs the blocking connection after this request has closed.
        if self.pending_connection is not None:
            self.pending_connection_at = time.ticks_add(
                time.ticks_ms(),
                CONNECTION_PAGE_SETTLE_MS,
            )

    # =====================================================
    # Device routes
    # =====================================================

    def _route_provisioning_success(
        self,
        client,
        request,
    ):
        first_delivery = self.awaiting_setup_result

        send_html(
            client,
            provisioning_success_page(
                ip=self.device_ip,
                network_name=self.connected_ssid,
                device_name=DEVICE_NAME,
                ap_shutdown_delay_seconds=(
                    AP_SHUTDOWN_DELAY_MS + 999
                ) // 1000,
            ),
        )

        # Start the short shutdown timer only after the success page has been
        # written. Repeated captive probes must not keep resetting the timer.
        if first_delivery:
            self.awaiting_setup_result = False
            self._schedule_ap_shutdown(AP_SHUTDOWN_DELAY_MS)
            log(
                "Setup Complete delivered; setup AP will stop in %d seconds."
                % ((AP_SHUTDOWN_DELAY_MS + 999) // 1000)
            )

    def _schedule_ap_shutdown(self, delay_ms):
        self.ap_shutdown_at = time.ticks_add(
            time.ticks_ms(),
            delay_ms,
        )

    def _route_device_home(
        self,
        client,
        request,
    ):
        self._show_device_page(client, "overview")

    def _route_nodes(
        self,
        client,
        request,
    ):
        self._show_device_page(client, "nodes")

    def _route_message_revision(self, client, request):
        plugin = self.communication_plugin
        revision = plugin.message_revision() if plugin is not None else 0
        send_text(client, str(revision))

    def _route_network(
        self,
        client,
        request,
    ):
        self._show_device_page(client, "network")

    def _route_about(
        self,
        client,
        request,
    ):
        self._show_device_page(client, "about")

    def _route_features(self, client, request):
        self._show_device_page(client, "features")

    def _dispatch_feature_route(self, client, request):
        if (
            self.feature_manager is None
            or not request.path.startswith(ROUTE_FEATURES + "/")
        ):
            return False

        remainder = request.path[len(ROUTE_FEATURES) + 1:]
        parts = remainder.split("/")
        feature = self.feature_manager.get(parts[0])
        if feature is None:
            return False

        if request.method == "GET" and len(parts) == 1:
            self._show_feature_page(client, feature)
            return True

        if request.method == "POST" and len(parts) == 2 and parts[1]:
            try:
                message = feature.handle_action(
                    parts[1], parse_form(request.body)
                ) or ""
            except ValueError as exc:
                message = str(exc)
            except Exception as exc:
                log("Feature %s action failed: %s" % (feature.feature_id, exc))
                message = "The feature action could not be completed."
            self.feature_notice = (feature.feature_id, message)
            send_redirect(
                client,
                ROUTE_FEATURES + "/" + feature.feature_id,
                status="303 See Other",
            )
            return True

        return False

    def _show_feature_page(self, client, feature):
        message = ""
        if self.feature_notice is not None:
            feature_id, notice = self.feature_notice
            if feature_id == feature.feature_id:
                message = notice
            self.feature_notice = None
        try:
            content = feature.render(message)
        except Exception as exc:
            log("Feature %s render failed: %s" % (feature.feature_id, exc))
            send_html(
                client,
                error_page("The feature page could not be displayed."),
                status="500 Internal Server Error",
            )
            return
        self._show_device_page(client, "features", content)

    def _route_communication_toggle(self, client, request):
        self.server_message_page = "network"
        plugin = self.communication_plugin
        if plugin is None:
            self.server_message = "The communication plugin is unavailable."
        else:
            form = parse_form(request.body)
            enabled = form.get("enabled") == "1"
            if plugin.set_enabled(enabled):
                self.server_message = ""
            else:
                self.server_message = "Could not change communication plugin state."
        send_redirect(client, ROUTE_NETWORK, status="303 See Other")

    def _route_send_command(self, client, request):
        self.server_message_page = "nodes"
        form = parse_form(request.body)
        peer_name = form.get("peer", "").strip()
        command = form.get("command", "").strip()
        payload = (
            form.get("feature_id", "").strip()
            if command == "feature_read"
            else form.get("payload", "").strip()
        )

        if self.communication_plugin is None:
            self.server_message = "The communication plugin is unavailable."
        else:
            try:
                ok, reply = self.communication_plugin.send_command(
                    peer_name, command, payload
                )
                if ok:
                    # Successful replies are rendered in the chat window.
                    self.server_message = ""
                else:
                    self.server_message = (
                        "Could not reach %s: %s" % (peer_name, reply)
                    )
            except Exception as exc:
                log("Could not send communication command: %s" % exc)
                self.server_message = "The command could not be sent."

        send_redirect(client, ROUTE_NODES, status="303 See Other")

    def _route_communication_refresh(self, client, request):
        self.server_message_page = "nodes"
        plugin = self.communication_plugin
        if plugin is None or not plugin.enabled:
            self.server_message = "Enable the communication plugin first."
        elif not plugin.refresh_devices():
            self.server_message = (
                "Device discovery is unavailable. Check the Wi-Fi connection."
            )
        else:
            # A successful refresh is reflected by the device list itself.
            self.server_message = ""
        send_redirect(client, ROUTE_NODES, status="303 See Other")

    def _route_clear_conversation(self, client, request):
        if self.communication_plugin is not None:
            self.communication_plugin.clear_messages()
        self.server_message = ""
        self.server_message_page = "nodes"
        send_redirect(client, ROUTE_NODES, status="303 See Other")

    def _show_device_page(self, client, page, feature_content=""):
        current_ip = self.wifi.station_ip()

        if current_ip:
            self.device_ip = current_ip

        plugin = None
        uptime = ""
        temperature = "Unavailable"
        temperature_state = ""

        if page == "overview":
            uptime = self.server_metrics.uptime_text()
            temperature, temperature_state = (
                self.server_metrics.temperature_status()
            )
        elif page in ("nodes", "network"):
            plugin = self.communication_plugin

        send_html(
            client,
            device_page(
                self.device_ip,
                network_name=self.connected_ssid,
                message=(
                    self.server_message
                    if self.server_message_page in (None, page)
                    else ""
                ),
                uptime=uptime,
                temperature=temperature,
                temperature_state=temperature_state,
                page=page,
                device_name=DEVICE_NAME,
                background_color=DASHBOARD_BACKGROUND_COLOR,
                accent_color=DASHBOARD_ACCENT_COLOR,
                temperature_limit=PROCESSOR_TEMPERATURE_CRITICAL_C,
                communication_enabled=(
                    plugin.enabled if plugin is not None else False
                ),
                node_name=(
                    plugin.node_name if plugin is not None else ""
                ),
                communication_group_name=(
                    plugin.group_name if plugin is not None else ""
                ),
                peers=(
                    plugin.available_peers()
                    if page == "nodes" and plugin is not None else []
                ),
                messages=(
                    plugin.recent_messages()
                    if page == "nodes" and plugin is not None else []
                ),
                message_revision=(
                    plugin.message_revision()
                    if page == "nodes" and plugin is not None else 0
                ),
                message_revision_route=ROUTE_MESSAGE_REVISION,
                communication_toggle_route=ROUTE_COMMUNICATION_TOGGLE,
                communication_refresh_route=ROUTE_COMMUNICATION_REFRESH,
                clear_conversation_route=ROUTE_CLEAR_CONVERSATION,
                send_command_route=ROUTE_SEND_COMMAND,
                max_payload_length=COMMUNICATION_MAX_PAYLOAD_BYTES,
                features=(
                    self.feature_manager.features()
                    if page == "features" and self.feature_manager is not None
                    else ()
                ),
                feature_content=feature_content,
            ),
        )

    def _route_forget_wifi(
        self,
        client,
        request,
    ):
        self.server_message_page = "network"
        network_name = self.connected_ssid
        removed = self.credential_store.delete()
        self.connected_ssid = ""

        if removed:
            self.server_message = (
                "Forgot saved Wi-Fi credentials for %s. "
                "The current connection remains active until restart."
                % network_name
            )
        else:
            self.server_message = "No saved Wi-Fi credentials were found."

        self._route_network(client, request)

    # =====================================================
    # Errors
    # =====================================================

    def _send_not_found(
        self,
        client,
        message,
    ):
        send_html(
            client,
            error_page(message),
            status="404 Not Found",
        )
