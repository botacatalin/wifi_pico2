"""HTML pages served by the device web server."""

from shared_web.html import html_escape
from shared_web.template import render_template


def device_page(
    ip,
    network_name="",
    message="",
    uptime="0 min",
    temperature="Unavailable",
    temperature_state="",
    page="overview",
    device_name="Pico 2 W",
    background_color="#ECFAEF",
    accent_color="#4F772D",
    temperature_limit=85,
    template_directory="device_dashboard/templates/",
):
    is_network_page = page == "network"

    return render_template(
        template_directory + "index.html",
        {
            "TITLE": html_escape(device_name),
            "BACKGROUND_COLOR": background_color,
            "ACCENT_COLOR": accent_color,
            "IS_DASHBOARD": True,
            "IS_ERROR": False,
            "IS_OVERVIEW": not is_network_page,
            "IS_NETWORK": is_network_page,
            "OVERVIEW_ACTIVE": "is-active" if not is_network_page else "",
            "NETWORK_ACTIVE": "is-active" if is_network_page else "",
            "DEVICE_NAME": html_escape(device_name),
            "NETWORK_NAME": (
                html_escape(network_name) if network_name else "Not saved"
            ),
            "HAS_NETWORK": bool(network_name),
            "IP": html_escape(ip),
            "MESSAGE": html_escape(message),
            "UPTIME": html_escape(uptime),
            "TEMPERATURE": html_escape(temperature),
            "TEMPERATURE_STATE": html_escape(temperature_state),
            "TEMPERATURE_LIMIT": temperature_limit,
        },
    )


def error_page(
    message,
    template_directory="device_dashboard/templates/",
):
    return render_template(
        template_directory + "index.html",
        {
            "TITLE": "Request Error",
            "BACKGROUND_COLOR": "#FFF3F3",
            "ACCENT_COLOR": "#C1121F",
            "IS_DASHBOARD": False,
            "IS_ERROR": True,
            "MESSAGE": html_escape(message),
        },
    )
