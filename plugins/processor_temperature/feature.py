"""Read the RP2350 internal processor temperature sensor."""

from shared_web.template import render_template
from plugins.interface import DeviceFeature


class ProcessorTemperatureFeature(DeviceFeature):
    feature_id = "processor-temperature"
    name = "Processor Temperature"
    description = "Read the board processor's internal temperature sensor."
    feature_type = "sensor"
    requires_external_hardware = False
    exposed_fields = ("temperature_c",)

    def __init__(self, sensor=None, critical_temperature_c=85):
        self.critical_temperature_c = critical_temperature_c
        self.sensor = sensor if sensor is not None else self._create_sensor()

    @staticmethod
    def _create_sensor():
        try:
            from machine import ADC
            try:
                return ADC(ADC.CORE_TEMP)
            except AttributeError:
                return ADC(4)
        except Exception:
            return None

    def temperature_c(self):
        if self.sensor is None:
            return None
        try:
            reading = self.sensor.read_u16()
            voltage = reading * 3.3 / 65535
            return 27 - (voltage - 0.706) / 0.001721
        except Exception:
            return None

    def read(self):
        temperature = self.temperature_c()
        return {
            "temperature_c": (
                None if temperature is None else round(temperature, 1)
            )
        }

    def render(self, message=""):
        temperature = self.temperature_c()
        value = "Unavailable" if temperature is None else "%.1f °C" % temperature
        is_critical = temperature is not None and temperature >= self.critical_temperature_c
        return render_template(
            "plugins/processor_temperature/templates/page.html",
            {
                "TEMPERATURE": value,
                "STATE_CLASS": "is-critical" if is_critical else "",
                "TEMPERATURE_LIMIT": self.critical_temperature_c,
            },
        )


def create_feature():
    return ProcessorTemperatureFeature()
