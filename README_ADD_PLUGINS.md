# Device Feature interface

Install a feature by copying one lowercase package folder into `plugins/`
and restarting the board. No central import, dashboard route, or peer-protocol
change is required.

```text
plugins/
  room_sensor/
    __init__.py
    feature.py
    templates/
      page.html
```

`feature.py` implements the versioned interface and exports one factory:

```python
from plugins import DeviceFeature
from shared_web.template import render_template


class RoomSensor(DeviceFeature):
    feature_id = "room-sensor"
    name = "Room Sensor"
    description = "Reads an attached room sensor."
    feature_type = "sensor"
    requires_external_hardware = True
    exposed_fields = ("temperature_c", "humidity_percent")
    field_labels = {
        "temperature_c": "Temperature (°C)",
        "humidity_percent": "Humidity (%)",
    }

    def read(self):
        return {
            "temperature_c": 23.4,
            "humidity_percent": 48,
        }

    def render(self, message=""):
        values = self.read()
        return render_template(
            "plugins/room_sensor/templates/page.html",
            values,
        )


def create_feature():
    return RoomSensor()
```

Rules:

- Folder names start with a lowercase letter and use lowercase letters,
  numbers, and underscores.
- Features inherit the current `api_version` from `DeviceFeature`; do not
  override it unless implementing a future interface version.
- `feature_id` uses lowercase letters, numbers, and hyphens and is unique.
- `name` and `description` are required human-readable strings.
- `feature_type` is `sensor`, `actuator`, or `integration`.
- `requires_external_hardware` is explicitly `True` or `False`.
- `exposed_fields` is a non-empty tuple of unique lowercase field names.
- `field_labels` is a dictionary that optionally maps exposed fields to
  non-empty human-readable UI labels.
- `read()` returns a dictionary with exactly those fields. Values are strings,
  numbers, booleans, or `None`.
- `render()` returns a trusted HTML fragment and escapes all dynamic text.
- Actuators override `handle_action(action, form)`; the default is read-only.
- Override `update()` only for short, non-blocking work and `close()` only when
  hardware or network resources need cleanup.

The manager validates the feature, lists it under **Device Features**, and
derives its peer-discovery manifest from `feature_id`, `name`,
`exposed_fields`, and `field_labels`. **Nodes** then shows it inside the remote
node's collapsible Shared features section and can query it automatically.
If the complete manifest exceeds the configured UDP packet limit, discovery
advertises as many features as fit and marks the list as truncated.
