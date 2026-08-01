"""Small runtime metrics collector for the device dashboard."""

import time

class ServerMetrics:

    def __init__(self, critical_temperature_c=85, temperature_reader=None):
        self.critical_temperature_c = critical_temperature_c
        self.temperature_reader = temperature_reader
        self.last_tick = time.ticks_ms()
        self.uptime_ms = 0

    def update(self):
        """Accumulate uptime frequently so the tick counter can safely wrap."""

        current_tick = time.ticks_ms()
        elapsed = time.ticks_diff(
            current_tick,
            self.last_tick,
        )

        if elapsed >= 0:
            self.uptime_ms += elapsed

        self.last_tick = current_tick

    def uptime_text(self):
        total_minutes = self.uptime_ms // 60000
        days = total_minutes // 1440
        hours = (total_minutes % 1440) // 60
        minutes = total_minutes % 60

        if days:
            return "%d d %d h %d min" % (
                days,
                hours,
                minutes,
            )

        if hours:
            return "%d h %d min" % (
                hours,
                minutes,
            )

        return "%d min" % minutes

    def temperature_status(self):
        try:
            temperature = (
                self.temperature_reader()
                if self.temperature_reader is not None else None
            )

            if temperature is None:
                return "Unavailable", ""

            state = (
                "is-critical"
                if temperature >= self.critical_temperature_c
                else ""
            )

            return "%.1f °C" % temperature, state
        except Exception:
            return "Unavailable", ""
