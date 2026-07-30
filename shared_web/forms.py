"""URL and HTML form decoding helpers."""


def url_decode(value):
    value = value.replace("+", " ")
    output = bytearray()
    index = 0

    while index < len(value):
        if value[index] == "%" and index + 2 < len(value):
            try:
                output.append(int(value[index + 1:index + 3], 16))
                index += 3
                continue
            except ValueError:
                pass

        output.extend(value[index].encode("utf-8"))
        index += 1

    return output.decode("utf-8", "replace")


def parse_form(body):
    """Parse an application/x-www-form-urlencoded request body."""

    result = {}

    if not body:
        return result

    for item in body.split("&"):
        if "=" not in item:
            continue

        key, value = item.split("=", 1)
        result[url_decode(key)] = url_decode(value)

    return result
