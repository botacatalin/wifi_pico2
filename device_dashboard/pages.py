"""HTML pages served by the device web server."""

import time

from shared_web.html import html_escape
from shared_web.template import render_template


_FEATURE_TYPE_LABELS = {
    "sensor": "Sensor",
    "actuator": "Actuator",
    "integration": "Integration",
}


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
    features=None,
    feature_content="",
    template_directory="device_dashboard/templates/",
):
    is_overview_page = page == "overview"
    is_nodes_page = page == "nodes"
    is_network_page = page == "network"
    is_about_page = page == "about"
    is_features_page = page == "features"
    peer_cards = []
    chat_messages = []
    feature_cards = []
    query_feature_options = []
    query_feature_ids = []
    rendered_at_ms = time.ticks_ms()
    for index, peer in enumerate(peers or []):
        name = html_escape(peer.get("name", ""))
        peer_ip = html_escape(peer.get("ip", ""))
        exposed = []
        for feature in peer.get("features", ()):
            feature_id = html_escape(feature.get("id", ""))
            fields = []
            for field in feature.get("fields", ()):
                fields.append(html_escape(field))
            if feature_id and fields:
                exposed.append(
                    '<span><code>%s</code>: %s</span>'
                    % (feature_id, ", ".join(fields))
                )
                if feature_id not in query_feature_ids:
                    query_feature_ids.append(feature_id)
                    query_feature_options.append(
                        '<option value="%s">%s</option>'
                        % (feature_id, ", ".join(fields))
                    )
        if peer.get("features_truncated"):
            exposed.append("<span>More features available</span>")
        exposed_html = (
            '<small class="peer-features"><b>Shared features</b>%s</small>'
            % "".join(exposed)
            if exposed
            else '<small class="peer-features is-empty">'
            'No shared feature information advertised</small>'
        )
        peer_cards.append(
            '<label class="peer-card"><input type="radio" name="peer" '
            'value="%s"%s><span><strong>%s</strong>'
            '<small>IP address <code>%s</code></small>%s</span></label>'
            % (
                name,
                " checked" if index == 0 else "",
                name,
                peer_ip,
                exposed_html,
            )
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

    for feature in features or []:
        requires_external_hardware = feature.requires_external_hardware
        hardware_label = (
            "External hardware required"
            if requires_external_hardware else "Built-in hardware"
        )
        hardware_class = (
            "is-external" if requires_external_hardware else "is-built-in"
        )
        type_label = _FEATURE_TYPE_LABELS[feature.feature_type]
        feature_cards.append(
            '<a class="resource-link" href="/features/%s">'
            '<span><strong>%s</strong><small>%s</small>'
            '<em class="hardware-badge type-badge">%s</em>'
            '<em class="hardware-badge %s">%s</em></span>'
            '<b aria-hidden="true">&rarr;</b></a>'
            % (
                html_escape(feature.feature_id),
                html_escape(feature.name),
                html_escape(feature.description),
                type_label,
                hardware_class,
                hardware_label,
            )
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
            "IS_NODES": is_nodes_page,
            "IS_NETWORK": is_network_page,
            "IS_ABOUT": is_about_page,
            "IS_FEATURES": is_features_page,
            "OVERVIEW_ACTIVE": "is-active" if is_overview_page else "",
            "NODES_ACTIVE": "is-active" if is_nodes_page else "",
            "NETWORK_ACTIVE": "is-active" if is_network_page else "",
            "ABOUT_ACTIVE": "is-active" if is_about_page else "",
            "FEATURES_ACTIVE": "is-active" if is_features_page else "",
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
            "HAS_FEATURES": bool(feature_cards),
            "NO_FEATURES": not bool(feature_cards),
            "FEATURE_CARDS": "".join(feature_cards),
            "FEATURE_CONTENT": feature_content,
            "HAS_FEATURE_CONTENT": bool(feature_content),
            "SHOW_FEATURE_INDEX": (
                is_features_page and not bool(feature_content)
            ),
            "SHOW_REMOTE_FEATURE_QUERY": bool(peer_cards),
            "QUERY_FEATURE_OPTIONS": "".join(query_feature_options),
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
