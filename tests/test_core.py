import hashlib
import tomllib
import zipfile
from pathlib import Path

import pytest
from builder.catalog import load_catalog
from builder.download import (
    protect_checksum,
    safe_extract_zip,
    validate_url,
    verify_checksum,
)
from builder.models import Release
from builder.opsi import generate
from builder.repository import inventory, obsolete
from builder.sources.adapters import resolve, select_github
from builder.state import atomic_json, read_state
from builder.versions import normalize, version_key

ROOT = Path(__file__).resolve().parents[1]


def test_catalog():
    packages = load_catalog(ROOT / "catalog/packages.yaml")
    assert len(packages) == 24
    assert next(p for p in packages if p["id"] == "rustdesk")["source"]["type"] == "github_release"


def test_libreoffice_and_pdf24_enabled_with_latest_sources():
    packages = {p["id"]: p for p in load_catalog(ROOT / "catalog/packages.yaml")}
    assert packages["libreoffice"]["enabled"] is True
    assert packages["libreoffice"]["source"]["type"] == "winget_manifest"
    assert packages["libreoffice"]["source"]["disable_host_validation"] is True
    assert packages["pdf24"]["enabled"] is True
    assert packages["pdf24"]["source"]["type"] == "winget_manifest"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("v1.4.2", "1.4.2"),
        ("2026.03", "2026.3"),
        ("1.2.3-beta", "1.2.3b0"),
        ("25.8.1.1", "25.8.1.1"),
        ("3.0.22", "3.0.22"),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_compare():
    assert version_key("9.9") < version_key("10.0")
    assert version_key("1.2.3-beta") < version_key("1.2.3")
    assert version_key("2026.03") == version_key("2026.3")


@pytest.mark.parametrize(
    "url",
    [
        "http://vendor.test/a",
        "https://vendor.test.evil/a",
        "https://vendor.test@evil.test/a",
        "https://vendor.test:444/a",
        "file:///a",
    ],
)
def test_url_reject(url):
    with pytest.raises(ValueError):
        validate_url(url, ["vendor.test"])


def test_url_accept():
    assert validate_url("https://vendor.test/a", ["vendor.test"])


def test_url_host_validation_can_be_disabled():
    assert validate_url("https://vendor.test/a", ["other.test"], disable_host_validation=True)


def test_checksums():
    sha = hashlib.sha256(b"hello").hexdigest()
    verify_checksum(sha, sha.upper())
    with pytest.raises(ValueError):
        verify_checksum(sha, "0" * 64)
    with pytest.raises(ValueError):
        protect_checksum(sha, "0" * 64)
    protect_checksum(sha, "0" * 64, True)


@pytest.mark.parametrize(
    "entry",
    [
        "../evil",
        "/etc/evil",
        "C:/evil",
        "a/../../evil",
        "a\\..\\..\\evil",
        "file:stream",
    ],
)
def test_bad_zip(tmp_path, entry):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(entry, "bad")
    with pytest.raises(ValueError):
        safe_extract_zip(archive, tmp_path / "out")


def test_good_zip(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("folder/file", "ok")
    safe_extract_zip(archive, tmp_path / "out")
    assert (tmp_path / "out/folder/file").read_text() == "ok"


def test_github():
    def release(v, pre=False):
        return {
            "tag_name": v,
            "prerelease": pre,
            "assets": [
                {
                    "name": "app-x64.exe",
                    "browser_download_url": "https://github.com/a/b/releases/a",
                },
                {
                    "name": "app-arm64.exe",
                    "browser_download_url": "https://github.com/wrong",
                },
            ],
        }

    source = {"asset_regex": "app-{architecture}\\.exe", "architecture": "x64"}
    r = select_github([release("v9.0"), release("v10.0"), release("v11.0-beta", True)], source)
    assert r.version == "10.0" and r.url.endswith("/a")
    with pytest.raises(ValueError):
        select_github([release("v1.0")], {"asset_regex": ".*"})


def test_metadata_and_scripts(tmp_path):
    p = load_catalog(ROOT / "catalog/packages.yaml")[0]
    root = generate(
        p,
        Release("143.0", "https://archive.mozilla.org/a"),
        "143.0",
        tmp_path / "source",
        ROOT / "builder/templates",
        ROOT / "catalog/overrides",
    )
    c = tomllib.loads((root / "OPSI/control.toml").read_text())
    assert c["Product"]["version"] == "143.0" and c["Package"]["version"] == "1"
    for name in ("setup", "uninstall"):
        text = (root / f"CLIENT_DATA/{name}.opsiscript").read_text()
        assert (
            "%ScriptPath%" in text
            and "getLastExitCode" in text
            and "isFatalError" in text
            and "3010" in text
        )
    assert "InstalledVersion" in (root / "CLIENT_DATA/install.ps1").read_text()
    assert "Quiet" in (root / "CLIENT_DATA/uninstall.ps1").read_text()


def test_state_migration(tmp_path):
    path = tmp_path / "packages.json"
    atomic_json(path, {"auto-test": {"sha256": "a" * 64, "upstream_version": "1.0"}})
    state = read_state(path)
    assert state["schema_version"] == 2 and state["checksums"]["auto-test@1.0"] == "a" * 64


def test_retention_and_duplicates(tmp_path):
    for name in [
        "auto-a_9.0-1.opsi",
        "auto-a_10.0-1.opsi",
        "auto-a_10.0-2.opsi",
        "auto-b_1.0-1.opsi",
    ]:
        (tmp_path / name).touch()
    assert [p.name for p in obsolete(tmp_path, 2)] == ["auto-a_9.0-1.opsi"]
    assert len(inventory(tmp_path, "auto-a")) == 3
    with pytest.raises(ValueError):
        obsolete(tmp_path, 0)


def test_mock_mozilla():
    p = load_catalog(ROOT / "catalog/packages.yaml")[0]

    class HTTP:
        def json(self, url, hosts):
            return {"LATEST_FIREFOX_VERSION": "143.0"}

        def get(self, *args):
            return ("a" * 64 + "  win64/en-US/Firefox Setup 143.0.exe").encode()

    r = resolve(p, HTTP())
    assert r.version == "143.0" and "/143.0/" in r.url
