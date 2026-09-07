import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

from .opsi import command
from .versions import version_key

PATTERN = re.compile(r"^([a-z0-9-]+)_([A-Za-z0-9.]+)-(\d+)\.opsi$")


def inventory(repository, product=None):
    result = []
    for path in Path(repository).glob("*.opsi"):
        m = PATTERN.fullmatch(path.name)
        if not m:
            raise ValueError("Unrecognized repository package: " + path.name)
        if not product or m[1] == product:
            result.append((version_key(m[2]), int(m[3]), path))
    return sorted(result, key=lambda i: (i[0], i[1]))


def obsolete(repository, keep):
    if keep < 1:
        raise ValueError("KEEP_VERSIONS must be >= 1")
    groups = {}
    for item in inventory(repository):
        groups.setdefault(PATTERN.fullmatch(item[2].name)[1], []).append(item)
    return [item[2] for group in groups.values() for item in group[:-keep]]


def metadata(repository, work, excluded=()):
    # Build in an unserved directory; never let the CLI mutate live metadata.
    with tempfile.TemporaryDirectory(prefix="metadata-", dir=work) as tmp:
        stage = Path(tmp)
        for p in Path(repository).glob("*.opsi"):
            if p not in excluded:
                try:
                    os.link(p, stage / p.name)
                except OSError as exc:
                    import errno

                    if exc.errno != errno.EXDEV:
                        raise
                    shutil.copyfile(p, stage / p.name)
        command(["manage-repo", "metafile", "create", stage])
        command(["manage-repo", "metafile", "scan-packages", stage])
        files = [p for p in stage.iterdir() if p.is_file() and p.suffix != ".opsi"]
        if not files:
            raise ValueError("OPSI CLI produced no repository metadata")
        for p in files:
            hidden = Path(repository) / ("." + p.name + ".tmp")
            shutil.copyfile(p, hidden)
            os.replace(hidden, Path(repository) / p.name)


def retain(repository, work, keep):
    old = obsolete(repository, keep)
    metadata(repository, work, old)
    for p in old:
        for suffix in ("", ".md5", ".zsync", ".provenance.json"):
            Path(str(p) + suffix).unlink(missing_ok=True)
        logging.info("Deleted obsolete package %s", p.name)


def publish(package, repository):
    for suffix in (".md5", ".zsync", ".provenance.json", ""):
        source = Path(str(package) + suffix)
        target = Path(repository) / (package.name + suffix)
        hidden = target.with_name("." + target.name + ".tmp")
        shutil.copyfile(source, hidden)
        with hidden.open("rb") as f:
            os.fsync(f.fileno())
        os.replace(hidden, target)
