import re

from packaging.version import Version


def normalize(value):
    value = str(value).strip()
    value = re.sub(r"^v(?=\d)", "", value)
    value = value.replace(".windows.", "+windows.")
    parsed = Version(value)
    if parsed.local and not parsed.local.startswith("windows."):
        result = str(parsed).replace("+", ".local.")
    else:
        result = str(parsed).replace("+", ".")
    if len(result) > 32 or not re.fullmatch(r"[a-zA-Z0-9.]+", result):
        raise ValueError(f"Not an OPSI-compatible version: {value}")
    return result


def version_key(value):
    return Version(
        re.sub(r"^v(?=\d)", "", str(value))
        .replace(".local.", "+")
        .replace(".windows.", "+windows.")
    )
