import sys
import time
import types
import unittest


if not hasattr(time, "ticks_ms"):
    time.ticks_ms = lambda: int(time.monotonic() * 1000)
if not hasattr(time, "ticks_diff"):
    time.ticks_diff = lambda value, previous: value - previous
if not hasattr(time, "sleep_ms"):
    time.sleep_ms = lambda unused_milliseconds: None


network = types.ModuleType("network")
network.AP_IF = 0
network.STA_IF = 1
network.STAT_WRONG_PASSWORD = -3
network.STAT_NO_AP_FOUND = -2
network.STAT_CONNECT_FAIL = -1
network.STAT_GOT_IP = 3


class FakeWLAN:
    def __init__(self, interface):
        self.interface = interface
        self.active_state = interface == network.AP_IF
        self.connection_checks = 0

    def active(self, enabled=None):
        if enabled is not None:
            self.active_state = bool(enabled)
        return self.active_state

    def config(self, **unused_options):
        pass

    def ifconfig(self, unused_config=None):
        if self.interface == network.STA_IF:
            return ("192.168.1.20", "255.255.255.0", "192.168.1.1", "1.1.1.1")
        return ("192.168.4.1", "255.255.255.0", "192.168.4.1", "192.168.4.1")

    def disconnect(self):
        pass

    def connect(self, unused_ssid, unused_password):
        pass

    def isconnected(self):
        if self.interface != network.STA_IF:
            return False
        self.connection_checks += 1
        return self.connection_checks > 1

    def status(self):
        # Simulate firmware whose status code lags behind its valid DHCP state.
        return 2


network.WLAN = FakeWLAN
sys.modules.setdefault("network", network)

from network_setup.wifi import WiFi


class WiFiConnectionTests(unittest.TestCase):
    def test_valid_station_ip_wins_when_status_code_lags(self):
        wifi = WiFi(logger=lambda unused_message: None)

        connected, ip, message = wifi.connect("Home", "secret")

        self.assertTrue(connected)
        self.assertEqual(ip, "192.168.1.20")
        self.assertEqual(message, "Connected successfully.")


if __name__ == "__main__":
    unittest.main()
