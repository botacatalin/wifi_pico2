# utils.py

from config import DEVICE_NAME
from shared_web.forms import parse_form, url_decode
from shared_web.html import html_escape

# =========================================================
# HTML Utilities
# =========================================================

# Backward-compatible imports. New code should import these helpers from
# shared_web so this module remains application-specific.


# =========================================================
# Formatting Helpers
# =========================================================

def format_signal(rssi):
    """
    Convert RSSI to a human-friendly description.
    """

    if rssi >= -50:
        return "Excellent"

    if rssi >= -60:
        return "Good"

    if rssi >= -70:
        return "Fair"

    if rssi >= -80:
        return "Weak"

    return "Very Weak"


# =========================================================
# Sorting Helpers
# =========================================================

def sort_networks(networks):
    """
    Sort scanned Wi-Fi networks by signal strength.

    Input:

        [
            ("Home",-63),
            ("Office",-48)
        ]

    Output:

        [
            ("Office",-48),
            ("Home",-63)
        ]
    """

    return sorted(
        networks,
        key=lambda item: item[1],
        reverse=True,
    )


# =========================================================
# Debug Logging
# =========================================================

def log(message):
    """
    Small wrapper around print().

    Makes it easy to redirect logging later.
    """

    print("[%s]" % DEVICE_NAME.upper(), message)
