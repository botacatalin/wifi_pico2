"""Enable/disable lifecycle for the optional communication plugin."""

import json
import os

from peer_communication.peer import PeerNetwork, normalize_command


class PluginStateStore:
    """Persist the enabled flag with an atomic temporary-file update."""

    def __init__(
        self,
        path="communication_plugin.json",
        temporary_path="communication_plugin.tmp",
        logger=print,
    ):
        self.path = path
        self.temporary_path = temporary_path
        self.log = logger

    def load(self, default=False):
        try:
            with open(self.path, "r") as file:
                data = json.load(file)
        except OSError:
            return bool(default)
        except Exception as exc:
            self.log("Could not load communication plugin state: %s" % exc)
            return bool(default)

        if not isinstance(data, dict) or not isinstance(data.get("enabled"), bool):
            return bool(default)
        return data["enabled"]

    def save(self, enabled):
        try:
            with open(self.temporary_path, "w") as file:
                json.dump({"enabled": bool(enabled)}, file)
            try:
                os.remove(self.path)
            except OSError:
                pass
            os.rename(self.temporary_path, self.path)
            return True
        except Exception as exc:
            self.log("Could not save communication plugin state: %s" % exc)
            try:
                os.remove(self.temporary_path)
            except OSError:
                pass
            return False


class CommunicationPlugin:
    """Optional discovery and command/reply service used by App."""

    COMMANDS = (
        "message",
        "ping",
        "plugin",
    )

    def __init__(
        self,
        node_name,
        group_name,
        state_store=None,
        enabled_default=False,
        max_payload_bytes=160,
        logger=print,
        network_factory=PeerNetwork,
        feature_handler=None,
        feature_catalog_provider=None,
        **network_options
    ):
        self.node_name = node_name
        self.group_name = group_name
        self.state_store = state_store or PluginStateStore(logger=logger)
        self.log = logger
        self.network_factory = network_factory
        self.network_options = network_options
        self.max_payload_bytes = max_payload_bytes
        self.feature_handler = feature_handler
        self.feature_catalog_provider = feature_catalog_provider
        self.network = None
        self.enabled = self.state_store.load(enabled_default)
        self.network_ready = False

    def recent_messages(self):
        network = self._active_network()
        if network is None:
            return []
        return network.recent_messages()

    def message_revision(self):
        network = self._active_network()
        if network is None:
            return 0
        return network.message_revision

    def clear_messages(self):
        network = self._active_network()
        if network is not None:
            network.clear_messages()

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.enabled:
            return True

        if enabled:
            if self.network_ready:
                try:
                    self._start()
                except Exception as exc:
                    self.log("Could not enable communication plugin: %s" % exc)
                    return False
        else:
            self._stop()

        if not self.state_store.save(enabled):
            if enabled:
                self._stop()
            elif self.network_ready:
                try:
                    self._start()
                except Exception:
                    pass
            return False

        self.enabled = enabled
        return True

    def set_network_ready(self, ready):
        """Start networking only when the station has a usable LAN connection."""

        ready = bool(ready)
        if ready == self.network_ready:
            return True

        if ready and self.enabled:
            try:
                self._start()
            except Exception as exc:
                self.log("Communication plugin could not start: %s" % exc)
                self.enabled = False
                self.state_store.save(False)
                return False
        elif not ready:
            self._stop()

        self.network_ready = ready
        return True

    def update(self):
        network = self._active_network()
        if network is not None:
            network.update()

    def available_peers(self):
        network = self._active_network()
        if network is None:
            return []
        return network.available_peers()

    def refresh_devices(self):
        network = self._active_network()
        if network is None:
            return False
        return network.discover()

    def send_command(self, peer_name, command, payload=""):
        network = self._active_network()
        if network is None:
            return False, "The communication plugin is disabled."
        if not peer_name:
            return False, "Please select an available board."
        command = normalize_command(command)
        if command not in self.COMMANDS:
            return False, "Unsupported command."
        if command == "message" and not payload:
            return False, "Please enter a message."
        if command == "plugin":
            valid, error = self._validate_plugin_request(payload)
            if not valid:
                return False, error
        elif not isinstance(payload, str):
            return False, "The command payload must be text."
        encoded_payload = (
            json.dumps(payload).encode("utf-8")
            if command == "plugin" else payload.encode("utf-8")
        )
        if len(encoded_payload) > self.max_payload_bytes:
            return False, "The command payload is too long."
        return network.send_command(peer_name, command, payload)

    def close(self):
        """Release runtime resources without changing the persisted setting."""

        self._stop()

    def _start(self):
        if self.network is not None:
            return
        self.network = self.network_factory(
            node_name=self.node_name,
            group_name=self.group_name,
            max_payload_bytes=self.max_payload_bytes,
            request_handler=self._handle_request,
            feature_catalog_provider=self.feature_catalog_provider,
            **self.network_options
        )

    def _handle_request(self, message_type, payload):
        if message_type != "plugin" or self.feature_handler is None:
            return False, "Unsupported command."
        valid, error = self._validate_plugin_request(payload)
        if not valid:
            return False, error
        ok, reply = self.feature_handler(
            payload["feature_id"],
            payload["operation"],
            payload["parameters"],
        )
        if ok and not isinstance(reply, dict):
            return False, "The plugin result must be an object."
        if len(json.dumps(reply).encode("utf-8")) > self.max_payload_bytes:
            return False, "The feature output is too long."
        return bool(ok), reply

    @staticmethod
    def _validate_plugin_request(payload):
        if not isinstance(payload, dict):
            return False, "Plugin request must be an object."
        feature_id = payload.get("feature_id")
        operation = normalize_command(payload.get("operation"))
        parameters = payload.get("parameters", {})
        if not isinstance(feature_id, str) or not feature_id:
            return False, "Please select a feature."
        if operation not in ("get", "set"):
            return False, "Unsupported plugin operation."
        if not isinstance(parameters, dict):
            return False, "Plugin parameters must be an object."
        payload["operation"] = operation
        payload["parameters"] = parameters
        return True, ""

    def _active_network(self):
        """Return the peer transport only while all network gates are open."""

        if not self.enabled or not self.network_ready:
            return None
        return self.network

    def _stop(self):
        if self.network is None:
            return
        self.network.close()
        self.network = None
