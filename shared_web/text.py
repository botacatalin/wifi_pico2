"""Small text-formatting helpers supported by MicroPython."""


def capitalize_first(value):
    """Uppercase the first character using MicroPython-supported operations."""
    value = str(value)
    return value[:1].upper() + value[1:]


def humanize_identifier(value):
    """Turn a lowercase underscore or hyphen identifier into a UI label."""
    words = []
    for word in str(value).replace("-", "_").split("_"):
        if word:
            words.append(capitalize_first(word))
    return " ".join(words)
