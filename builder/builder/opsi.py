import hashlib
import json
import shutil
import subprocess
import tomllib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .download import safe_extract_zip


def command(args):
    subprocess.run(
        ["opsi-cli", *map(str, args)],
        check=True,
        timeout=3600,
        stdin=subprocess.DEVNULL,
    )


def generate(package, release, version, destination, templates, overrides, installer=None):
    root = Path(destination)
    client = root / "CLIENT_DATA"
    control = root / "OPSI"
    client.mkdir(parents=True)
    control.mkdir()
    env = Environment(
        loader=FileSystemLoader(str(templates)),
        undefined=StrictUndefined,
        autoescape=lambda template_name: template_name is not None and template_name.endswith((".html", ".xml")),
    )
    context = {
        "p": package,
        "version": version,
        "revision": str(package["package_revision"]),
        "custom_detection": "",
    }
    override = Path(overrides) / package["opsi_product_id"]
    for key in (
        "pre_install_opsi_script",
        "post_install_opsi_script",
        "pre_uninstall_opsi_script",
        "post_uninstall_opsi_script",
    ):
        context[key] = ""
        if package.get(key):
            path = (override / package[key]).resolve()
            if not path.is_relative_to(override.resolve()):
                raise ValueError("Override traversal")
            context[key] = env.from_string(path.read_text()).render(**context)
    if package["detection"]["method"] == "custom":
        path = (override / package["detection"]["script"]).resolve()
        if not path.is_relative_to(override.resolve()):
            raise ValueError("Override traversal")
        context["custom_detection"] = env.from_string(path.read_text()).render(**context)
    for name, target in [
        ("control.toml", control),
        ("setup.opsiscript", client),
        ("uninstall.opsiscript", client),
    ]:
        custom = override / (name + ".j2")
        template = (
            env.from_string(custom.read_text())
            if custom.exists()
            else env.get_template(name + ".j2")
        )
        (target / name).write_text(template.render(**context) + "\n")
    tomllib.loads((control / "control.toml").read_text())
    for name in ("runtime.ps1", "install.ps1", "uninstall.ps1"):
        shutil.copyfile(Path(templates) / name, client / name)
    detection_version = (release.detection_version or release.version).lstrip("v")
    for old, new in package["detection"].get("version_replacements", {}).items():
        detection_version = detection_version.replace(old, new)
    config = {**package, "detection_version": detection_version}
    if package["detection"].get("version_regex"):
        import re

        config["detection_version"] = re.search(
            package["detection"]["version_regex"], detection_version
        ).group(1)
    (client / "config.json").write_text(json.dumps(config, indent=2))
    if installer:
        shutil.copyfile(installer, client / ("installer." + package["installer"]["type"]))
        if package["installer"]["type"] == "zip":
            safe_extract_zip(installer, client / "payload")
    return root


def build(source, output, expected):
    output.mkdir()
    command(["package", "make", source, output])
    package = output / expected
    if not package.is_file() or not all(
        Path(str(package) + suffix).is_file() for suffix in (".md5", ".zsync")
    ):
        raise ValueError("OPSI make did not produce expected package and sidecars")
    extracted = output / "verify"
    command(["package", "extract", package, extracted])
    if not list(extracted.rglob("control.toml")) or not list(extracted.rglob("setup.opsiscript")):
        raise ValueError("OPSI archive round-trip validation failed")
    extracted_controls = list(extracted.rglob("control.toml"))
    expected_control = tomllib.loads((source / "OPSI/control.toml").read_text())
    actual_control = tomllib.loads(extracted_controls[0].read_text())
    for section, fields in [("Product", ("id", "version")), ("Package", ("version",))]:
        if any(
            actual_control[section][field] != expected_control[section][field] for field in fields
        ):
            raise ValueError("OPSI archive control metadata mismatch")
    for original in (source / "CLIENT_DATA").glob("installer.*"):
        matches = list(extracted.rglob(original.name))
        if len(matches) != 1:
            raise ValueError("Bundled installer missing or ambiguous after extraction")
        with original.open("rb") as a, matches[0].open("rb") as b:
            if (
                hashlib.file_digest(a, "sha256").digest()
                != hashlib.file_digest(b, "sha256").digest()
            ):
                raise ValueError("Bundled installer changed during packaging")
    with package.open("rb") as archive:
        if (
            hashlib.file_digest(archive, "md5").hexdigest()
            != Path(str(package) + ".md5").read_text().strip().split()[0]
        ):
            raise ValueError("OPSI package MD5 sidecar mismatch")
    return package
