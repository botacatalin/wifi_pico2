"""Application-configured logging."""

from config import DEVICE_NAME


def log(message):
    print("[%s]" % DEVICE_NAME.upper(), message)
