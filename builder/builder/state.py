import json
import os
from datetime import UTC, datetime
from pathlib import Path


def now():
    return datetime.now(UTC).isoformat()


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def read_state(path):
    if not Path(path).exists():
        return {"schema_version": 2, "packages": {}, "checksums": {}}
    data = json.loads(Path(path).read_text())
    if "schema_version" not in data:
        data = {"schema_version": 1, "packages": data}
    if data["schema_version"] not in (1, 2):
        raise ValueError("Unsupported future state schema")
    data.setdefault("checksums", {})
    for pid, p in data["packages"].items():
        if p.get("sha256") and p.get("upstream_version"):
            data["checksums"].setdefault(pid + "@" + p["upstream_version"], p["sha256"])
    data["schema_version"] = 2
    return data
