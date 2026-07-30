# utils.py

from config import DEVICE_NAME


# =========================================================
# Debug Logging
# =========================================================

def log(message):
    """
    Small wrapper around print().

    Makes it easy to redirect logging later.
    """

    print("[%s]" % DEVICE_NAME.upper(), message)
