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


def ipv4_broadcast_address(ip_address, netmask):
    """Return the directed broadcast address for an IPv4 subnet."""

    ip_parts = [int(part) for part in ip_address.split(".")]
    mask_parts = [int(part) for part in netmask.split(".")]
    if len(ip_parts) != 4 or len(mask_parts) != 4:
        raise ValueError("Invalid IPv4 address or netmask")

    broadcast = []
    for ip_part, mask_part in zip(ip_parts, mask_parts):
        if not 0 <= ip_part <= 255 or not 0 <= mask_part <= 255:
            raise ValueError("Invalid IPv4 address or netmask")
        broadcast.append(ip_part | (255 ^ mask_part))
    return ".".join(str(part) for part in broadcast)
