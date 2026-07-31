import os
import builtins
import tempfile
import time
import unittest

if not hasattr(time, "ticks_ms"):
    time.ticks_ms = lambda: int(time.monotonic() * 1000)
if not hasattr(time, "ticks_add"):
    time.ticks_add = lambda value, delta: value + delta
if not hasattr(time, "ticks_diff"):
    time.ticks_diff = lambda value, previous: value - previous
if not hasattr(time, "sleep_ms"):
    time.sleep_ms = lambda milliseconds: time.sleep(milliseconds / 1000)

from network_setup.credentials import CredentialStore
from network_setup.networks import ipv4_broadcast_address
from network_setup.pages import (
    connection_pending_page,
    provisioning_page,
    provisioning_success_page,
)
from device_dashboard.pages import device_page
from peer_communication import (
    CommunicationPlugin,
    PeerNetwork,
    PluginStateStore,
)
from shared_web import parse_form, read_request, render_template, send_html, send_response
from shared_web import template as template_module


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


class TemplateTests(unittest.TestCase):
    def test_template_source_is_read_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "page.html")
            with open(path, "w") as file:
                file.write("Hello {{ NAME }}")

            template_module._template_cache.pop(path, None)
            real_open = builtins.open
            reads = []

            def tracking_open(candidate, *args, **kwargs):
                if candidate == path:
                    reads.append(candidate)
                return real_open(candidate, *args, **kwargs)

            builtins.open = tracking_open
            try:
                self.assertEqual(render_template(path, {"NAME": "A"}), "Hello A")
                self.assertEqual(render_template(path, {"NAME": "B"}), "Hello B")
            finally:
                builtins.open = real_open
                template_module._template_cache.pop(path, None)

            self.assertEqual(reads, [path])


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


class NetworkHelperTests(unittest.TestCase):
    def test_ipv4_broadcast_address_uses_station_netmask(self):
        self.assertEqual(
            ipv4_broadcast_address("192.168.1.98", "255.255.255.0"),
            "192.168.1.255",
        )
        self.assertEqual(
            ipv4_broadcast_address("10.20.18.4", "255.255.252.0"),
            "10.20.19.255",
        )


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


