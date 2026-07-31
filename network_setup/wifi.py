# network_setup/wifi.py

import network
import time

from network_setup.networks import ipv4_broadcast_address, sort_networks


def wifi_status_name(status):
    """Return a readable name for a CYW43 Wi-Fi status code."""

    return {
        -3: "WRONG PASSWORD",
        -2: "NETWORK NOT FOUND",
        -1: "CONNECTION FAILED",
        0: "IDLE",
        1: "CONNECTING",
        2: "CONNECTED - WAITING FOR IP",
        3: "CONNECTED - IP READY",
    }.get(status, "UNKNOWN")


class WiFi:

    def __init__(
        self,
        ap_ssid="Pico2-Setup",
        ap_ip="192.168.4.1",
        ap_netmask="255.255.255.0",
        ap_gateway=None,
        ap_dns=None,
        ap_open=True,
        ap_password="configureme",
        device_name="Pico 2 W",
        connect_timeout_ms=12000,
        connect_status_grace_ms=1500,
        logger=print,
    ):

        self.ap_ssid = ap_ssid
        self.ap_ip_address = ap_ip
        self.ap_netmask = ap_netmask
        self.ap_gateway = ap_gateway if ap_gateway is not None else ap_ip
        self.ap_dns = ap_dns if ap_dns is not None else ap_ip
        self.ap_open = ap_open
        self.ap_password = ap_password
        self.device_name = device_name
        self.connect_timeout_ms = connect_timeout_ms
        self.connect_status_grace_ms = connect_status_grace_ms
        self.log = logger

        self.ap = network.WLAN(network.AP_IF)
        self.sta = network.WLAN(network.STA_IF)

        self.network_cache = []

    # =====================================================
    # Access Point
    # =====================================================

    def _configure_setup_ap(self):

        if self.ap_open:
            self.ap.config(
                essid=self.ap_ssid,
                security=0,
            )
        else:
            self.ap.config(
                essid=self.ap_ssid,
                password=self.ap_password,
            )

        self.ap.ifconfig(
            (
                self.ap_ip_address,
                self.ap_netmask,
                self.ap_gateway,
                self.ap_dns,
            )
        )

    def start_setup_ap(self):

        self.sta.active(True)
        self.ap.active(True)
        self._configure_setup_ap()

        time.sleep_ms(500)

        self.log("----------------------------------------")
        self.log("%s SETUP MODE" % self.device_name.upper())
        self.log("----------------------------------------")
        self.log("SSID : %s" % self.ap_ssid)
        self.log("IP   : %s" % self.ap_ip_address)
        self.log("URL  : http://%s/" % self.ap_ip_address)
        self.log("----------------------------------------")

    def restore_setup_ap(self):
        """Restart the setup AP after STA changes the shared radio channel."""

        # AP_IF can still report active after STA joins a network even though
        # clients associated on its previous channel can no longer reach it.
        # Cycling AP_IF makes the setup network advertise on the radio's new
        # channel while preserving the established station connection.
        if self.ap.active():
            self.ap.active(False)
            time.sleep_ms(200)

        self.ap.active(True)
        self._configure_setup_ap()
        time.sleep_ms(500)

        self.log("Setup Access Point restored for connection result.")

    def stop_setup_ap(self):

        if self.ap.active():

            self.ap.active(False)

            self.log("Setup Access Point disabled.")

    # =====================================================
    # Information
    # =====================================================

    def ap_ip(self):

        return self.ap.ifconfig()[0]

    def station_ip(self):

        if self.sta.isconnected():
            return self.sta.ifconfig()[0]

        return ""

    def station_broadcast(self):
        """Return the LAN broadcast address when station networking is ready."""

        if not self.sta.isconnected():
            return ""

        ip_address, netmask = self.sta.ifconfig()[:2]
        try:
            return ipv4_broadcast_address(ip_address, netmask)
        except (TypeError, ValueError):
            return ""

    def connected(self):

        return self.sta.isconnected()

    # =====================================================
    # Scan
    # =====================================================

    def scan(self, force=False):

        if self.network_cache and not force:
            return self.network_cache

        self.log("Scanning Wi-Fi...")

        found = {}

        try:

            for record in self.sta.scan():

                raw_ssid = record[0]
                rssi = record[3]

                try:
                    ssid = raw_ssid.decode()

                except Exception:
                    ssid = raw_ssid.decode(
                        "utf-8",
                        "replace"
                    )

                if not ssid:
                    continue

                if ssid not in found:
                    found[ssid] = rssi

                elif rssi > found[ssid]:
                    found[ssid] = rssi

        except Exception as exc:

            self.log("Scan failed: %s" % exc)

        self.network_cache = sort_networks(
            list(found.items())
        )

        self.log(
            "Found %d network(s)"
            % len(self.network_cache)
        )

        return self.network_cache

    # =====================================================
    # Connect
    # =====================================================

    def connect(self, ssid, password):

        if not ssid:

            return (
                False,
                "",
                "Please select a Wi-Fi network."
            )

        try:
            setup_ap_was_active = self.ap.active()

            # A plain disconnect can leave the previous WPA
            # key cached inside the CYW43 driver. Cycling only
            # STA_IF clears that in-memory connection profile.
            try:
                self.sta.disconnect()
            except Exception:
                pass

            self.sta.active(False)
            time.sleep_ms(300)
            self.sta.active(True)
            time.sleep_ms(300)

            if self.sta.isconnected():
                return (
                    False,
                    "",
                    "The previous Wi-Fi session could not be cleared. "
                    "Please restart the device and try again.",
                )

            # Some firmware builds briefly disturb AP_IF when
            # STA_IF is reset. Restore it before authentication
            # so a failed attempt can still return its page.
            if setup_ap_was_active and not self.ap.active():
                self.start_setup_ap()

            self.log("Connecting to %s..." % ssid)

            # Submit the new credentials immediately. A delay
            # here lets the driver reconnect with an old key.
            self.sta.connect(
                ssid,
                password,
            )

            start = time.ticks_ms()
            last_status = None

            while (
                time.ticks_diff(
                    time.ticks_ms(),
                    start
                )
                < self.connect_timeout_ms
            ):

                status = self.sta.status()
                elapsed = time.ticks_diff(
                    time.ticks_ms(),
                    start,
                )

                if status != last_status:
                    self.log(
                        "Wi-Fi status: %s"
                        % wifi_status_name(status)
                    )
                    last_status = status

                if self.sta.isconnected():
                    ip = self.station_ip()
                    if ip and ip != "0.0.0.0":
                        return self._connection_success(
                            ssid,
                            ip,
                            setup_ap_was_active,
                        )

                # The driver can briefly expose the previous
                # attempt's terminal status after connect().
                if elapsed < self.connect_status_grace_ms:
                    time.sleep_ms(250)
                    continue

                if status == network.STAT_WRONG_PASSWORD:

                    return (
                        False,
                        "",
                        "Incorrect Wi-Fi password."
                    )

                if status == network.STAT_NO_AP_FOUND:

                    return (
                        False,
                        "",
                        "Wi-Fi network not found."
                    )

                if status == network.STAT_CONNECT_FAIL:

                    return (
                        False,
                        "",
                        "Connection failed."
                    )

                time.sleep_ms(250)

            final_status = self.sta.status()

            # DHCP may complete between the last polling iteration and the
            # deadline check. Accept that valid LAN address instead of
            # disconnecting an established station as a timeout.
            if self.sta.isconnected():
                ip = self.station_ip()
                if ip and ip != "0.0.0.0":
                    return self._connection_success(
                        ssid,
                        ip,
                        setup_ap_was_active,
                    )

            try:
                self.sta.disconnect()
            except:
                pass

            self.log(
                "Connection timed out with status %s"
                % wifi_status_name(final_status)
            )

            return (
                False,
                "",
                "Connection timed out."
            )

        except Exception as exc:

            return (
                False,
                "",
                str(exc)
            )

        finally:

            password = None

    def _connection_success(self, ssid, ip, setup_ap_was_active):
        if setup_ap_was_active:
            try:
                self.restore_setup_ap()
            except Exception as exc:
                self.log(
                    "Could not restore setup access point: %s"
                    % exc
                )

        self.log("----------------------------------------")
        self.log("CONNECTED")
        self.log("SSID : %s" % ssid)
        self.log("IP   : %s" % ip)
        self.log("----------------------------------------")

        return (
            True,
            ip,
            "Connected successfully."
        )

    # =====================================================
    # Status
    # =====================================================

    def status(self):

        return {

            "connected": self.connected(),

            "ap_ip": self.ap_ip(),

            "station_ip": self.station_ip(),

            "networks": len(
                self.network_cache
            ),
        }

    # =====================================================
    # Refresh
    # =====================================================

    def clear_scan_cache(self):

        self.network_cache = []
