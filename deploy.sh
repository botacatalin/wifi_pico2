#!/bin/sh

set -eu

APP_ID="nodes-pico2w"
VERSION="${1:-1.0.0}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ARCHIVE="$SCRIPT_DIR/$APP_ID-$VERSION.zip"

case "$VERSION" in
    ''|*[!0-9.]*|.*|*.|*..*)
        echo "Usage: $0 [version]" >&2
        echo "Version must contain dot-separated numbers, for example 1.0.0." >&2
        exit 2
        ;;
esac

python3 - "$SCRIPT_DIR" "$ARCHIVE" "$VERSION" <<'PY'
import json
import os
import stat
import sys
import tempfile
import zipfile

root, archive, version = sys.argv[1:]
payload = (
    "main.py",
    "app.py",
    "app_logging.py",
    "config.py",
    "device_dashboard",
    "network_setup",
    "peer_communication",
    "plugins",
    "shared_web",
)

manifest = {
    "format": 1,
    "id": "wifi-pico2",
    "name": "Nodes Web Server",
    "version": version,
    "entrypoint": "main.py",
    "boards": ["pico2w"],
    "micropython": {"minimum": "1.28.0"},
    "install": {"erase_first": True, "reset_after": True},
    "source": "https://github.com/botacatalin/wifi_pico2",
    "files": [
        "main.py",
        "app.py",
        "app_logging.py",
        "config.py",
        "device_dashboard/",
        "network_setup/",
        "peer_communication/",
        "plugins/",
        "shared_web/",
    ],
}


def excluded(name):
    return (
        name == "__pycache__"
        or name.endswith(".pyc")
        or name.startswith("README") and name.endswith(".md")
        or name in (".git", ".github", "tests", "AGENTS.md", "LICENSE")
    )


def archive_info(name):
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


files = []
for item in payload:
    source = os.path.join(root, item)
    if not os.path.exists(source):
        raise SystemExit("Missing required payload: " + item)
    if os.path.isfile(source):
        files.append((source, "files/" + item))
        continue

    for directory, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(name for name in dirnames if not excluded(name))
        for filename in sorted(filenames):
            if excluded(filename):
                continue
            path = os.path.join(directory, filename)
            if os.path.islink(path):
                raise SystemExit("Refusing to package symbolic link: " + path)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            files.append((path, "files/" + relative))

fd, temporary = tempfile.mkstemp(
    prefix="." + os.path.basename(archive) + ".",
    suffix=".tmp",
    dir=os.path.dirname(archive),
)
os.close(fd)
try:
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as package:
        manifest_data = (
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")
        package.writestr(archive_info("manifest.json"), manifest_data)
        for source, destination in files:
            with open(source, "rb") as payload_file:
                package.writestr(archive_info(destination), payload_file.read())
    os.replace(temporary, archive)
except BaseException:
    try:
        os.unlink(temporary)
    except OSError:
        pass
    raise

print("Created {} ({} payload files)".format(archive, len(files)))
PY
