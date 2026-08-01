"""Editable text and command vocabulary for peer communication."""

import json


def load_communication_vocabulary(path="peer_communication/vocabulary.json"):
    with open(path, "r") as file:
        vocabulary = json.load(file)
    if not isinstance(vocabulary, dict):
        raise ValueError("Communication vocabulary must be an object.")

    ping = vocabulary.get("ping")
    if not isinstance(ping, dict):
        raise ValueError("Communication vocabulary must define ping.")
    required = ("request_text", "success_text", "reply_template")
    for key in required:
        if not isinstance(ping.get(key), str) or not ping[key]:
            raise ValueError("Ping vocabulary must define %s." % key)
    return vocabulary


VOCABULARY = load_communication_vocabulary()
PING = VOCABULARY["ping"]
