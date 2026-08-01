"""Versioned interface shared by every device feature."""

FEATURE_API_VERSION = 1


class DeviceFeature:
    """MicroPython-friendly base for local sensors and controls."""

    api_version = FEATURE_API_VERSION
    feature_id = ""
    name = ""
    description = ""
    feature_type = "integration"
    requires_external_hardware = False
    exposed_fields = ()
    field_labels = {}

    def render(self, message=""):
        """Return the feature's trusted dashboard HTML fragment."""
        raise NotImplementedError

    def read(self):
        """Return a dictionary whose keys exactly match exposed_fields."""
        raise NotImplementedError

    def handle_action(self, action, form):
        """Handle a local dashboard action; sensors may keep this default."""
        raise ValueError("This feature is read-only.")

    def update(self):
        """Advance optional non-blocking work from the application loop."""

    def close(self):
        """Release optional hardware or network resources at shutdown."""
