"""Dashboard control for the Pico 2 W onboard LED."""

from shared_web.template import render_template
from shared_web.html import html_escape
from plugins.interface import DeviceFeature


class OnboardLedFeature(DeviceFeature):
    feature_id = "onboard-led"
    name = "Onboard LED"
    description = "Switch the board's built-in LED on or off."
    feature_type = "actuator"
    requires_external_hardware = False
    exposed_fields = ("state",)

    def __init__(self, pin=None):
        if pin is None:
            from machine import Pin
            pin = Pin("LED", Pin.OUT)
        self.pin = pin

    def is_on(self):
        return bool(self.pin.value())

    def read(self):
        return {"state": "on" if self.is_on() else "off"}

    def handle_action(self, action, form):
        if action != "set":
            raise ValueError("Unknown LED action.")
        turn_on = form.get("state") == "on"
        self.pin.value(1 if turn_on else 0)
        return "The onboard LED is now %s." % ("on" if turn_on else "off")

    def render(self, message=""):
        is_on = self.is_on()
        return render_template(
            "plugins/onboard_led/templates/page.html",
            {
                "MESSAGE": html_escape(message),
                "STATE": "On" if is_on else "Off",
                "STATE_CLASS": "is-on" if is_on else "is-off",
                "NEXT_STATE": "off" if is_on else "on",
                "BUTTON_LABEL": "Turn LED off" if is_on else "Turn LED on",
            },
        )


def create_feature():
    return OnboardLedFeature()
