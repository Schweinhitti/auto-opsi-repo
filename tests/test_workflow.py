import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from builder.catalog import load_catalog
from builder.download import HTTP, UpstreamRateLimitError, download, safe_extract_zip
from builder.models import Release
from builder.sources.adapters import resolve, select_github
from builder.versions import normalize, version_key

from builder import main, repository

ROOT = Path(__file__).resolve().parents[1]


def package():
    return copy.deepcopy(load_catalog(ROOT / "catalog/packages.yaml")[0])


@pytest.mark.parametrize("version", ["21.0.12+101.0.LTS", "2.55.0.windows.5", "1.2.3+build.8"])
def test_normalization_roundtrip(version):
    assert version_key(normalize(version)) == version_key(version)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(redistribution="free"),
        lambda p: p.update(architecture=["arm64"]),
        lambda p: p.update(package_revision=0),
        lambda p: p["source"].update(type="bogus"),
        lambda p: p.update(opsi_product_id="../bad"),
        lambda p: p["installer"].update(type="script"),
        lambda p: p["source"].update(allowed_hosts=[]),
        lambda p: p["detection"].update(method="guess"),
    ],
)
def test_invalid_catalog(tmp_path, mutation):
    p = package()
    mutation(p)
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump({"packages": [p]}))
    with pytest.raises(ValueError):
        load_catalog(path)


def test_duplicate_catalog(tmp_path):
    p = package()
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump({"packages": [p, p]}))
    with pytest.raises(ValueError):
        load_catalog(path)


def test_no_stale_github_fallback():
    data = [
        {"tag_name": "v2.0", "assets": []},
        {
            "tag_name": "v1.0",
            "assets": [{"name": "a.exe", "browser_download_url": "https://github.com/a"}],
        },
    ]
    with pytest.raises(ValueError, match="Newest release"):
        select_github(data, {"asset_regex": "a.exe"})


@pytest.mark.parametrize("kind", ["direct_url", "videolan", "documentfoundation"])
def test_direct_sources(kind):
    p = package()
    p["source"] = {
        "type": kind,
        "version_url": "https://vendor.test/versions",
        "version_regex": r"(\d+\.\d+\.\d+)",
        "download_url_template": "https://vendor.test/{version}.exe",
        "allowed_hosts": ["vendor.test"],
        "track": "3.14",
    }

    class Mock:
        def get(self, *args):
            return b"3.14.1 3.15.0 3.14.10"

    assert resolve(p, Mock()).version == "3.14.10"


@pytest.mark.parametrize("kind", ["adoptium", "vendor_json_api"])
def test_json_source(kind):
    p = package()
    p["source"] = {
        "type": kind,
        "api_url": "https://vendor.test/{java_version}",
        "java_version": 21,
        "version_field": "0.version",
        "url_field": "0.url",
        "sha256_field": "0.sha",
        "allowed_hosts": ["vendor.test"],
    }

    class Mock:
        def json(self, *args):
            return [
                {
                    "version": "21.0.1",
                    "url": "https://vendor.test/a.msi",
                    "sha": "a" * 64,
                }
            ]

    assert resolve(p, Mock()).sha256 == "a" * 64


def test_microsoft():
    p = package()
    p["source"] = {
        "type": "microsoft",
        "api_url": "https://vendor.test/api",
        "allowed_hosts": ["vendor.test"],
    }

    class Mock:
        def json(self, *args):
            return {
                "productVersion": "1.5",
                "url": "https://vendor.test/a.exe",
                "sha256hash": "b" * 64,
            }

    assert resolve(p, Mock()).version == "1.5"