class DevicePageTests(unittest.TestCase):
    def test_messaging_lists_and_escapes_discovered_peers(self):
        page = device_page(
            "192.168.1.20",
            page="messages",
            node_name="nodes-a1b2",
            communication_group_name="workshop",
            communication_enabled=True,
            peers=[{"name": 'peer<one>', "ip": '192.168.1.21'}],
            messages=[{
                "direction": "received",
                "node": "peer<one>",
                "payload": '<script>alert("x")</script>',
                "created_at_ms": time.ticks_ms(),
            }],
        )

        self.assertIn("<h1>Messages</h1>", page)
        self.assertIn("<dt>Board ID</dt><dd>nodes-a1b2</dd>", page)
        self.assertIn("<dt>Group name</dt><dd>workshop</dd>", page)
        self.assertIn("peer&lt;one&gt;", page)
        self.assertNotIn("peer<one>", page)
        self.assertIn("IP address <code>192.168.1.21</code>", page)
        self.assertIn(
            '<span class="badge ip-badge">Device IP: '
            '<code>192.168.1.20</code></span>',
            page,
        )
        self.assertIn(
            '<span class="badge network-badge">Not saved</span>', page
        )
        self.assertIn('value="peer&lt;one&gt;" checked', page)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertIn('<time data-message-age-ms="', page)
        self.assertIn("messageDate.toLocaleTimeString", page)
        self.assertIn('action="/communication/command"', page)
        self.assertIn('formaction="/communication/refresh"', page)
        self.assertIn('formaction="/communication/clear"', page)
        self.assertIn("Clear conversation", page)
        self.assertIn("Refresh devices", page)
        self.assertIn('fetch("/communication/message-revision"', page)
        self.assertIn("var revision = 0;", page)
        self.assertIn("window.location.reload()", page)
        self.assertIn("Discover", page)
        self.assertIn('action="/communication/toggle"', page)
        self.assertIn("Disable", page)
        self.assertLess(page.index("<dt>Board ID</dt>"), page.index("Devices found"))

    def test_messaging_owns_settings_and_device_operations(self):
        page = device_page(
            "192.168.1.20",
            page="messages",
            node_name="nodes-a1b2",
            communication_group_name="workshop",
            communication_enabled=True,
            peers=[{"name": "peer-one", "ip": "192.168.1.21"}],
        )

        self.assertIn("<h1>Messages</h1>", page)
        self.assertIn("<dt>Group name</dt><dd>workshop</dd>", page)
        self.assertIn('nav-link is-active" href="/messages"', page)
        self.assertIn("Devices found", page)
        self.assertIn("Conversation", page)
        self.assertLess(page.index("Devices found"), page.index("Conversation"))
        self.assertIn('name="peer"', page)
        self.assertIn('placeholder="Write a message"', page)
        self.assertIn(">Send</button>", page)
        self.assertIn('name="command" value="ping">Ping</button>', page)
        self.assertLess(
            page.index('name="command" value="message"'),
            page.index('name="command" value="ping"'),
        )
        self.assertLess(
            page.index('name="command" value="ping"'),
            page.index("Clear conversation"),
        )
        self.assertIn('class="ping-button"', page)
        sent_page = device_page(
            "192.168.1.20",
            page="messages",
            communication_enabled=True,
            peers=[{"name": "peer-one", "ip": "192.168.1.21"}],
            messages=[{
                "direction": "sent",
                "node": "nodes-a1b2",
                "payload": "hello",
            }],
        )
        self.assertIn("<small><span>This Device</span>", sent_page)
        self.assertNotIn("<small>nodes-a1b2</small>", sent_page)
        self.assertNotIn('href="/communication"', page)

    def test_messaging_shows_discovery_state_without_peers(self):
        page = device_page(
            "192.168.1.20",
            page="messages",
            communication_enabled=True,
        )
        self.assertIn("Searching for other boards", page)

    def test_messaging_hides_peers_when_plugin_is_disabled(self):
        page = device_page(
            "192.168.1.20", page="messages", communication_enabled=False
        )
        self.assertNotIn("Devices found", page)
        self.assertNotIn("Searching for other boards", page)
        self.assertNotIn("<dt>Board ID</dt>", page)
        self.assertNotIn("<dt>Group name</dt>", page)
        self.assertIn("Discover", page)
        self.assertIn("Enable", page)

    def test_system_status_belongs_to_overview_only(self):
        overview = device_page(
            "192.168.1.20",
            uptime="12 min",
            temperature="42.0 °C",
        )
        messages = device_page("192.168.1.20", page="messages")
        network = device_page(
            "192.168.1.20",
            page="network",
            uptime="12 min",
            temperature="42.0 °C",
        )

        self.assertIn("System status", overview)
        self.assertIn("12 min", overview)
        self.assertNotIn("System status", messages)
        self.assertNotIn("System status", network)
        self.assertNotIn("12 min", network)

    def test_about_page_contains_project_contact_readme_and_license(self):
        page = device_page("192.168.1.20", page="about")

        self.assertIn("<h1>About</h1>", page)
        self.assertIn('nav-link is-active" href="/about"', page)
        self.assertIn("Raspberry Pi Pico 2 W", page)
        self.assertIn('href="mailto:nodes.ro@proton.me"', page)
        self.assertIn(
            'href="https://github.com/botacatalin/wifi_pico2/blob/main/README.md"',
            page,
        )
        self.assertIn(
            'href="https://github.com/botacatalin/wifi_pico2/blob/main/LICENSE"',
            page,
        )
        self.assertIn(
            "LICENSE GPLv2 - Provided without any warranty</a>", page
        )
        self.assertIn(
            '<p class="license-note">2026 - nodes.ro - Contact: '
            '<a href="mailto:nodes.ro@proton.me">nodes.ro@proton.me</a></p>',
            page,
        )
        self.assertIn(
            '<p class="build-version">Build - 2026.06.31</p>', page
        )
        self.assertNotIn("<strong>Contact</strong>", page)
        self.assertNotIn("Project README", device_page("192.168.1.20"))


