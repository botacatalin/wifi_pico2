"""Small, dependency-free loader for device features."""

import os

from plugins.interface import DeviceFeature, FEATURE_API_VERSION


class FeatureManager:
    """Discover and own independent device features stored below one directory."""

    def __init__(self, features=None, directory="plugins", package="plugins", logger=None):
        self.directory = directory
        self.package = package
        self.logger = logger or (lambda message: None)
        self._features = []
        self._by_id = {}

        if features is None:
            self.discover()
        else:
            for feature in features:
                self._register(feature)

    def discover(self):
        try:
            entries = os.listdir(self.directory)
        except OSError as exc:
            self.logger("Could not scan plugins: %s" % exc)
            return

        for folder in sorted(entries):
            if not self._valid_module_name(folder):
                continue
            try:
                module_name = "%s.%s.feature" % (self.package, folder)
                module = __import__(module_name, None, None, ("create_feature",))
                self._register(module.create_feature())
            except Exception as exc:
                self.logger("Feature %s could not be loaded: %s" % (folder, exc))

    def _register(self, feature):
        self._validate_feature(feature)
        self._features.append(feature)
        self._by_id[feature.feature_id] = feature

    def _validate_feature(self, feature):
        if not isinstance(feature, DeviceFeature):
            raise ValueError("Features must inherit DeviceFeature.")
        if feature.api_version != FEATURE_API_VERSION:
            raise ValueError(
                "Unsupported feature API version: %s" % feature.api_version
            )
        if feature.feature_id in self._by_id:
            raise ValueError("Duplicate feature ID: %s" % feature.feature_id)
        if not self._valid_feature_id(feature.feature_id):
            raise ValueError("Invalid feature ID: %s" % feature.feature_id)
        if not feature.name or not feature.description:
            raise ValueError("Feature name and description are required.")
        if feature.feature_type not in ("sensor", "actuator", "integration"):
            raise ValueError("Invalid feature type: %s" % feature.feature_type)
        if not isinstance(feature.requires_external_hardware, bool):
            raise ValueError("Feature hardware requirement must be boolean.")
        if not self._valid_exposed_fields(feature.exposed_fields):
            raise ValueError("Feature exposed_fields must be a non-empty tuple.")
        if getattr(feature.__class__, "render", None) is DeviceFeature.render:
            raise ValueError("Feature must implement render().")
        if getattr(feature.__class__, "read", None) is DeviceFeature.read:
            raise ValueError("Feature must implement read().")

    @staticmethod
    def _valid_exposed_fields(fields):
        if not isinstance(fields, tuple) or not fields:
            return False
        seen = []
        for field in fields:
            if (
                not isinstance(field, str)
                or not FeatureManager._valid_module_name(field)
                or field in seen
            ):
                return False
            seen.append(field)
        return True

    @staticmethod
    def _valid_module_name(name):
        if not name or name.startswith("_") or not (
            "a" <= name[0] <= "z"
        ):
            return False
        for character in name[1:]:
            if not (
                "a" <= character <= "z"
                or "0" <= character <= "9"
                or character == "_"
            ):
                return False
        return True

    @staticmethod
    def _valid_feature_id(feature_id):
        """Keep IDs safe for unencoded URL path segments."""
        if not feature_id:
            return False
        for character in feature_id:
            if not (
                "a" <= character <= "z"
                or "0" <= character <= "9"
                or character == "-"
            ):
                return False
        return True

    def features(self):
        return tuple(self._features)

    def get(self, feature_id):
        return self._by_id.get(feature_id)

    def discovery_manifest(self):
        """Return compact metadata safe to advertise during peer discovery."""
        manifest = []
        for feature in self._features:
            manifest.append({
                "id": feature.feature_id,
                "fields": feature.exposed_fields,
            })
        return manifest

    def read_output(self, feature_id):
        """Return one bounded-command-friendly display value."""
        feature = self.get(feature_id)
        if feature is None:
            return False, "That feature is not installed on this board."
        try:
            value = self._format_reading(
                feature.read(), feature.exposed_fields
            )
        except Exception as exc:
            self.logger("Feature %s read failed: %s" % (feature_id, exc))
            return False, "The feature output could not be read."
        return True, "%s: %s" % (feature.name, value)

    @staticmethod
    def _format_reading(reading, exposed_fields):
        """Normalize feature state and sensor values for bounded peer replies."""
        if not isinstance(reading, dict):
            raise ValueError("Feature read() must return a dictionary.")
        if len(reading) != len(exposed_fields):
            raise ValueError("Feature reading fields do not match metadata.")

        values = []
        for key in exposed_fields:
            if key not in reading:
                raise ValueError("Feature reading fields do not match metadata.")
            value = reading[key]
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                raise ValueError("Feature reading values must be scalar.")
            if isinstance(value, bool):
                value = "true" if value else "false"
            elif value is None:
                value = "unavailable"
            values.append("%s=%s" % (key, value))
        return ", ".join(values)

    def update(self):
        for feature in self._features:
            try:
                feature.update()
            except Exception as exc:
                self.logger("Feature %s update failed: %s" % (feature.feature_id, exc))

    def close(self):
        for feature in self._features:
            try:
                feature.close()
            except Exception as exc:
                self.logger("Feature %s close failed: %s" % (feature.feature_id, exc))