@pytest.mark.parametrize("host", ["vendor.test", "evil.test"])
def test_winget_selection(host):
    p = package()
    p["source"] = {
        "type": "winget_manifest",
        "package_identifier": "Vendor.App",
        "allowed_hosts": ["vendor.test"],
    }

    class Mock:
        def json(self, *args):
            return [
                {"type": "dir", "name": "1.9"},
                {"type": "dir", "name": "1.10"},
                {"type": "dir", "name": "2.0-beta"},
            ]

        def get(self, url, *args):
            assert "/1.10/" in url
            return yaml.safe_dump(
                {
                    "Installers": [
                        {
                            "Architecture": "x64",
                            "InstallerType": "exe",
                            "Scope": "machine",
                            "InstallerUrl": f"https://{host}/a",
                            "InstallerSha256": "a" * 64,
                        },
                        {
                            "Architecture": "arm64",
                            "InstallerType": "exe",
                            "InstallerUrl": "https://wrong/a",
                        },
                    ]
                }
            ).encode()

    if host == "evil.test":
        with pytest.raises(ValueError):
            resolve(p, Mock())
    else:
        assert resolve(p, Mock()).version == "1.10"


def test_html_download_rejected(tmp_path):
    class Mock:
        def stream(self, *args):
            yield b"<html>" + b"x" * 2000

    with pytest.raises(ValueError, match="format"):
        download(Mock(), Release("1", "https://vendor.test/a"), package(), tmp_path)
    assert not (tmp_path / "installer.exe").exists()


def test_download_hash(tmp_path):
    import hashlib

    payload = b"MZ" + b"x" * 2048

    class Mock:
        def stream(self, *args):
            yield payload

    result = download(
        Mock(),
        Release("1", "https://vendor.test/a", hashlib.sha256(payload).hexdigest()),
        package(),
        tmp_path,
    )
    assert result[2] == len(payload)


def test_dry_run_no_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CATALOG_PATH", str(ROOT / "catalog/packages.yaml"))
    monkeypatch.setattr(
        main, "resolve", lambda *args: Release("155.0", "https://archive.mozilla.org/a")
    )
    args = SimpleNamespace(product="auto-firefox", force=[], force_all=False, dry_run=True)
    assert main.run(args) == 0
    assert list(tmp_path.iterdir()) == []


