import argparse
import fcntl
import hashlib
import json
import logging
import os
import signal
import tempfile
import threading
from pathlib import Path

from .catalog import load_catalog
from .download import HTTP, UpstreamRateLimitError, download, protect_checksum
from .opsi import build, generate
from .repository import inventory, publish, retain
from .sources import resolve
from .state import atomic_json, now, read_state
from .versions import normalize, version_key

LOG = logging.getLogger(__name__)


def run(args):
    root = Path(os.getenv("REPO_ROOT", "/data"))
    catalog = Path(os.getenv("CATALOG_PATH", "/app/catalog/packages.yaml"))
    packages = load_catalog(catalog)
    ids = {p["opsi_product_id"] for p in packages}
    if (args.product and args.product not in ids) or set(args.force) - ids:
        raise ValueError("Unknown product selection")
    statepath = root / "state/packages.json"
    work = root / "work"
    repo = root / "repository"
    state = read_state(statepath)
    summary = {k: [] for k in ("Updated", "Unchanged", "Failed", "Warnings", "Disabled")}
    http = HTTP()
    keep = int(os.getenv("KEEP_VERSIONS", "2"))
    if keep < 1:
        raise ValueError("KEEP_VERSIONS must be >=1")
    # Reconstruct immutable checksum evidence even after state loss.
    for sidecar in repo.glob("*.opsi.provenance.json"):
        p = json.loads(sidecar.read_text())
        key = p["product_id"] + "@" + p["upstream_version"]
        current = state["checksums"].get(key)
        approved = state.get("checksum_overrides", {}).get(key, [])
        if current not in approved or p["sha256"] not in approved:
            protect_checksum(current, p["sha256"])
        state["checksums"].setdefault(key, p["sha256"])
    for p in packages:
        pid = p["opsi_product_id"]
        if args.product and args.product != pid:
            continue
        if not p.get("enabled", True):
            summary["Disabled"].append(pid + ": " + p["disabled_reason"])
            continue
        if p["redistribution"] != "allowed":
            warning = (
                pid
                + ": redistribution "
                + p["redistribution"]
                + "; verify rights before public exposure"
            )
            LOG.warning(warning)
            summary["Warnings"].append(warning)
        try:
            checked = now()
            if not args.dry_run:
                state["packages"].setdefault(pid, {})["last_checked"] = checked
            release = resolve(p, http)
            version = normalize(release.version)
            previous = state["packages"].get(pid, {})
            existing = inventory(repo, pid)
            desired = (version_key(version), p["package_revision"])
            if existing and desired < existing[-1][:2]:
                summary["Warnings"].append(
                    pid + ": upstream/catalog older than repository; downgrade blocked"
                )
                summary["Unchanged"].append(pid + ": " + str(existing[-1][0]))
                continue
            expected = f"{pid}_{version}-{p['package_revision']}.opsi"
            key = pid + "@" + release.version
            force = args.force_all or pid in args.force
            known = state["checksums"].get(key)
            allow = os.getenv("ALLOW_CHANGED_CHECKSUM", "false").lower() == "true"
            if release.sha256:
                protect_checksum(known, release.sha256.lower(), allow)
            proof = Path(str(repo / expected) + ".provenance.json")
            if proof.exists():
                evidence = json.loads(proof.read_text())
                if evidence["upstream_version"] != release.version:
                    raise ValueError(
                        "Normalized version collision; use a distinct product/revision"
                    )
                if (repo / expected).exists():
                    with (repo / expected).open("rb") as package_file:
                        if (
                            hashlib.file_digest(package_file, "sha256").hexdigest()
                            != evidence["package_sha256"]
                        ):
                            raise ValueError(
                                "Published package checksum mismatch; investigate repository corruption"
                            )
            if (repo / expected).exists() and not force:
                summary["Unchanged"].append(pid + ": " + version)
                continue
            if args.dry_run:
                summary["Updated"].append(
                    pid + ": would build " + expected + " from " + release.url
                )
                continue
            with tempfile.TemporaryDirectory(prefix=pid + "-", dir=work) as tmp:
                tmp = Path(tmp)
                installer, sha, size, signature = download(http, release, p, tmp)
                protect_checksum(known, sha, allow)
                if force and (repo / expected).exists() and not known:
                    raise ValueError(
                        "Existing version has no checksum provenance; restore state or increment revision"
                    )
                provenance = {
                    "product_id": pid,
                    "vendor": p["name"],
                    "upstream_version": release.version,
                    "opsi_version": version,
                    "package_revision": p["package_revision"],
                    "source_url": release.url,
                    "sha256": sha,
                    "size": size,
                    "download_timestamp": now(),
                    "last_checked": checked,
                    "last_success": now(),
                    "signature_status": signature,
                    "detection_version": release.detection_version,
                }
                LOG.info("%s: %s SHA256=%s bytes=%s", pid, signature, sha, size)
                source = generate(
                    p,
                    release,
                    version,
                    tmp / pid,
                    Path(__file__).resolve().parents[1] / "templates",
                    catalog.parent / "overrides",
                    installer,
                )
                (source / "CLIENT_DATA/provenance.json").write_text(
                    json.dumps(provenance, indent=2)
                )
                artifact = build(source, tmp / "output", expected)
                with artifact.open("rb") as package_file:
                    provenance["package_sha256"] = hashlib.file_digest(
                        package_file, "sha256"
                    ).hexdigest()
                Path(str(artifact) + ".provenance.json").write_text(
                    json.dumps(provenance, indent=2)
                )
                if known and known != sha:
                    LOG.warning(
                        "%s: EXPLICIT CHECKSUM OVERRIDE accepted: %s -> %s",
                        pid,
                        known,
                        sha,
                    )
                    history = state.setdefault("checksum_overrides", {}).setdefault(key, [])
                    for accepted in (known, sha):
                        if accepted not in history:
                            history.append(accepted)
                publish(artifact, repo)
                state["packages"][pid] = provenance
                state["checksums"][key] = sha
                atomic_json(statepath, state)
                summary["Updated"].append(
                    pid + ": " + previous.get("upstream_version", "none") + " -> " + release.version
                )
        except UpstreamRateLimitError as exc:
            if exc.host == "api.github.com":
                LOG.warning("%s skipped", pid)
                summary["Warnings"].append(pid + ": " + str(exc))
            else:
                LOG.exception("%s failed", pid)
                summary["Failed"].append(pid + ": " + str(exc))
        except Exception as exc:
            LOG.exception("%s failed", pid)
            summary["Failed"].append(pid + ": " + str(exc))
    if not args.dry_run:
        try:
            retain(repo, work, keep)
        except Exception as exc:
            LOG.exception("Repository metadata/retention failed")
            summary["Failed"].append("repository: " + str(exc))
        atomic_json(statepath, state)
        atomic_json(root / "state/last-run.json", {"finished": now(), "summary": summary})
    for title, items in summary.items():
        print(title + ":", flush=True)
        for line in items:
            print("  " + line, flush=True)
    return bool(summary["Failed"])


