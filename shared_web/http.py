# shared_web/http.py

import socket


DEFAULT_BIND_IP = "0.0.0.0"
DEFAULT_MAX_HEADER_BYTES = 4096
DEFAULT_MAX_BODY_BYTES = 2048


# =========================================================
# HTTP Request
# =========================================================

class HttpRequest:

    def __init__(
        self,
        method,
        path,
        headers,
        body,
    ):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body


# =========================================================
# Request Parsing
# =========================================================

def read_request(
    client,
    max_header_bytes=DEFAULT_MAX_HEADER_BYTES,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
):
    """
    Read and parse a complete HTTP request.

    Returns:

        HttpRequest(
            method,
            path,
            headers,
            body
        )
    """

    raw = bytearray()

    # Read until all HTTP headers have arrived.
    while b"\r\n\r\n" not in raw:

        chunk = client.recv(512)

        if not chunk:
            break

        raw.extend(chunk)

        if len(raw) > max_header_bytes:
            raise ValueError(
                "HTTP headers are too large."
            )

    header_end = raw.find(b"\r\n\r\n")

    if header_end < 0:
        raise ValueError(
            "Incomplete HTTP request."
        )

    header_data = bytes(
        raw[:header_end]
    )

    body_data = bytearray(
        raw[header_end + 4:]
    )

    header_lines = header_data.split(
        b"\r\n"
    )

    if not header_lines:
        raise ValueError(
            "Missing HTTP request line."
        )

    request_line = header_lines[0].decode(
        "latin-1"
    )

    request_parts = request_line.split(" ")

    if len(request_parts) < 2:
        raise ValueError(
            "Invalid HTTP request line."
        )

    method = request_parts[0].upper()

    raw_path = request_parts[1]

    # Ignore URL query parameters for routing.
    path = raw_path.split("?", 1)[0]

    headers = {}

    for line in header_lines[1:]:

        if b":" not in line:
            continue

        name, value = line.split(
            b":",
            1,
        )

        name = (
            name.decode("latin-1")
                .strip()
                .lower()
        )

        value = (
            value.decode("latin-1")
                 .strip()
        )

        headers[name] = value

    content_length = 0

    try:
        content_length = int(
            headers.get(
                "content-length",
                "0",
            )
        )

    except ValueError:
        raise ValueError(
            "Invalid Content-Length header."
        )

    if content_length < 0:
        raise ValueError(
            "Invalid HTTP body length."
        )

    if content_length > max_body_bytes:
        raise ValueError(
            "HTTP body is too large."
        )

    # Continue reading until the entire POST body arrives.
    while len(body_data) < content_length:

        remaining = (
            content_length
            - len(body_data)
        )

        chunk = client.recv(
            min(512, remaining)
        )

        if not chunk:
            break

        body_data.extend(chunk)

    if len(body_data) < content_length:
        raise ValueError(
            "Incomplete HTTP body."
        )

    body = bytes(
        body_data[:content_length]
    ).decode(
        "utf-8",
        "replace",
    )

    return HttpRequest(
        method,
        path,
        headers,
        body,
    )


# =========================================================
# Response Writing
# =========================================================

def write_all(client, data):
    """
    Write all bytes to the socket.

    socket.write() may send fewer bytes than requested,
    so this function continues until all bytes are sent.
    """

    position = 0

    while position < len(data):

        written = client.write(
            data[position:]
        )

        # Some MicroPython socket implementations return
        # None after successfully writing all data.
        if written is None:
            return

        if written <= 0:
            raise OSError(
                "Socket write failed."
            )

        position += written


def send_response(
    client,
    body,
    status="200 OK",
    content_type="text/html; charset=utf-8",
    extra_headers=None,
    cache_control="no-store",
):
    """
    Send a complete HTTP response.
    """

    if body is None:
        body = ""

    if isinstance(body, bytes):
        body_bytes = body
    else:
        body_bytes = str(body).encode(
            "utf-8"
        )

    headers = [
        "HTTP/1.1 %s" % status,
        "Content-Type: %s" % content_type,
        "Content-Length: %d" % len(body_bytes),
        "Cache-Control: %s" % cache_control,
        "Connection: close",
    ]

    if extra_headers:

        for name, value in extra_headers.items():
            headers.append(
                "%s: %s" % (
                    name,
                    value,
                )
            )

    header_text = (
        "\r\n".join(headers)
        + "\r\n\r\n"
    )

    write_all(
        client,
        header_text.encode("ascii"),
    )

    write_all(
        client,
        body_bytes,
    )


# =========================================================
# Common Responses
# =========================================================

def send_html(
    client,
    body,
    status="200 OK",
    extra_headers=None,
):
    send_response(
        client,
        body,
        status=status,
        extra_headers=extra_headers,
        content_type=(
            "text/html; charset=utf-8"
        ),
    )


def send_text(
    client,
    body,
    status="200 OK",
):
    send_response(
        client,
        body,
        status=status,
        content_type=(
            "text/plain; charset=utf-8"
        ),
    )


def send_redirect(
    client,
    location,
    status="302 Found",
):
    send_response(
        client,
        "",
        status=status,
        extra_headers={
            "Location": location,
        },
    )


# =========================================================
# HTTP Server Socket
# =========================================================

def create_server(
    port,
    accept_timeout_seconds,
    bind_ip=DEFAULT_BIND_IP,
    logger=None,
):
    """
    Create the HTTP listening socket.

    Binding to 0.0.0.0 allows the same server to work on:

    - the setup access point IP
    - the normal Wi-Fi station IP
    """

    address_info = socket.getaddrinfo(
    bind_ip,
    port,
    )

    address = address_info[0][-1]

    server = socket.socket()

    try:
        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )
    except Exception:
        # Some MicroPython firmware versions do not
        # implement SO_REUSEADDR.
        pass

    server.bind(address)

    server.listen(2)

    server.settimeout(
        accept_timeout_seconds
    )

    if logger is not None:
        logger(
            "HTTP server listening on port %d"
            % port
        )

    return server
