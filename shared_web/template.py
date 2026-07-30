"""Small file-based template helper for MicroPython."""


def render_template(path, values=None):
    """Render values plus normal and conditional component includes."""

    with open(path, "r") as file:
        content = file.read()

    if values is None:
        values = {}

    output = []
    position = 0
    separator = path.rfind("/")
    directory = path[:separator + 1] if separator >= 0 else ""

    while True:
        start = content.find("{{", position)
        if start < 0:
            output.append(content[position:])
            break

        end = content.find("}}", start + 2)
        if end < 0:
            output.append(content[position:])
            break

        output.append(content[position:start])
        key = content[start + 2:end].strip()

        if key.startswith(">"):
            component = key[1:].strip()
            output.append(
                render_template(directory + component, values)
            )
        elif key.startswith("?") and ">" in key:
            condition, component = key[1:].split(">", 1)
            condition = condition.strip()
            component = component.strip()

            if values.get(condition):
                output.append(
                    render_template(directory + component, values)
                )
        elif key in values:
            value = values[key]
            output.append("" if value is None else str(value))
        else:
            output.append(content[start:end + 2])

        position = end + 2

    return "".join(output)
