import sys
import time
import types
import unittest


# Provide the small MicroPython surface needed while importing app.py.
if not hasattr(time, "ticks_ms"):
    time.ticks_ms = lambda: int(time.monotonic() * 1000)
    time.ticks_add = lambda value, delta: value + delta
    time.ticks_diff = lambda value, previous: value - previous

if "machine" not in sys.modules:
    machine = types.ModuleType("machine")

    class FakeADC:
        CORE_TEMP = 4

        def __init__(self, channel):
            self.channel = channel

        def read_u16(self):
            return 0

    machine.ADC = FakeADC
    sys.modules["machine"] = machine

from app import App
from config import (
    AP_RESULT_TIMEOUT_MS,
    AP_SHUTDOWN_DELAY_MS,
    CONNECTION_PAGE_SETTLE_MS,
    CONNECTION_START_DELAY_MS,
)


class FakeSocket:
    def __init__(self, incoming=None):
        self.output = bytearray()
        self.incoming = list(incoming or [])
        self.timeout = None
        self.closed = False

    def recv(self, size):
        if not self.incoming:
            return b""
        return self.incoming.pop(0)

    def write(self, data):
        self.output.extend(data)
        return len(data)

    def settimeout(self, timeout):
        self.timeout = timeout

    def close(self):
        self.closed = True


class FakeWiFi:
    def __init__(self, result=(True, "192.168.1.20", "Connected.")):
        self.result = result
        self.setup_ap_starts = 0
        self.setup_ap_stops = 0

    def station_ip(self):
        return ""

    def connect(self, ssid, password):
        return self.result

    def start_setup_ap(self):
        self.setup_ap_starts += 1

    def stop_setup_ap(self):
        self.setup_ap_stops += 1

    def scan(self, force=False):
        return [("Home", -40)]


class FakeCredentialStore:
    def __init__(self, save_result=True):
        self.save_result = save_result
        self.saved = []

    def save(self, ssid, password):
        self.saved.append((ssid, password))
        return self.save_result


