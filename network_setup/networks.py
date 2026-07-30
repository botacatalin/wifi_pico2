"""Helpers for presenting scanned Wi-Fi networks."""


def format_signal(rssi):
    if rssi >= -50:
        return "Excellent"
    if rssi >= -60:
        return "Good"
    if rssi >= -70:
        return "Fair"
    if rssi >= -80:
        return "Weak"
    return "Very Weak"


def sort_networks(networks):
    return sorted(networks, key=lambda item: item[1], reverse=True)
