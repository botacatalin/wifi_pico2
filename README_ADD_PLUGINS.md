# Device Feature interface

Install a feature by copying one lowercase package folder into `plugins/`
and restarting the board. No central import, dashboard route, or peer-protocol
change is required.

```text
plugins/
  room_sensor/
    __init__.py
    feature.py
    vocabulary.json
    templates/
      page.html
```

Put only the plugin's editable display text in `vocabulary.json`:

```json
{
  "name": "Room Sensor",
  "description": "Reads an attached room sensor.",
  "field_labels": {
    "temperature_c": "Temperature (°C)",
    "humidity_percent": "Humidity (%)"
  }
}
```

These labels are shared with other nodes during UDP discovery. Stable feature
IDs, field keys, hardware flags, operations, and validation stay in Python so
editing display text cannot change behavior or break interoperability.

`feature.py` implements the versioned interface and exports one factory:

```python
from plugins import DeviceFeature, load_vocabulary
from shared_web.template import render_template

VOCABULARY = load_vocabulary("plugins/room_sensor/vocabulary.json")


class RoomSensor(DeviceFeature):
    feature_id = "room-sensor"
    name = VOCABULARY["name"]
    description = VOCABULARY["description"]
    feature_type = "sensor"
    requires_external_hardware = True
    exposed_fields = ("temperature_c", "humidity_percent")
    field_labels = VOCABULARY["field_labels"]
    remote_operations = ("get",)

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
- Each plugin owns a `vocabulary.json` for static display text and field labels;
  changing display text there does not require editing its hardware Python code.
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
- `remote_operations` is a tuple containing `"get"`, with optional `"set"`
  only for features that validate and permit remote mutation.
- `render()` returns a trusted HTML fragment and escapes all dynamic text.
- Actuators override `handle_action(action, form)`; the default is read-only.
- Override `update()` only for short, non-blocking work and `close()` only when
  hardware or network resources need cleanup.

The manager validates the feature, lists it under **Device Features**, and
derives its peer-discovery manifest from `feature_id`, `name`,
`exposed_fields`, `field_labels`, and `remote_operations`. **Nodes** then shows
it inside the remote node's collapsible Shared features section and can query
it automatically with the `plugin`/`get` protocol.
If the complete manifest exceeds the configured UDP packet limit, discovery
advertises as many features as fit and marks the list as truncated.

To allow remote mutation, an actuator explicitly declares it in Python:

```python
remote_operations = ("get", "set")
```

Remote `set` calls are passed to `handle_action("set", parameters)`. Validate
every required field and allowed value before touching hardware. After a
successful update, the manager calls `read()` and returns the validated state
in the structured plugin reply. Sensors should keep the default get-only
behavior.
