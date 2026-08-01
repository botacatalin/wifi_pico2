"""Dashboard control for the Pico 2 W onboard LED."""

from shared_web.template import render_template
from shared_web.html import html_escape
from plugins.interface import DeviceFeature, load_vocabulary


VOCABULARY = load_vocabulary("plugins/onboard_led/vocabulary.json")


class OnboardLedFeature(DeviceFeature):
    feature_id = "onboard-led"
    name = VOCABULARY["name"]
    description = VOCABULARY["description"]
    feature_type = "actuator"
    requires_external_hardware = False
    exposed_fields = ("state",)
    field_labels = VOCABULARY["field_labels"]
    remote_operations = ("get", "set")

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
        state = form.get("state")
        if state not in ("on", "off"):
            raise ValueError("LED state must be on or off.")
        turn_on = state == "on"
        self.pin.value(1 if turn_on else 0)
        return "The onboard LED is now %s." % ("on" if turn_on else "off")

    def render(self, message=""):
        is_on = self.is_on()
        return render_template(
            "plugins/onboard_led/templates/page.html",
            {
                "MESSAGE": html_escape(message),
                "STATE": "ON" if is_on else "OFF",
                "NEXT_STATE": "off" if is_on else "on",
                "BUTTON_LABEL": "OFF" if is_on else "ON",
                "BUTTON_CLASS": "is-off" if is_on else "is-on",
                "BUTTON_TOOLTIP": "Turn OFF" if is_on else "Turn ON",
            },
        )


def create_feature():
    return OnboardLedFeature()