class ConnectionFlowTests(unittest.TestCase):
    def test_health_route_works_in_setup_and_device_modes(self):
        for provisioned in (False, True):
            app = App(
                FakeWiFi(),
                FakeCredentialStore(),
                provisioned=provisioned,
            )
            client = FakeSocket([
                b"GET /health HTTP/1.1\r\nHost: device\r\n\r\n",
            ])

            app.handle_client(client, ("192.168.4.2", 1234))

            self.assertIn(b"HTTP/1.1 200 OK", client.output)
            self.assertTrue(client.output.endswith(b"\r\n\r\nOK"))
            self.assertTrue(client.closed)

    def test_setup_and_dashboard_styles_have_stable_urls(self):
        app = App(FakeWiFi(), FakeCredentialStore())
        setup_client = FakeSocket([
            b"GET /setup.css HTTP/1.1\r\nHost: device\r\n\r\n",
        ])
        dashboard_client = FakeSocket([
            b"GET /style.css HTTP/1.1\r\nHost: device\r\n\r\n",
        ])

        app.handle_client(setup_client, ("192.168.4.2", 1234))
        app.handle_client(dashboard_client, ("192.168.4.2", 1234))

        self.assertIn(b".connection-progress", setup_client.output)
        self.assertNotIn(b".dashboard-layout", setup_client.output)
        self.assertIn(b".dashboard-layout", dashboard_client.output)

    def test_connect_submission_keeps_fallback_start_timer(self):
        app = App(FakeWiFi(), FakeCredentialStore())
        client = FakeSocket()
        before_request = time.ticks_ms()

        app._connect_to_wifi(client, "ssid=Home&wifi_key=secret")

        self.assertEqual(app.pending_connection, ("Home", "secret"))
        self.assertEqual(app.connection_state, "connecting")
        self.assertGreaterEqual(
            app.pending_connection_at,
            before_request + CONNECTION_START_DELAY_MS,
        )
        self.assertIn(b"303 See Other", client.output)

    def test_pending_result_polls_until_success_and_renders_page(self):
        app = App(FakeWiFi(), FakeCredentialStore())
        app.pending_connection = ("Home", "secret")
        app.pending_connection_at = time.ticks_add(time.ticks_ms(), 1500)
        app.connection_state = "connecting"
        client = FakeSocket()
        before_response = time.ticks_ms()

        app._route_connection_result(client, None)
        after_response = time.ticks_ms()

        response = client.output.decode("utf-8")
        self.assertIn("HTTP/1.1 202 Accepted", response)
        self.assertNotIn("Refresh:", response)
        self.assertIn("Connecting to Home", response)
        self.assertIn("Credentials received. Connecting now", response)
        self.assertIn("Finalizing the connection", response)
        self.assertNotIn("Check connection", response)
        self.assertNotIn("{{", response)
        self.assertGreaterEqual(
            app.pending_connection_at,
            before_response + CONNECTION_PAGE_SETTLE_MS,
        )
        self.assertLessEqual(
            app.pending_connection_at,
            after_response + CONNECTION_PAGE_SETTLE_MS,
        )

    def test_success_changes_mode_and_saves_credentials(self):
        wifi = FakeWiFi()
        store = FakeCredentialStore()
        app = App(wifi, store)
        app.pending_connection = ("Home", "secret")
        before_connection = time.ticks_ms()

        app._run_pending_connection()

        self.assertTrue(app.provisioned)
        self.assertEqual(app.connection_state, "connected")
        self.assertEqual(app.device_ip, "192.168.1.20")
        self.assertEqual(app.connected_ssid, "Home")
        self.assertEqual(store.saved, [("Home", "secret")])
        self.assertTrue(app.awaiting_setup_result)
        self.assertGreaterEqual(
            app.ap_shutdown_at,
            before_connection + AP_RESULT_TIMEOUT_MS,
        )

    def test_success_page_schedules_automatic_ap_shutdown(self):
        app = App(
            FakeWiFi(),
            FakeCredentialStore(),
            provisioned=True,
            connected_ssid="Home",
        )
        app.device_ip = "192.168.1.20"
        app.awaiting_setup_result = True
        client = FakeSocket()
        before_response = time.ticks_ms()

        app._route_provisioning_success(client, None)

        after_response = time.ticks_ms()
        response = client.output.decode("utf-8")
        shutdown_seconds = (AP_SHUTDOWN_DELAY_MS + 999) // 1000
        self.assertIn(
            "turn off in %d seconds" % shutdown_seconds,
            response,
        )
        self.assertGreaterEqual(
            app.ap_shutdown_at,
            before_response + AP_SHUTDOWN_DELAY_MS,
        )
        self.assertLessEqual(
            app.ap_shutdown_at,
            after_response + AP_SHUTDOWN_DELAY_MS,
        )
        self.assertFalse(app.awaiting_setup_result)

        first_deadline = app.ap_shutdown_at
        app._route_provisioning_success(FakeSocket(), None)
        self.assertEqual(app.ap_shutdown_at, first_deadline)

    def test_captive_probe_delivers_success_after_ap_reconnect(self):
        app = App(
            FakeWiFi(),
            FakeCredentialStore(),
            provisioned=True,
            connected_ssid="Home",
        )
        app.device_ip = "192.168.1.20"
        app.awaiting_setup_result = True
        client = FakeSocket([
            b"GET /generate_204 HTTP/1.1\r\nHost: device\r\n\r\n",
        ])

        app.handle_client(client, ("192.168.4.2", 1234))

        response = client.output.decode("utf-8")
        self.assertIn("HTTP/1.1 200 OK", response)
        self.assertIn("Setup Complete", response)
        self.assertIn("http://192.168.1.20/", response)
        self.assertFalse(app.awaiting_setup_result)
        self.assertIsNotNone(app.ap_shutdown_at)

    def test_update_disables_ap_when_shutdown_timer_expires(self):
        wifi = FakeWiFi()
        app = App(wifi, FakeCredentialStore(), provisioned=True)
        app.ap_shutdown_at = time.ticks_add(time.ticks_ms(), -1)

        app.update()

        self.assertEqual(wifi.setup_ap_stops, 1)
        self.assertIsNone(app.ap_shutdown_at)

    def test_failure_restores_setup_ap_without_saving(self):
        wifi = FakeWiFi((False, "", "Incorrect password."))
        store = FakeCredentialStore()
        app = App(wifi, store)
        app.pending_connection = ("Home", "wrong")

        app._run_pending_connection()

        self.assertFalse(app.provisioned)
        self.assertEqual(app.connection_state, "failed")
        self.assertEqual(app.connection_error, "Incorrect password.")
        self.assertEqual(wifi.setup_ap_starts, 1)
        self.assertEqual(store.saved, [])


if __name__ == "__main__":
    unittest.main()
