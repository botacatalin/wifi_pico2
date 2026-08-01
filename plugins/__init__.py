"""Drop-in dashboard plugins discovered at startup."""

from plugins.manager import FeatureManager
from plugins.interface import DeviceFeature, FEATURE_API_VERSION

__all__ = ("DeviceFeature", "FEATURE_API_VERSION", "FeatureManager")
