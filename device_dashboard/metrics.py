"""Small runtime metrics collector for the device dashboard."""

import machine
import time

class ServerMetrics:

    def __init__(self, critical_temperature_c=85):
        self.critical_temperature_c = critical_temperature_c
        self.last_tick = time.ticks_ms()
        self.uptime_ms = 0

        try:
            self.temperature_sensor = machine.ADC(
                machine.ADC.CORE_TEMP
            )
        except AttributeError:
            # The RP2350 QFN-60 internal temperature sensor is ADC channel 4.
            try:
                self.temperature_sensor = machine.ADC(4)
            except Exception:
                self.temperature_sensor = None
        except Exception:
            self.temperature_sensor = None

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
        if self.temperature_sensor is None:
            return "Unavailable", ""

        try:
            reading = self.temperature_sensor.read_u16()
            voltage = reading * 3.3 / 65535
            temperature = 27 - (
                voltage - 0.706
            ) / 0.001721

            state = (
                "is-critical"
                if temperature >= self.critical_temperature_c
                else ""
            )

            return "%.1f °C" % temperature, state
        except Exception:
            return "Unavailable", ""
