# main.py

import gc
import time

from app import App

from config import (
    AP_DNS,
    AP_GATEWAY,
    AP_IP,
    AP_NETMASK,
    AP_OPEN,
    AP_SSID,
    CONNECT_STATUS_GRACE_MS,
    CONNECT_TIMEOUT_MS,
    DEVICE_NAME,
    HTTP_PORT,
    SERVER_ACCEPT_TIMEOUT_SECONDS,
    SERVER_BIND_IP,
    WIFI_CREDENTIALS_FILE,
    WIFI_CREDENTIALS_TEMP_FILE,
)

from shared_web import create_server
from network_setup import CredentialStore

from utils import log

from network_setup.wifi import WiFi


def connect_with_saved_credentials(wifi, credential_store):
    credentials = credential_store.load()

    if credentials is None:
        log("No saved Wi-Fi credentials.")
        return False, ""

    ssid = credentials["ssid"]
    password = credentials["password"]
    log("Trying saved Wi-Fi network: %s" % ssid)

    connected, ip, message = wifi.connect(ssid, password)
    credentials = None
    password = None
    gc.collect()

    if connected:
        log("Saved Wi-Fi connection succeeded.")
        log("Device page: http://%s/" % ip)
        return True, ssid

    log("Saved Wi-Fi connection failed: %s" % message)
    return False, ssid


def main():

    log("")
    log("========================================")
    log("%s Web Server" % DEVICE_NAME)
    log("========================================")

    wifi = WiFi(
        ap_ssid=AP_SSID,
        ap_ip=AP_IP,
        ap_netmask=AP_NETMASK,
        ap_gateway=AP_GATEWAY,
        ap_dns=AP_DNS,
        ap_open=AP_OPEN,
        device_name=DEVICE_NAME,
        connect_timeout_ms=CONNECT_TIMEOUT_MS,
        connect_status_grace_ms=CONNECT_STATUS_GRACE_MS,
        logger=log,
    )
    credential_store = CredentialStore(
        path=WIFI_CREDENTIALS_FILE,
        temporary_path=WIFI_CREDENTIALS_TEMP_FILE,
        logger=log,
    )

    connected, saved_ssid = connect_with_saved_credentials(
        wifi,
        credential_store,
    )

    if not connected:
        log("Starting Wi-Fi setup mode.")
        wifi.start_setup_ap()
        wifi.scan(force=True)

    app = App(
        wifi=wifi,
        credential_store=credential_store,
        provisioned=connected,
        connected_ssid=saved_ssid if connected else "",
    )

    server = create_server(
        HTTP_PORT,
        SERVER_ACCEPT_TIMEOUT_SECONDS,
        bind_ip=SERVER_BIND_IP,
        logger=log,
    )

    log("Device mode ready." if connected else "Setup mode ready.")

    log(
        "Waiting for browser connections..."
    )

    while True:
        client = None

        try:
            app.update()

            gc.collect()

            client, address = (
                server.accept()
            )

            app.handle_client(
                client,
                address,
            )

        except OSError:
            # Expected server accept timeout.
            continue

        except KeyboardInterrupt:
            log(
                "Stopping server..."
            )

            break

        except Exception as exc:
            log(
                "Main loop error: %s"
                % exc
            )

            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

            time.sleep_ms(100)

    try:
        server.close()
    except Exception:
        pass

    log(
        "Server stopped."
    )


main()
