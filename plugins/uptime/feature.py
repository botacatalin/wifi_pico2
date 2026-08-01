"""Report how long the node has been running."""

import time

from plugins.interface import DeviceFeature
from shared_web.template import render_template


class UptimeFeature(DeviceFeature):
    feature_id = "uptime"
    name = "Uptime"
    description = "Report how long the node has been online."
    feature_type = "sensor"
    requires_external_hardware = False
    exposed_fields = ("uptime",)
    field_labels = {"uptime": "Online for"}

    def __init__(self, clock_ms=None, ticks_diff=None):
        self.clock_ms = clock_ms or time.ticks_ms
        self.ticks_diff = ticks_diff or time.ticks_diff
        self.last_tick = self.clock_ms()
        self.uptime_ms = 0

    def update(self):
        current_tick = self.clock_ms()
        elapsed = self.ticks_diff(current_tick, self.last_tick)
        if elapsed >= 0:
            self.uptime_ms += elapsed
        self.last_tick = current_tick

    def uptime_text(self):
        self.update()
        total_minutes = self.uptime_ms // 60000
        days = total_minutes // 1440
        hours = (total_minutes % 1440) // 60
        minutes = total_minutes % 60

        if days:
            return "%d d %d h %d min" % (days, hours, minutes)
        if hours:
            return "%d h %d min" % (hours, minutes)
        return "%d min" % minutes

    def read(self):
        return {"uptime": self.uptime_text()}

    def render(self, message=""):
        return render_template(
            "plugins/uptime/templates/page.html",
            {"UPTIME": self.uptime_text()},
        )


def create_feature():
    return UptimeFeature()
