"""Enable/disable lifecycle for the optional communication plugin."""

import json
import os

from peer_communication.peer import PeerNetwork


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
        ("message", "Message"),
        ("ping", "Ping"),
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
        **network_options
    ):
        self.node_name = node_name
        self.group_name = group_name
        self.state_store = state_store or PluginStateStore(logger=logger)
        self.log = logger
        self.network_factory = network_factory
        self.network_options = network_options
        self.max_payload_bytes = max_payload_bytes
        self.network = None
        self.enabled = self.state_store.load(enabled_default)
        self.network_ready = False

    def recent_messages(self):
        if self.network is None:
            return []
        return self.network.recent_messages()

    def message_revision(self):
        if self.network is None:
            return 0
        return self.network.message_revision

    def clear_messages(self):
        if self.network is not None:
            self.network.clear_messages()

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
        if self.enabled and self.network_ready and self.network is not None:
            self.network.update()

    def available_peers(self):
        if not self.enabled or self.network is None:
            return []
        return self.network.available_peers()

    def refresh_devices(self):
        if not self.enabled or self.network is None:
            return False
        return self.network.discover()

    def send_command(self, peer_name, command, payload=""):
        if not self.enabled or self.network is None:
            return False, "The communication plugin is disabled."
        if not peer_name:
            return False, "Please select an available board."
        if not self._supports_command(command):
            return False, "Unsupported command."
        if command == "message" and not payload:
            return False, "Please enter a message."
        if len(payload.encode("utf-8")) > self.max_payload_bytes:
            return False, "The command payload is too long."
        return self.network.send_command(peer_name, command, payload)

    def _supports_command(self, command):
        for value, unused_label in self.COMMANDS:
            if value == command:
                return True
        return False

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
            **self.network_options
        )

    def _stop(self):
        if self.network is None:
            return
        self.network.close()
        self.network = None