class FakePeerNetwork:
    instances = []

    def __init__(self, **options):
        self.options = options
        self.closed = False
        self.messages = []
        self.__class__.instances.append(self)

    def close(self):
        self.closed = True

    def update(self):
        pass

    def available_peers(self):
        return []

    def recent_messages(self):
        return self.messages

    def clear_messages(self):
        self.messages = []

    def send_command(self, peer_name, command, payload):
        return True, "reply"


def failing_peer_network(**unused_options):
    raise OSError("port unavailable")


class FakeDatagramSocket:
    def __init__(self, incoming=None):
        self.incoming = list(incoming or [])
        self.sent = []
        self.closed = False

    def setsockopt(self, unused_level, unused_option, unused_value):
        pass

    def bind(self, unused_address):
        pass

    def setblocking(self, unused_enabled):
        pass

    def recvfrom(self, unused_size):
        if not self.incoming:
            raise OSError("no packet")
        return self.incoming.pop(0)

    def sendto(self, data, address):
        self.sent.append((data, address))

    def close(self):
        self.closed = True


class UnreachableBroadcastSocket(FakeDatagramSocket):
    def sendto(self, unused_data, unused_address):
        raise OSError(113)


class FailingStateStore:
    def __init__(self, enabled):
        self.enabled = enabled

    def load(self, unused_default=False):
        return self.enabled

    def save(self, unused_enabled):
        return False


