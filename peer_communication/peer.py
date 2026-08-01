"""Bounded UDP discovery and messaging for local Pico boards."""

import json
import socket
import time


def normalize_command(command):
    """Return the canonical lowercase form used on the UDP wire."""

    if not isinstance(command, str):
        return ""
    return command.strip().lower()


def default_node_name(device_name):
    """Create a readable name that is normally unique to this board."""

    try:
        import machine
        import ubinascii

        identifier = ubinascii.hexlify(machine.unique_id()).decode("ascii")
        suffix = identifier[-8:]
    except Exception:
        suffix = "node"

    base = device_name.lower().replace(" ", "-")
    return "%s-%s" % (base, suffix)


class PeerNetwork:
    """Discover peers and exchange short command/reply-style messages."""

    def __init__(
        self,
        node_name,
        group_name,
        port=4242,
        discovery_interval_ms=5000,
        peer_expiry_ms=30000,
        reply_timeout_ms=3000,
        command_retry_interval_ms=500,
        broadcast_address="255.255.255.255",
        max_packet_bytes=512,
        max_payload_bytes=160,
        udp_socket=None,
        request_handler=None,
        feature_catalog_provider=None,
    ):
        self.node_name = node_name
        self.group_name = group_name
        self.port = port
        self.discovery_interval_ms = discovery_interval_ms
        self.peer_expiry_ms = peer_expiry_ms
        self.reply_timeout_ms = reply_timeout_ms
        self.command_retry_interval_ms = command_retry_interval_ms
        self.broadcast_address = broadcast_address
        self.max_packet_bytes = max_packet_bytes
        self.max_payload_bytes = max_payload_bytes
        self.peers = {}
        self.messages = []
        self.message_revision = 0
        self.last_discovery_at = None
        self.session_id = time.ticks_ms()
        self.next_message_id = 1
        self.recent_commands = {}
        self.request_handler = request_handler
        self.feature_catalog_provider = feature_catalog_provider

        self.socket = udp_socket if udp_socket is not None else socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.bind(("0.0.0.0", self.port))
        self.socket.setblocking(False)

    def update(self):
        """Advance discovery and handle a few waiting packets without blocking."""

        now = time.ticks_ms()
        if (
            self.last_discovery_at is None
            or time.ticks_diff(now, self.last_discovery_at)
            >= self.discovery_interval_ms
        ):
            self.discover()

        for unused in range(4):
            if self._receive_one() is None:
                break

        self._expire_peers(now)

    def discover(self):
        """Broadcast this node's presence immediately."""

        self.last_discovery_at = time.ticks_ms()
        address = (
            self.broadcast_address()
            if callable(self.broadcast_address)
            else self.broadcast_address
        )
        if not address:
            return False

        try:
            self._send_discovery(
                (address, self.port),
                "hello",
            )
            return True
        except OSError:
            # The CYW43 stack can temporarily reject a broadcast while the
            # station interface or router route is settling. Retry on the next
            # normal discovery interval instead of flooding the main loop.
            return False

    def available_peers(self):
        """Return stable display records for currently available peers."""

        records = []
        for name in sorted(self.peers):
            record = self.peers[name]
            display_record = {
                "name": name,
                "ip": record["address"][0],
            }
            features = record.get("features", ())
            if features:
                display_record["features"] = features
            if record.get("features_truncated", False):
                display_record["features_truncated"] = True
            records.append(display_record)
        return records

    def send_command(self, peer_name, command, payload=""):
        """Send a command to a discovered peer and wait for its matched reply."""

        command = normalize_command(command)
        if command not in ("message", "ping", "plugin"):
            return False, "Unsupported command."
        if command == "plugin":
            if not isinstance(payload, dict):
                return False, "Plugin request must be an object."
            payload = {
                "feature_id": payload.get("feature_id"),
                "operation": normalize_command(payload.get("operation")),
                "parameters": payload.get("parameters", {}),
            }
            validation_packet = {"kind": "request"}
            validation_packet.update(payload)
            if not self._valid_plugin_packet(validation_packet):
                return False, "Invalid plugin request."
            if len(json.dumps(payload).encode("utf-8")) > self.max_payload_bytes:
                return False, "The command payload is too long."
        elif not isinstance(payload, str):
            return False, "The command payload must be text."
        elif len(payload.encode("utf-8")) > self.max_payload_bytes:
            return False, "The command payload is too long."
        peer = self.peers.get(peer_name)
        if peer is None:
            return False, "That board is no longer available."

        started = time.ticks_ms()
        message_id = "%s-%d-%d" % (
            self.node_name,
            self.session_id,
            self.next_message_id,
        )
        self.next_message_id += 1
        packet = {
            "message_type": command,
            "kind": "request",
            "request_id": message_id,
            "node_name": self.node_name,
        }
        if command == "plugin":
            packet.update(payload)
        else:
            packet["payload"] = payload

        if command == "message":
            display_payload = payload
        elif command == "plugin":
            display_payload = "%s feature: %s" % (
                payload["operation"].capitalize(),
                payload["feature_id"],
            )
        else:
            display_payload = "Ping"
        self._remember_message("sent", peer_name, display_payload)

        # Give a peer selected by the user a full liveness window. A command
        # timeout should not make a device vanish merely because its previous
        # discovery record was already close to expiry.
        peer["last_seen"] = started
        last_sent = None
        while time.ticks_diff(time.ticks_ms(), started) < self.reply_timeout_ms:
            now = time.ticks_ms()
            if (
                last_sent is None
                or time.ticks_diff(now, last_sent)
                >= self.command_retry_interval_ms
            ):
                try:
                    self._send(peer["address"], packet)
                except OSError:
                    # Routes can be temporarily unavailable while CYW43 or the
                    # access point settles. Keep retrying within the bounded
                    # reply window.
                    pass
                last_sent = now

            event = self._receive_one()
            if event is not None:
                packet, address = event
                if (
                    packet.get("message_type") == command
                    and packet.get("kind") in ("reply", "error")
                    and packet.get("request_id") == message_id
                    and packet.get("node_name") == peer_name
                    and address[0] == peer["address"][0]
                    and (
                        command != "plugin"
                        or (
                            packet.get("feature_id") == payload["feature_id"]
                            and packet.get("operation") == payload["operation"]
                        )
                    )
                ):
                    ok = packet.get("kind") == "reply"
                    if command == "plugin":
                        reply_payload = (
                            packet.get("result", {})
                            if ok else packet.get("error", "Plugin request failed.")
                        )
                    else:
                        reply_payload = str(
                            packet.get("payload", "Message received.")
                        )
                    if ok and command == "plugin":
                        self._remember_message(
                            "received", peer_name, json.dumps(reply_payload)
                        )
                    return ok, reply_payload
            time.sleep_ms(20)

        return False, "No reply was received before the timeout."

    def close(self):
        try:
            self.socket.close()
        except Exception:
            pass
        self.peers = {}

    def recent_messages(self):
        return self.messages

    def clear_messages(self):
        if self.messages:
            self.message_revision += 1
        self.messages = []

    def _receive_one(self):
        try:
            data, address = self.socket.recvfrom(self.max_packet_bytes + 1)
        except OSError:
            return None

        if len(data) > self.max_packet_bytes:
            return None

        try:
            packet = json.loads(data.decode("utf-8"))
        except Exception:
            return None

        if not isinstance(packet, dict):
            return None
        if packet.get("group_name") != self.group_name:
            return None

        packet_type = normalize_command(packet.get("message_type"))
        if packet_type not in (
            "hello",
            "hello_reply",
            "message",
            "ping",
            "plugin",
        ):
            return None
        packet["message_type"] = packet_type
        if packet_type in ("message", "ping", "plugin"):
            if packet.get("kind") not in ("request", "reply", "error"):
                return None
            request_id = packet.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                return None
            if packet_type != "plugin" and not isinstance(
                packet.get("payload", ""), str
            ):
                return None
            if packet_type == "plugin" and not self._valid_plugin_packet(packet):
                return None

        node = packet.get("node_name")
        if not isinstance(node, str) or not node or node == self.node_name:
            return packet, address

        previous_peer = self.peers.get(node, {})
        features = previous_peer.get("features", ())
        features_truncated = previous_peer.get(
            "features_truncated", False
        )
        if "features" in packet:
            features = self._validated_features(packet["features"])
            features_truncated = bool(
                packet.get("features_truncated", False)
            )
        self.peers[node] = {
            "address": (address[0], self.port),
            "last_seen": time.ticks_ms(),
            "features": features,
            "features_truncated": features_truncated,
        }

        if packet_type == "hello":
            self._send_discovery(address, "hello_reply")
        elif (
            packet_type in ("message", "ping", "plugin")
            and packet.get("kind") == "request"
        ):
            request_id = packet["request_id"]
            payload = (
                {
                    "feature_id": packet["feature_id"],
                    "operation": packet["operation"],
                    "parameters": packet.get("parameters", {}),
                }
                if packet_type == "plugin"
                else packet.get("payload", "")
            )
            command_key = (node, packet_type, request_id)
            cached = self.recent_commands.get(command_key)
            if cached is None:
                ok, reply_payload = self._execute_request(
                    node, packet_type, payload
                )
                self._remember_command(command_key, ok, reply_payload)
            else:
                ok, reply_payload = cached
            response = {
                "message_type": packet_type,
                "kind": "reply" if ok else "error",
                "request_id": request_id,
                "node_name": self.node_name,
            }
            if packet_type == "plugin":
                response["feature_id"] = payload["feature_id"]
                response["operation"] = payload["operation"]
                response["result" if ok else "error"] = reply_payload
            else:
                response["payload"] = reply_payload
            self._send(address, response)

        return packet, address

    def _remember_command(self, command_key, ok, reply_payload):
        if len(self.recent_commands) >= 8:
            evicted_key = next(iter(self.recent_commands))
            del self.recent_commands[evicted_key]
        self.recent_commands[command_key] = (ok, reply_payload)

    def _execute_request(self, node, message_type, payload):
        message_type = normalize_command(message_type)
        if message_type == "ping":
            reply_payload = "Ping ACK from %s." % self.node_name
            self._remember_message("received", node, "Ping")
            return True, reply_payload
        if (
            message_type == "message"
            and isinstance(payload, str)
            and payload
            and len(payload.encode("utf-8")) <= self.max_payload_bytes
        ):
            self._remember_message("received", node, payload)
            return True, payload
        if self.request_handler is not None:
            try:
                return self.request_handler(message_type, payload)
            except Exception:
                return False, "The command could not be completed."
        return False, "Unsupported command."

    @staticmethod
    def _valid_plugin_packet(packet):
        feature_id = packet.get("feature_id")
        operation = normalize_command(packet.get("operation"))
        kind = packet.get("kind")
        if not isinstance(feature_id, str) or not feature_id:
            return False
        if operation not in ("get", "set"):
            return False
        packet["operation"] = operation
        if kind == "request":
            return isinstance(packet.get("parameters", {}), dict)
        if kind == "reply":
            return isinstance(packet.get("result"), dict)
        return isinstance(packet.get("error"), str)

    def _remember_message(self, direction, node, payload):
        if len(self.messages) >= 8:
            del self.messages[0]
        self.messages.append({
            "direction": direction,
            "node": node,
            "payload": payload,
            "created_at_ms": time.ticks_ms(),
        })
        self.message_revision += 1

    def _send(self, address, packet):
        packet["group_name"] = self.group_name
        data = json.dumps(packet).encode("utf-8")
        if len(data) > self.max_packet_bytes:
            raise ValueError("Peer message is too large.")
        self.socket.sendto(data, address)

    def _send_discovery(self, address, message_type):
        features = []
        if self.feature_catalog_provider is not None:
            try:
                features = list(self.feature_catalog_provider())
            except Exception:
                features = []

        packet = {
            "message_type": normalize_command(message_type),
            "node_name": self.node_name,
            "features": features,
        }
        feature_count = len(features)
        while True:
            packet["features_truncated"] = len(features) < feature_count
            try:
                self._send(address, packet)
                return
            except ValueError:
                if not features:
                    raise
                del features[-1]

    @staticmethod
    def _validated_features(features):
        records = []
        if not isinstance(features, list):
            return records
        for feature in features:
            if not isinstance(feature, dict):
                continue
            feature_id = feature.get("id")
            feature_name = feature.get("name")
            fields = feature.get("fields")
            if not isinstance(feature_id, str) or not feature_id:
                continue
            if not isinstance(fields, (list, tuple)) or not fields:
                continue
            if not isinstance(feature_name, str) or not feature_name:
                feature_name = feature_id
            labels = feature.get("field_labels", {})
            if not isinstance(labels, dict):
                labels = {}
            valid_fields = []
            valid_labels = {}
            operations = feature.get("operations", ("get",))
            valid_operations = []
            if isinstance(operations, (list, tuple)):
                for operation in operations:
                    operation = normalize_command(operation)
                    if operation in ("get", "set") and operation not in valid_operations:
                        valid_operations.append(operation)
            for field in fields:
                if isinstance(field, str) and field:
                    valid_fields.append(field)
                    label = labels.get(field)
                    if isinstance(label, str) and label:
                        valid_labels[field] = label
            if valid_fields:
                if "get" not in valid_operations:
                    valid_operations.insert(0, "get")
                records.append({
                    "id": feature_id,
                    "name": feature_name,
                    "fields": valid_fields,
                    "field_labels": valid_labels,
                    "operations": valid_operations,
                })
        return records

    def _expire_peers(self, now):
        expired = []
        for name, record in self.peers.items():
            if time.ticks_diff(now, record["last_seen"]) >= self.peer_expiry_ms:
                expired.append(name)
        for name in expired:
            del self.peers[name]