def test_duplicate_prevention(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CATALOG_PATH", str(ROOT / "catalog/packages.yaml"))
    (tmp_path / "repository").mkdir()
    (tmp_path / "repository/auto-firefox_155.0-1.opsi").touch()
    monkeypatch.setattr(
        main, "resolve", lambda *args: Release("155.0", "https://archive.mozilla.org/a")
    )
    monkeypatch.setattr(
        main, "download", lambda *args: pytest.fail("duplicate installer downloaded")
    )
    args = SimpleNamespace(product="auto-firefox", force=[], force_all=False, dry_run=True)
    assert main.run(args) == 0


def test_metadata_failure_does_not_delete(tmp_path, monkeypatch):
    for version in ["1.0", "2.0", "3.0"]:
        (tmp_path / f"auto-a_{version}-1.opsi").touch()

    def fail(*args):
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(repository, "metadata", fail)
    with pytest.raises(RuntimeError):
        repository.retain(tmp_path, tmp_path, 2)
    assert len(list(tmp_path.glob("*.opsi"))) == 3


def test_retain_deletes_obsolete_sidecars(tmp_path, monkeypatch):
    old = tmp_path / "auto-a_1.0-1.opsi"
    new = tmp_path / "auto-a_2.0-1.opsi"
    old.touch()
    new.touch()
    for suffix in (".md5", ".zsync", ".provenance.json"):
        Path(str(old) + suffix).write_text("x")
        Path(str(new) + suffix).write_text("x")

    def metadata(repo, work, excluded=()):
        assert list(excluded) == [old]

    monkeypatch.setattr(repository, "metadata", metadata)
    repository.retain(tmp_path, tmp_path, 1)
    assert not old.exists()
    for suffix in (".md5", ".zsync", ".provenance.json"):
        assert not Path(str(old) + suffix).exists()
        assert Path(str(new) + suffix).exists()


def test_metadata_cross_device_fallback(tmp_path, monkeypatch):
    import errno

    repo = tmp_path / "repo"
    repo.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    (repo / "auto-a_1.0-1.opsi").write_bytes(b"package")

    def link(*args):
        raise OSError(errno.EXDEV, "cross-device")

    def cli(args):
        stage = Path(args[-1])
        assert (stage / "auto-a_1.0-1.opsi").read_bytes() == b"package"
        (stage / "packages.json").write_text("{}")

    monkeypatch.setattr(repository.os, "link", link)
    monkeypatch.setattr(repository, "command", cli)
    repository.metadata(repo, work)
    assert (repo / "packages.json").read_text() == "{}"


def test_stream_redirect_is_validated_before_request(monkeypatch):
    http = HTTP()
    calls = []

    class Response:
        is_redirect = True
        headers = {"Location": "https://evil.test/payload"}

        def close(self):
            pass

    def get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(http.session, "get", get)
    with pytest.raises(ValueError):
        http.get("https://vendor.test/payload", ["vendor.test"])
    assert calls == ["https://vendor.test/payload"]


def test_partial_download_retried_from_scratch(tmp_path, monkeypatch):
    import requests

    from builder import download as module

    calls = []

    class Mock:
        def stream(self, *args):
            calls.append(1)
            yield b"MZ" + b"x" * 2048
            if len(calls) == 1:
                raise requests.exceptions.ChunkedEncodingError("connection lost")

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    result = download(Mock(), Release("1", "https://vendor.test/a"), package(), tmp_path)
    assert len(calls) == 2 and result[2] == 2050


def test_named_vendor_checksum():
    p = package()

    class Mock:
        def json(self, *args):
            return {"LATEST_FIREFOX_VERSION": "155.0"}

        def get(self, *args):
            return (
                "b" * 64 + "  other.exe\n" + "a" * 64 + "  win64/en-US/Firefox Setup 155.0.exe\n"
            ).encode()

    assert resolve(p, Mock()).sha256 == "a" * 64


def test_signature_checksum_asset():
    p = package()
    p["source"] = {
        "type": "github_release",
        "repo": "vendor/app",
        "asset_regex": "app.exe",
        "checksum_asset_regex": "SHA256SUMS",
        "allowed_hosts": ["github.com"],
    }

    class Mock:
        def json(self, *args):
            return [
                {
                    "tag_name": "v1.0",
                    "assets": [
                        {
                            "name": "app.exe",
                            "browser_download_url": "https://github.com/vendor/app/releases/app.exe",
                        },
                        {
                            "name": "SHA256SUMS",
                            "browser_download_url": "https://github.com/vendor/app/releases/SHA256SUMS",
                        },
                    ],
                }
            ]

        def get(self, *args):
            return ("a" * 64 + "  app.exe\n").encode()

    assert resolve(p, Mock()).sha256 == "a" * 64


def test_failure_isolation(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CATALOG_PATH", str(ROOT / "catalog/packages.yaml"))
    calls = []

    def resolve_mock(p, http):
        calls.append(p["id"])
        if p["id"] == "firefox":
            raise RuntimeError("vendor unavailable")
        return Release("100.0", "https://vendor.test/a")

    monkeypatch.setattr(main, "resolve", resolve_mock)
    assert main.run(SimpleNamespace(product=None, force=[], force_all=False, dry_run=True)) == 1
    assert "everything" in calls
    assert "auto-firefox: vendor unavailable" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_github_rate_limit_is_cached(monkeypatch):
    http = HTTP()
    calls = []
    reset = str(int(time.time()) + 3600)

    class Response:
        is_redirect = False
        status_code = 429
        headers = {"X-RateLimit-Reset": reset}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(http.session, "get", get)
    with pytest.raises(UpstreamRateLimitError):
        http.get("https://api.github.com/repos/vendor/app/releases", ["api.github.com"])
    with pytest.raises(UpstreamRateLimitError):
        http.get("https://api.github.com/repos/vendor/app/releases", ["api.github.com"])
    assert len(calls) == 1


def test_github_rate_limit_is_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CATALOG_PATH", str(ROOT / "catalog/packages.yaml"))
    calls = []

    def resolve_mock(p, http):
        calls.append(p["id"])
        if p["id"] == "firefox":
            raise UpstreamRateLimitError("api.github.com", "123")
        return Release("100.0", "https://vendor.test/a")

    monkeypatch.setattr(main, "resolve", resolve_mock)
    assert main.run(SimpleNamespace(product=None, force=[], force_all=False, dry_run=True)) == 0
    out = capsys.readouterr().out
    assert "auto-firefox: Upstream access/rate limit; retry next cycle (reset=123)" in out
    assert "everything" in calls


def test_zip_symlink(tmp_path):
    import stat
    import zipfile

    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        item = zipfile.ZipInfo("link")
        item.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(item, "/outside")
    with pytest.raises(ValueError):
        safe_extract_zip(archive, tmp_path / "output")


def test_approved_checksum_history_survives_retention(tmp_path, monkeypatch):
    from builder.state import atomic_json

    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CATALOG_PATH", str(ROOT / "catalog/packages.yaml"))
    (tmp_path / "state").mkdir()
    (tmp_path / "repository").mkdir()
    key = "auto-firefox@155.0"
    atomic_json(
        tmp_path / "state/packages.json",
        {
            "schema_version": 2,
            "packages": {},
            "checksums": {key: "b" * 64},
            "checksum_overrides": {key: ["a" * 64, "b" * 64]},
        },
    )
    atomic_json(
        tmp_path / "repository/auto-firefox_155.0-1.opsi.provenance.json",
        {"product_id": "auto-firefox", "upstream_version": "155.0", "sha256": "a" * 64},
    )
    monkeypatch.setattr(
        main, "resolve", lambda *args: Release("156.0", "https://archive.mozilla.org/a")
    )
    assert (
        main.run(SimpleNamespace(product="auto-firefox", force=[], force_all=False, dry_run=True))
        == 0
    )


def test_tabular_checksum_asset():
    p = package()
    p["source"] = {
        "type": "github_release",
        "repo": "vendor/app",
        "asset_regex": "app.exe",
        "checksum_asset_regex": "CHECKSUMS.txt",
        "checksum_line_regex": r"^{filename}\s+\d+\s+([a-fA-F0-9]{64})\s*$",
        "allowed_hosts": ["github.com"],
    }

    class Mock:
        def json(self, *args):
            return [
                {
                    "tag_name": "v1.0",
                    "assets": [
                        {
                            "name": "app.exe",
                            "browser_download_url": "https://github.com/vendor/app/releases/app.exe",
                        },
                        {
                            "name": "CHECKSUMS.txt",
                            "browser_download_url": "https://github.com/vendor/app/releases/CHECKSUMS.txt",
                        },
                    ],
                }
            ]

        def get(self, *args):
            return ("app.exe 1234 " + "a" * 64 + "\n").encode()

    assert resolve(p, Mock()).sha256 == "a" * 64


@pytest.mark.parametrize(
    "product,release,expected",
    [
        ("git", Release("2.55.0.windows.5", "https://github.com/a"), "2.55.0.5"),
        ("python", Release("3.14.7", "https://www.python.org/a"), "3.14.7"),
        (
            "temurin",
            Release(
                "21.0.12+101.0.LTS", "https://github.com/a", detection_version="21.0.12.1+1-LTS"
            ),
            "21.0.12.1",
        ),
    ],
)
def test_vendor_detection_versions(tmp_path, product, release, expected):
    from builder.opsi import generate

    p = next(p for p in load_catalog(ROOT / "catalog/packages.yaml") if p["id"] == product)
    source = generate(
        p,
        release,
        normalize(release.version),
        tmp_path / "source",
        ROOT / "builder/templates",
        ROOT / "catalog/overrides",
    )
    config = json.loads((source / "CLIENT_DATA/config.json").read_text())
    assert config["detection_version"] == expected
    if product == "python":
        assert config["detection"]["version_from_display_name_regex"]


def test_offline_repackage_rejects_modified_archive(tmp_path):
    from builder.repackage import verify_archive

    path = tmp_path / "bad.opsi"
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA256"):
        verify_archive(path, {"package_sha256": "0" * 64})