class CommunicationPluginTests(unittest.TestCase):
    def setUp(self):
        FakePeerNetwork.instances = []

    def test_enabled_state_is_persisted_and_controls_network_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PluginStateStore(
                os.path.join(directory, "state.json"),
                os.path.join(directory, "state.tmp"),
                logger=lambda unused: None,
            )
            plugin = CommunicationPlugin(
                "nodes-a1b2",
                "workshop",
                state_store=store,
                network_factory=FakePeerNetwork,
            )

            self.assertFalse(plugin.enabled)
            self.assertEqual(FakePeerNetwork.instances, [])
            self.assertTrue(plugin.set_enabled(True))
            self.assertTrue(plugin.enabled)
            self.assertEqual(store.load(), True)
            self.assertEqual(FakePeerNetwork.instances, [])
            self.assertTrue(plugin.set_network_ready(True))

            network = FakePeerNetwork.instances[0]
            self.assertTrue(plugin.set_enabled(False))
            self.assertTrue(network.closed)
            self.assertFalse(store.load(True))

    def test_builtin_commands_return_correlated_results(self):
        network = PeerNetwork.__new__(PeerNetwork)
        network.node_name = "nodes-a1b2"
        network.messages = []
        network.message_revision = 0
        network.max_payload_bytes = 160

        self.assertEqual(
            network._execute_request("nodes-c3d4", "ping", ""),
            (True, "Ping ACK from nodes-a1b2."),
        )
        self.assertEqual(
            network._execute_request("nodes-c3d4", "message", "hello"),
            (True, "hello"),
        )
        recent_messages = network.recent_messages()[-2:]
        self.assertTrue(all("created_at_ms" in message for message in recent_messages))
        self.assertEqual(
            [{key: value for key, value in message.items() if key != "created_at_ms"}
             for message in recent_messages],
            [
                {
                    "direction": "received",
                    "node": "nodes-c3d4",
                    "payload": "hello",
                },
                {
                    "direction": "sent",
                    "node": "nodes-c3d4",
                    "payload": "hello",
                },
            ],
        )
        self.assertEqual(
            network._execute_request("nodes-c3d4", "unknown", ""),
            (False, "Unsupported command."),
        )

    def test_discovery_uses_configured_broadcast_address(self):
        udp_socket = FakeDatagramSocket()
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            broadcast_address=lambda: "192.168.7.255",
            udp_socket=udp_socket,
        )

        self.assertTrue(network.discover())
        self.assertEqual(udp_socket.sent[0][1], ("192.168.7.255", 4242))

    def test_unreachable_broadcast_waits_for_next_discovery_interval(self):
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            discovery_interval_ms=5000,
            udp_socket=UnreachableBroadcastSocket(),
        )

        self.assertFalse(network.discover())
        first_attempt = network.last_discovery_at
        network.update()
        self.assertEqual(network.last_discovery_at, first_attempt)

    def test_failed_disable_save_does_not_start_network_before_lan_ready(self):
        plugin = CommunicationPlugin(
            "nodes-a1b2",
            "workshop",
            state_store=FailingStateStore(enabled=True),
            network_factory=FakePeerNetwork,
        )

        self.assertFalse(plugin.set_enabled(False))
        self.assertTrue(plugin.enabled)
        self.assertEqual(FakePeerNetwork.instances, [])

    def test_saved_enabled_state_does_not_break_startup_if_socket_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PluginStateStore(
                os.path.join(directory, "state.json"),
                os.path.join(directory, "state.tmp"),
                logger=lambda unused: None,
            )
            self.assertTrue(store.save(True))

            plugin = CommunicationPlugin(
                "nodes-a1b2",
                "workshop",
                state_store=store,
                network_factory=failing_peer_network,
                logger=lambda unused: None,
            )

            self.assertTrue(plugin.enabled)
            self.assertFalse(plugin.set_network_ready(True))
            self.assertFalse(plugin.enabled)
            self.assertFalse(store.load(True))

    def test_plugin_owns_outbound_command_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PluginStateStore(
                os.path.join(directory, "state.json"),
                os.path.join(directory, "state.tmp"),
                logger=lambda unused: None,
            )
            plugin = CommunicationPlugin(
                "nodes-a1b2",
                "workshop",
                state_store=store,
                network_factory=FakePeerNetwork,
                max_payload_bytes=5,
            )
            self.assertTrue(plugin.set_enabled(True))
            self.assertTrue(plugin.set_network_ready(True))

            self.assertEqual(
                plugin.send_command("peer", "unknown", ""),
                (False, "Unsupported command."),
            )
            self.assertEqual(
                plugin.send_command("peer", "message", "123456"),
                (False, "The command payload is too long."),
            )

    def test_udp_command_packet_dispatches_and_preserves_reply_id(self):
        packet = (
            b'{"message_type":"message","kind":"request",'
            b'"request_id":"request-7",'
            b'"node_name":"peer-one","payload":"hello",'
            b'"group_name":"workshop"}'
        )
        udp_socket = FakeDatagramSocket([
            (packet, ("192.168.1.21", 4242)),
        ])
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            udp_socket=udp_socket,
        )

        network._receive_one()

        recent_messages = network.recent_messages()[-2:]
        self.assertTrue(all("created_at_ms" in message for message in recent_messages))
        self.assertEqual([
            {key: value for key, value in message.items() if key != "created_at_ms"}
            for message in recent_messages
        ], [
            {"direction": "received", "node": "peer-one", "payload": "hello"},
            {"direction": "sent", "node": "peer-one", "payload": "hello"},
        ])
        reply = udp_socket.sent[0][0].decode("utf-8")
        self.assertIn('"message_type": "message"', reply)
        self.assertIn('"request_id": "request-7"', reply)
        self.assertIn('"kind": "reply"', reply)
        self.assertNotIn('"reply":', reply)
        self.assertIn('"payload": "hello"', reply)
        self.assertNotIn('"result"', reply)

    def test_two_nodes_discover_each_other_through_hello_reply(self):
        hello = (
            b'{"message_type":"hello","node_name":"node-b",'
            b'"group_name":"workshop"}'
        )
        socket_a = FakeDatagramSocket([
            (hello, ("192.168.1.22", 4242)),
        ])
        node_a = PeerNetwork("node-a", "workshop", udp_socket=socket_a)

        node_a._receive_one()
        reply, unused_address = socket_a.sent[0]

        socket_b = FakeDatagramSocket([
            (reply, ("192.168.1.21", 4242)),
        ])
        node_b = PeerNetwork("node-b", "workshop", udp_socket=socket_b)
        node_b._receive_one()

        self.assertEqual(
            node_a.available_peers(),
            [{"name": "node-b", "ip": "192.168.1.22"}],
        )
        self.assertEqual(
            node_b.available_peers(),
            [{"name": "node-a", "ip": "192.168.1.21"}],
        )

    def test_udp_sender_matches_reply_to_its_request(self):
        udp_socket = FakeDatagramSocket()
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            udp_socket=udp_socket,
        )
        request_id = "nodes-a1b2-%d-1" % network.session_id
        wrong_reply = (
            '{"message_type":"ping","kind":"reply",'
            '"request_id":"%s","node_name":"other-peer",'
            '"payload":"wrong","group_name":"workshop"}' % request_id
        ).encode("utf-8")
        reply = (
            '{"message_type":"ping","kind":"reply",'
            '"request_id":"%s","node_name":"peer-one",'
            '"payload":"accepted","group_name":"workshop"}' % request_id
        ).encode("utf-8")
        udp_socket.incoming.extend([
            (wrong_reply, ("192.168.1.99", 4242)),
            (reply, ("192.168.1.21", 4242)),
        ])
        network.peers["peer-one"] = {
            "address": ("192.168.1.21", 4242),
            "last_seen": time.ticks_ms(),
        }

        self.assertEqual(
            network.send_command("peer-one", "ping"),
            (True, "accepted"),
        )
        recent_messages = network.recent_messages()[-2:]
        self.assertTrue(all("created_at_ms" in message for message in recent_messages))
        self.assertEqual([
            {key: value for key, value in message.items() if key != "created_at_ms"}
            for message in recent_messages
        ], [
            {"direction": "sent", "node": "peer-one", "payload": "Ping"},
            {"direction": "received", "node": "peer-one", "payload": "accepted"},
        ])
        request = udp_socket.sent[0][0].decode("utf-8")
        self.assertIn('"message_type": "ping"', request)
        self.assertIn('"kind": "request"', request)
        self.assertNotIn('"command"', request)
        self.assertIn('"request_id": "%s"' % request_id, request)

    def test_unknown_packet_does_not_create_discovered_peer(self):
        packet = (
            b'{"message_type":"unknown","node_name":"peer-one",'
            b'"group_name":"workshop"}'
        )
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            udp_socket=FakeDatagramSocket([
                (packet, ("192.168.1.21", 4242)),
            ]),
        )

        self.assertIsNone(network._receive_one())
        self.assertEqual(network.available_peers(), [])

    def test_command_retries_with_same_request_id_until_timeout(self):
        udp_socket = FakeDatagramSocket()
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            reply_timeout_ms=45,
            command_retry_interval_ms=10,
            udp_socket=udp_socket,
        )
        network.peers["peer-one"] = {
            "address": ("192.168.1.21", 4242),
            "last_seen": time.ticks_ms(),
        }

        ok, unused_result = network.send_command("peer-one", "ping")

        self.assertFalse(ok)
        self.assertGreaterEqual(len(udp_socket.sent), 2)
        request_ids = []
        for data, unused_address in udp_socket.sent:
            request_ids.append(
                data.decode("utf-8")
                .split('"request_id": "', 1)[1]
                .split('"', 1)[0]
            )
        self.assertEqual(len(set(request_ids)), 1)

    def test_command_attempt_gives_peer_a_fresh_expiry_window(self):
        udp_socket = FakeDatagramSocket()
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            peer_expiry_ms=1000,
            reply_timeout_ms=10,
            command_retry_interval_ms=5,
            udp_socket=udp_socket,
        )
        network.peers["peer-one"] = {
            "address": ("192.168.1.21", 4242),
            "last_seen": time.ticks_add(time.ticks_ms(), -2000),
        }

        self.assertFalse(network.send_command("peer-one", "ping")[0])
        network._expire_peers(time.ticks_ms())
        self.assertIn("peer-one", network.peers)

    def test_duplicate_command_reuses_reply_without_reexecution(self):
        packet = (
            b'{"message_type":"message","kind":"request",'
            b'"request_id":"request-7",'
            b'"node_name":"peer-one","payload":"hello",'
            b'"group_name":"workshop"}'
        )
        udp_socket = FakeDatagramSocket([
            (packet, ("192.168.1.21", 4242)),
            (packet, ("192.168.1.21", 4242)),
        ])
        network = PeerNetwork(
            "nodes-a1b2",
            "workshop",
            udp_socket=udp_socket,
        )
        executions = []
        network._execute_request = lambda node, message_type, payload: (
            executions.append((node, message_type, payload)) or (True, "accepted")
        )

        network._receive_one()
        network._receive_one()

        self.assertEqual(executions, [("peer-one", "message", "hello")])
        self.assertEqual(len(udp_socket.sent), 2)



if __name__ == "__main__":
    unittest.main()
