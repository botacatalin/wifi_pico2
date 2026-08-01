"""Versioned interface shared by every device feature."""

import json

FEATURE_API_VERSION = 1


def load_vocabulary(path):
    """Load the small, editable vocabulary owned by one feature plugin."""
    with open(path, "r") as file:
        vocabulary = json.load(file)
    if not isinstance(vocabulary, dict):
        raise ValueError("Feature vocabulary must be an object.")

    labels = vocabulary.get("field_labels")
    if not isinstance(labels, dict):
        raise ValueError("Feature vocabulary must define field labels.")

    return {
        "name": vocabulary.get("name"),
        "description": vocabulary.get("description"),
        "field_labels": labels,
    }


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
    remote_operations = ("get",)

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
