"""HTML pages served by the device web server."""

import time

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
    communication_enabled=False,
    node_name="",
    communication_group_name="",
    peers=None,
    messages=None,
    message_revision=0,
    message_revision_route="/communication/message-revision",
    communication_toggle_route="/communication/toggle",
    communication_refresh_route="/communication/refresh",
    clear_conversation_route="/communication/clear",
    send_command_route="/communication/command",
    max_payload_length=160,
    template_directory="device_dashboard/templates/",
):
    is_overview_page = page == "overview"
    is_messages_page = page == "messages"
    is_network_page = page == "network"
    is_about_page = page == "about"
    peer_cards = []
    chat_messages = []
    rendered_at_ms = time.ticks_ms()
    for index, peer in enumerate(peers or []):
        name = html_escape(peer.get("name", ""))
        peer_ip = html_escape(peer.get("ip", ""))
        peer_cards.append(
            '<label class="peer-card"><input type="radio" name="peer" '
            'value="%s"%s><span><strong>%s</strong>'
            '<small>IP address <code>%s</code></small></span></label>'
            % (name, " checked" if index == 0 else "", name, peer_ip)
        )
    for message_record in messages or []:
        is_sent = message_record.get("direction") == "sent"
        direction = "is-sent" if is_sent else "is-received"
        node = (
            "This Device"
            if is_sent
            else html_escape(message_record.get("node", ""))
        )
        payload = html_escape(message_record.get("payload", ""))
        created_at_ms = message_record.get("created_at_ms")
        timestamp_html = ""
        if created_at_ms is not None:
            age_ms = max(0, time.ticks_diff(rendered_at_ms, created_at_ms))
            timestamp_html = '<time data-message-age-ms="%d"></time>' % age_ms
        chat_messages.append(
            '<div class="chat-message %s"><small><span>%s</span>%s</small>'
            '<p>%s</p></div>'
            % (direction, node, timestamp_html, payload)
        )

    return render_template(
        template_directory + "index.html",
        {
            "TITLE": html_escape(device_name),
            "BACKGROUND_COLOR": background_color,
            "ACCENT_COLOR": accent_color,
            "IS_DASHBOARD": True,
            "IS_ERROR": False,
            "IS_OVERVIEW": is_overview_page,
            "IS_MESSAGES": is_messages_page,
            "IS_NETWORK": is_network_page,
            "IS_ABOUT": is_about_page,
            "OVERVIEW_ACTIVE": "is-active" if is_overview_page else "",
            "MESSAGES_ACTIVE": "is-active" if is_messages_page else "",
            "NETWORK_ACTIVE": "is-active" if is_network_page else "",
            "ABOUT_ACTIVE": "is-active" if is_about_page else "",
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
            "NODE_NAME": html_escape(node_name),
            "COMMUNICATION_GROUP_NAME": html_escape(communication_group_name),
            "COMMUNICATION_ENABLED": communication_enabled,
            "COMMUNICATION_DISABLED": not communication_enabled,
            "HAS_PEERS": bool(peer_cards),
            "NO_PEERS": not bool(peer_cards),
            "PEER_CARDS": "".join(peer_cards),
            "HAS_MESSAGES": bool(chat_messages),
            "NO_MESSAGES": not bool(chat_messages),
            "CHAT_MESSAGES": "".join(chat_messages),
            "MESSAGE_REVISION": int(message_revision),
            "MESSAGE_REVISION_ROUTE": html_escape(message_revision_route),
            "COMMUNICATION_TOGGLE_ROUTE": html_escape(communication_toggle_route),
            "COMMUNICATION_REFRESH_ROUTE": html_escape(communication_refresh_route),
            "CLEAR_CONVERSATION_ROUTE": html_escape(clear_conversation_route),
            "SEND_COMMAND_ROUTE": html_escape(send_command_route),
            "MAX_PAYLOAD_LENGTH": max_payload_length,
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
