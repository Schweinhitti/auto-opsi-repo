import re
from pathlib import Path

import yaml

SOURCE_TYPES = {
    "github_release",
    "direct_url",
    "mozilla",
    "videolan",
    "documentfoundation",
    "microsoft",
    "vendor_json_api",
    "winget_manifest",
    "adoptium",
}


def load_catalog(path):
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict) or not isinstance(data.get("packages"), list):
        raise ValueError("Catalog requires packages list")
    seen = set()
    for p in data["packages"]:
        if not isinstance(p, dict):
            raise ValueError("Each package must be a mapping")
        if type(p.get("enabled", True)) is not bool:
            raise ValueError("enabled must be a boolean")
        pid = p["opsi_product_id"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", pid) or pid in seen:
            raise ValueError(f"Invalid or duplicate product: {pid}")
        seen.add(pid)
        if p.get("redistribution") not in {"allowed", "internal_only", "unknown"}:
            raise ValueError(f"{pid}: invalid redistribution")
        if not p.get("enabled", True):
            if not p.get("disabled_reason"):
                raise ValueError("Disabled package needs reason")
            continue
        if p["source"]["type"] not in SOURCE_TYPES:
            raise ValueError("Unknown source")
        if p.get("architecture") != ["x64"]:
            raise ValueError("One x64 installer per product supported")
        if type(p["package_revision"]) is not int or p["package_revision"] < 1:
            raise ValueError("Invalid revision")
        if p["installer"]["type"] not in {"exe", "msi", "msix", "zip"}:
            raise ValueError("Invalid installer")
        if not p["source"].get("allowed_hosts"):
            raise ValueError("Explicit official host allowlist required")
        if p["detection"]["method"] not in {
            "registry",
            "file_version",
            "msi",
            "custom",
        }:
            raise ValueError("Invalid detection")
        if p["uninstall"]["method"] not in {
            "registry",
            "msi",
            "command",
            "vendor",
            "zip",
            "msix",
        }:
            raise ValueError("Invalid uninstall")
        for required in ("id", "name", "description"):
            if not isinstance(p.get(required), str) or not p[required].strip():
                raise ValueError(f"{pid}: missing {required}")
        detect = p["detection"]
        if detect["method"] == "registry":
            if not detect.get("display_name_regex"):
                raise ValueError("Registry detection needs regex")
            re.compile(detect["display_name_regex"])
        if detect["method"] == "file_version" and not detect.get("path"):
            raise ValueError("File-version detection needs path")
        if detect["method"] == "msi" and not re.fullmatch(
            r"\{[a-fA-F0-9-]{36}\}", detect.get("product_code", "")
        ):
            raise ValueError("MSI detection needs GUID")
        if detect["method"] == "custom" and not detect.get("script"):
            raise ValueError("Custom detection needs script file")
        if p["installer"]["type"] in ("exe", "msi") and not p["installer"].get("silent_args"):
            raise ValueError("Installer needs explicit unattended arguments")
        if p["installer"]["type"] == "zip" and not p["installer"].get("target_dir"):
            raise ValueError("ZIP installer needs dedicated target directory")
        for host in p["source"]["allowed_hosts"]:
            if not isinstance(host, str) or not re.fullmatch(r"(?:\*\.)?[A-Za-z0-9.-]+", host):
                raise ValueError("Invalid source hostname")
        for section in ("installer", "uninstall"):
            args = p[section].get("silent_args", [])
            if not isinstance(args, list) or not all(
                isinstance(a, str) and "\n" not in a for a in args
            ):
                raise ValueError("Invalid arguments")
    return data["packages"]
