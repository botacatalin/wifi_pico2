"""HTML pages served by the device web server."""

import time

from shared_web.html import html_escape
from shared_web.template import render_template
from shared_web.text import humanize_identifier


_FEATURE_TYPE_LABELS = {
    "sensor": "Sensor",
    "actuator": "Actuator",
    "integration": "Integration",
}


def _humanize_field(field):
    if field == "state":
        return "Status"
    if field.endswith("_c"):
        return "%s (°C)" % humanize_identifier(field[:-2])
    if field.endswith("_percent"):
        return "%s (%%)" % humanize_identifier(field[:-8])
    return humanize_identifier(field)


def _humanize_feature(feature_id):
    words = []
    for word in feature_id.replace("_", "-").split("-"):
        words.append(
            "LED" if word.lower() == "led" else humanize_identifier(word)
        )
    return " ".join(words)


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
    ping_text="Ping",
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
    peer_feature_panels = []
    chat_messages = []
    feature_cards = []
    rendered_at_ms = time.ticks_ms()
    for index, peer in enumerate(peers or []):
        name = html_escape(peer.get("name", ""))
        peer_ip = html_escape(peer.get("ip", ""))
        exposed = []
        for feature in peer.get("features", ()):
            feature_id = html_escape(feature.get("id", ""))
            feature_name = html_escape(
                feature.get("name", "")
                or _humanize_feature(feature.get("id", ""))
            )
            field_labels = feature.get("field_labels", {})
            fields = []
            for field in feature.get("fields", ()):
                label = field_labels.get(field) if isinstance(field_labels, dict) else None
                fields.append(html_escape(label or _humanize_field(field)))
            if feature_id and fields:
                exposed.append(
                    '<form class="peer-feature-action" method="post" action="%s">'
                    '<input type="hidden" name="peer" value="%s">'
                    '<input type="hidden" name="command" value="plugin">'
                    '<input type="hidden" name="operation" value="get">'
                    '<input type="hidden" name="feature_id" value="%s">'
                    '<button type="submit"><strong>%s</strong><small>%s</small></button>'
                    '</form>'
                    % (
                        html_escape(send_command_route),
                        name,
                        feature_id,
                        feature_name,
                        ", ".join(fields),
                    )
                )
        if peer.get("features_truncated"):
            exposed.append("<span>More features available</span>")
        feature_items = (
            "".join(exposed)
            if exposed
            else '<p class="feature-empty">No shared features advertised.</p>'
        )
        peer_feature_panels.append(
            '<div class="shared-features-panel" data-peer-panel="%s"%s>'
            '<p class="panel-intro">Capabilities shared by <strong>%s</strong></p>'
            '<div class="peer-feature-list">%s</div></div>'
            % (
                name,
                "" if index == 0 else " hidden",
                name,
                feature_items,
            )
        )
        peer_cards.append(
            '<article class="peer-card%s" role="option" data-peer-card="%s"%s><label class="peer-selector">'
            '<input form="node-command-form" type="radio" name="peer" '
            'value="%s" data-peer-ip="%s"%s><span class="peer-card-copy">'
            '<strong>%s</strong><small>IP address <code>%s</code></small>'
            '</span></label></article>'
            % (
                " is-selected" if index == 0 else "",
                name,
                ' aria-selected="true"' if index == 0 else ' aria-selected="false"',
                name,
                peer_ip,
                " checked" if index == 0 else "",
                name,
                peer_ip,
            )
        )
    selected_name = ""
    selected_ip = ""
    has_selected_peer = False
    if peers:
        selected_name = html_escape(peers[0].get("name", ""))
        selected_ip = html_escape(peers[0].get("ip", ""))
        has_selected_peer = True
    elif messages:
        for message_record in reversed(messages):
            if message_record.get("node"):
                selected_name = html_escape(message_record.get("node", ""))
                break
    previous_sender = None
    for message_record in messages or []:
        is_sent = message_record.get("direction") == "sent"
        direction = "is-sent" if is_sent else "is-received"
        node = (
            "You"
            if is_sent
            else html_escape(message_record.get("node", ""))
        )
        payload = html_escape(message_record.get("payload", ""))
        created_at_ms = message_record.get("created_at_ms")
        timestamp_html = ""
        if created_at_ms is not None:
            age_ms = max(0, time.ticks_diff(rendered_at_ms, created_at_ms))
            timestamp_html = '<time data-message-age-ms="%d"></time>' % age_ms
        sender_key = (direction, node)
        repeated = sender_key == previous_sender
        previous_sender = sender_key
        meta = (
            '<small><span>%s</span>%s</small>' % (node, timestamp_html)
            if not repeated else '<small class="timestamp-only">%s</small>' % timestamp_html
        )
        chat_messages.append(
            '<div class="chat-row %s%s" data-message-peer="%s">'
            '<div class="chat-message">%s<p>%s</p></div></div>'
            % (direction, " is-consecutive" if repeated else "", html_escape(message_record.get("node", "")), meta, payload)
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
            "PEER_FEATURE_PANELS": "".join(peer_feature_panels),
            "SELECTED_NODE_NAME": selected_name,
            "SELECTED_NODE_IP": selected_ip,
            "COMPOSER_DISABLED": "" if has_selected_peer else "disabled",
            "HAS_MESSAGES": bool(chat_messages),
            "EMPTY_STATE_HIDDEN": "hidden" if chat_messages else "",
            "SHOW_CONVERSATION": bool(peer_cards or chat_messages),
            "CHAT_MESSAGES": "".join(chat_messages),
            "MESSAGE_REVISION": int(message_revision),
            "MESSAGE_REVISION_ROUTE": html_escape(message_revision_route),
            "COMMUNICATION_TOGGLE_ROUTE": html_escape(communication_toggle_route),
            "COMMUNICATION_REFRESH_ROUTE": html_escape(communication_refresh_route),
            "CLEAR_CONVERSATION_ROUTE": html_escape(clear_conversation_route),
            "SEND_COMMAND_ROUTE": html_escape(send_command_route),
            "MAX_PAYLOAD_LENGTH": max_payload_length,
            "PING_TEXT": html_escape(ping_text),
            "HAS_FEATURES": bool(feature_cards),
            "NO_FEATURES": not bool(feature_cards),
            "FEATURE_CARDS": "".join(feature_cards),
            "FEATURE_CONTENT": feature_content,
            "HAS_FEATURE_CONTENT": bool(feature_content),
            "SHOW_FEATURE_INDEX": (
                is_features_page and not bool(feature_content)
            ),
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
