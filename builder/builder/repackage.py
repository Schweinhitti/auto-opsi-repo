"""Offline packaging-revision recovery using an existing verified OPSI payload.

This command never discovers a new software version. It requires an increased
catalog revision and retains original installer provenance.
"""

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .catalog import load_catalog
from .download import protect_checksum
from .models import Release
from .opsi import build, command, generate
from .repository import inventory, publish, retain
from .state import atomic_json, now, read_state


def verify_archive(archive, proof):
    with archive.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != proof["package_sha256"]:
            raise ValueError("Existing OPSI archive does not match recorded SHA256")


def repackage(product, root, catalog):
    p = next(p for p in load_catalog(catalog) if p["opsi_product_id"] == product)
    if not p.get("enabled", True):
        raise ValueError("Cannot repackage disabled product")
    repo = root / "repository"
    work = root / "work"
    statepath = root / "state/packages.json"
    with (root / "state/builder.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = read_state(statepath)
        previous = inventory(repo, product)
        if not previous:
            raise ValueError("No existing archive to repackage")
        archive = previous[-1][2]
        proof = json.loads(Path(str(archive) + ".provenance.json").read_text())
        verify_archive(archive, proof)
        if p["package_revision"] <= proof["package_revision"]:
            raise ValueError("Increase package_revision before offline repackaging")
        key = product + "@" + proof["upstream_version"]
        protect_checksum(state["checksums"].get(key), proof["sha256"])
        if p["source"].get("detection_version_field") and not proof.get("detection_version"):
            raise ValueError("Required source detection metadata absent; perform an online build")
        release = Release(
            proof["upstream_version"],
            proof["source_url"],
            proof["sha256"],
            detection_version=proof.get("detection_version"),
        )
        expected = f"{product}_{proof['opsi_version']}-{p['package_revision']}.opsi"
        with tempfile.TemporaryDirectory(prefix=product + "-", dir=work) as tmp:
            tmp = Path(tmp)
            command(["package", "extract", archive, tmp / "previous"])
            installers = list((tmp / "previous").rglob("installer." + p["installer"]["type"]))
            if len(installers) != 1:
                raise ValueError("No unique installer of the configured type")
            installer = installers[0]
            with installer.open("rb") as f:
                protect_checksum(proof["sha256"], hashlib.file_digest(f, "sha256").hexdigest())
            source = generate(
                p,
                release,
                proof["opsi_version"],
                tmp / product,
                Path(__file__).resolve().parents[1] / "templates",
                catalog.parent / "overrides",
                installer,
            )
            newproof = {
                **proof,
                "package_revision": p["package_revision"],
                "repackaged_from": archive.name,
                "last_success": now(),
            }
            newproof.pop("package_sha256", None)
            (source / "CLIENT_DATA/provenance.json").write_text(json.dumps(newproof, indent=2))
            result = build(source, tmp / "output", expected)
            with result.open("rb") as f:
                newproof["package_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
            Path(str(result) + ".provenance.json").write_text(json.dumps(newproof, indent=2))
            publish(result, repo)
            state["packages"][product] = newproof
            state["checksums"][key] = proof["sha256"]
            atomic_json(statepath, state)
        retain(repo, work, int(os.getenv("KEEP_VERSIONS", "2")))
        print(f"Offline repackaged {archive.name} -> {expected}; upstream was NOT checked")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product")
    args = parser.parse_args()
    repackage(
        args.product,
        Path(os.getenv("REPO_ROOT", "/data")),
        Path(os.getenv("CATALOG_PATH", "/app/catalog/packages.yaml")),
    )


if __name__ == "__main__":
    main()
