"""Persistent Wi-Fi credential storage for MicroPython."""

import json
import os

class CredentialStore:
    def __init__(
        self,
        path="wifi_credentials.json",
        temporary_path="wifi_credentials.tmp",
        logger=print,
    ):
        self.path = path
        self.temporary_path = temporary_path
        self.log = logger

    def load(self):
        try:
            with open(self.path, "r") as file:
                data = json.load(file)
        except OSError:
            return None
        except Exception as exc:
            self.log("Could not load saved Wi-Fi credentials: %s" % exc)
            return None

        if not isinstance(data, dict):
            return None

        ssid = data.get("ssid", "")
        password = data.get("password", "")

        if not isinstance(ssid, str) or not ssid:
            return None

        if not isinstance(password, str):
            return None

        return {"ssid": ssid, "password": password}

    def save(self, ssid, password):
        if not ssid:
            return False

        try:
            with open(self.temporary_path, "w") as file:
                json.dump({"ssid": ssid, "password": password}, file)

            try:
                os.remove(self.path)
            except OSError:
                pass

            os.rename(self.temporary_path, self.path)
            self.log("Wi-Fi credentials saved for %s." % ssid)
            return True
        except Exception as exc:
            self.log("Could not save Wi-Fi credentials: %s" % exc)
            try:
                os.remove(self.temporary_path)
            except OSError:
                pass
            return False

    def delete(self):
        removed = False

        for filename in (self.path, self.temporary_path):
            try:
                os.remove(filename)
                removed = True
            except OSError:
                pass

        if removed:
            self.log("Saved Wi-Fi credentials removed.")

        return removed
