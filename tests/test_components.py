import os
import tempfile
import unittest

from network_setup.credentials import CredentialStore
from network_setup.pages import (
    connection_pending_page,
    provisioning_page,
    provisioning_success_page,
)
from shared_web import parse_form, read_request, send_html, send_response


class FakeSocket:
    def __init__(self, chunks=None, write_size=None):
        self.chunks = list(chunks or [])
        self.write_size = write_size
        self.output = bytearray()

    def recv(self, size):
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    def write(self, data):
        size = min(len(data), self.write_size or len(data))
        self.output.extend(data[:size])
        return size


class HttpTests(unittest.TestCase):
    def test_fragmented_request_and_form_body(self):
        client = FakeSocket([
            b"POST /connect?source=test HTTP/1.1\r\nContent-L",
            b"ength: 14\r\n\r\nssid=Home+WiFi",
        ])
        request = read_request(client)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/connect")
        self.assertEqual(parse_form(request.body), {"ssid": "Home WiFi"})

    def test_response_handles_partial_writes(self):
        client = FakeSocket(write_size=3)
        send_response(client, "OK", content_type="text/plain")
        self.assertIn(b"Content-Length: 2\r\n", client.output)
        self.assertTrue(client.output.endswith(b"\r\n\r\nOK"))

    def test_html_response_accepts_extra_headers(self):
        client = FakeSocket()
        send_html(
            client,
            "waiting",
            status="202 Accepted",
            extra_headers={"Refresh": "5; url=/connection-result"},
        )
        self.assertIn(
            b"Refresh: 5; url=/connection-result\r\n",
            client.output,
        )


class CredentialStoreTests(unittest.TestCase):
    def test_round_trip_uses_injected_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "credentials.json")
            temporary_path = os.path.join(directory, "credentials.tmp")
            store = CredentialStore(path, temporary_path, logger=lambda _: None)
            self.assertTrue(store.save("Home", "secret"))
            self.assertEqual(store.load(), {"ssid": "Home", "password": "secret"})
            self.assertTrue(store.delete())
            self.assertIsNone(store.load())


class ProvisioningPageTests(unittest.TestCase):
    def test_page_uses_injected_identity_and_escapes_ssid(self):
        page = provisioning_page(
            [("A&B", -42)],
            device_name="Reusable Board",
        )
        self.assertIn("Reusable Board Setup", page)
        self.assertIn("A&amp;B", page)
        self.assertNotIn(">A&B<", page)

    def test_pending_page_has_bounded_polling_and_routes(self):
        page = connection_pending_page(
            "Home",
            status_route="/status-test",
            result_route="/result-test",
            request_timeout_ms=2300,
        )
        self.assertIn('fetch(\n            "/status-test?t="', page)
        self.assertIn('"/result-test?t="', page)
        self.assertIn("controller.abort()", page)
        self.assertIn("}, 2300);", page)
        self.assertNotIn("Check connection", page)

    def test_success_page_uses_configured_ap_countdown(self):
        page = provisioning_success_page(
            "192.168.1.20",
            ap_shutdown_delay_seconds=17,
        )
        self.assertIn("turn off in 17 seconds", page)
        self.assertIn("var remaining = 17;", page)
        self.assertNotIn("{{", page)


if __name__ == "__main__":
    unittest.main()