def main():
    parser = argparse.ArgumentParser(description="Build official-installer OPSI repository")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="append", default=[])
    parser.add_argument("--force-all", action="store_true")
    parser.add_argument("--product")
    args = parser.parse_args()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    root = Path(os.getenv("REPO_ROOT", "/data"))
    for name in ("state", "work", "repository"):
        if not args.dry_run:
            (root / name).mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    interval = int(os.getenv("UPDATE_INTERVAL_SECONDS", "21600"))
    if interval < 60:
        parser.error("UPDATE_INTERVAL_SECONDS must be >=60")
    # Dry runs do not create or write lock/state files. Writers serialize using flock.
    while not stop.is_set():
        try:
            if args.dry_run:
                failed = run(args)
            else:
                with (root / "state/builder.lock").open("a") as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        LOG.error("Another builder is active; retry after it completes")
                        return 2
                    # Work contains only owned temporary build data; clean crash leftovers under lock.
                    import shutil

                    for path in (root / "work").iterdir():
                        if path.is_dir() and (
                            path.name.startswith("auto-")
                            or path.name.startswith("metadata-")
                            or (path.name.startswith("ziplaunch.") and ".opsi-cli." in path.name)
                        ):
                            shutil.rmtree(path)
                    failed = run(args)
        except Exception:
            LOG.exception("Builder cycle failed")
            failed = True
        if args.once or args.dry_run:
            return int(failed)
        stop.wait(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
