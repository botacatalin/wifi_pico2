"""HTML pages used during Wi-Fi setup."""

from network_setup.networks import format_signal
from shared_web.html import html_escape
from shared_web.template import render_template


TEMPLATE_DIRECTORY = "network_setup/templates/"


def render_setup_template(name, values=None, template_directory=TEMPLATE_DIRECTORY):
    return render_template(
        template_directory + name,
        values,
    )


def provisioning_page(
    networks,
    message="",
    device_name="Pico 2 W",
    template_directory=TEMPLATE_DIRECTORY,
):
    options = []

    for ssid, rssi in networks:
        safe_ssid = html_escape(ssid)
        options.append(
            render_setup_template(
                "network_option.html",
                {
                    "SSID": safe_ssid,
                    "SIGNAL": format_signal(rssi),
                },
                template_directory,
            )
        )

    if not options:
        options.append(render_setup_template(
            "no_network_option.html",
            template_directory=template_directory,
        ))

    return render_setup_template(
        "index.html",
        {
            "TITLE": "%s Setup" % html_escape(device_name),
            "BADGE_TEXT": "Device setup",
            "IS_SETUP": True,
            "IS_PENDING": False,
            "IS_SUCCESS": False,
            "DEVICE_NAME": html_escape(device_name),
            "NETWORK_OPTIONS": "\n".join(options),
            "MESSAGE": html_escape(message),
        },
        template_directory,
    )


def provisioning_success_page(
    ip,
    network_name="",
    device_name="Pico 2 W",
    ap_shutdown_delay_seconds=30,
    template_directory=TEMPLATE_DIRECTORY,
):
    safe_ip = html_escape(ip)
    safe_network_name = html_escape(network_name)

    if safe_network_name:
        connection_text = (
            "The %s connected successfully to <strong>%s</strong>."
            % (html_escape(device_name), safe_network_name)
        )
    else:
        connection_text = (
            "The %s connected successfully." % html_escape(device_name)
        )

    return render_setup_template(
        "index.html",
        {
            "TITLE": "Setup Complete",
            "BADGE_TEXT": "Setup complete",
            "IS_SETUP": False,
            "IS_PENDING": False,
            "IS_SUCCESS": True,
            "CONNECTION_TEXT": connection_text,
            "IP": safe_ip,
            "AP_SHUTDOWN_DELAY_SECONDS": ap_shutdown_delay_seconds,
        },
        template_directory,
    )


def connection_pending_page(
    network_name="",
    setup_ssid="Pico2-Setup",
    setup_ip="192.168.4.1",
    status_route="/connection-status",
    result_route="/connection-result",
    connect_timeout_seconds=12,
    poll_interval_ms=1000,
    request_timeout_ms=16000,
    template_directory=TEMPLATE_DIRECTORY,
):
    selected_network = (
        html_escape(network_name)
        if network_name
        else "the selected Wi-Fi network"
    )

    return render_setup_template(
        "index.html",
        {
            "TITLE": "Connecting to %s" % selected_network,
            "BADGE_TEXT": "Connecting",
            "IS_SETUP": False,
            "IS_PENDING": True,
            "IS_SUCCESS": False,
            "SETUP_SSID": html_escape(setup_ssid),
            "SETUP_IP": html_escape(setup_ip),
            "SELECTED_NETWORK": selected_network,
            "STATUS_ROUTE": html_escape(status_route),
            "RESULT_ROUTE": html_escape(result_route),
            "CONNECT_TIMEOUT_SECONDS": connect_timeout_seconds,
            "POLL_INTERVAL_MS": poll_interval_ms,
            "REQUEST_TIMEOUT_MS": request_timeout_ms,
        },
        template_directory,
    )
