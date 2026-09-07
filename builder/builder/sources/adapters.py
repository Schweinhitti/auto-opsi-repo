"""Metadata-only adapters. Every installer URL is separately allowlisted."""

import re
from dataclasses import replace
from urllib.parse import quote, unquote, urlparse

import yaml

from ..download import validate_url
from ..models import Release
from ..versions import version_key


def select_github(releases, source):
    candidates = [
        r
        for r in releases
        if not r.get("draft") and (source.get("prerelease", False) or not r.get("prerelease"))
    ]
    if source.get("release_type", "latest") == "tag":
        candidates = [r for r in candidates if r["tag_name"] == source["tag"]]
    parsed = []
    for r in candidates:
        raw = r["tag_name"]
        match = re.search(source.get("version_regex", r"v?(\d+(?:\.\d+)+(?:[-+][\w.]+)?)"), raw)
        if not match:
            continue
        version = match.group(1)
        assets = [
            a
            for a in r["assets"]
            if re.fullmatch(
                source["asset_regex"].replace("{architecture}", source.get("architecture", "x64")),
                a["name"],
            )
        ]
        if len(assets) > 1:
            raise ValueError("Ambiguous GitHub installer assets")
        parsed.append((version_key(version), version, assets[0] if assets else None))
    if not parsed:
        raise ValueError("No matching stable GitHub installer")
    _, version, asset = max(parsed, key=lambda x: x[0])
    if asset is None:
        raise ValueError(
            "Newest release has no matching installer; refusing stale release fallback"
        )
    digest = asset.get("digest") or ""
    return Release(
        version,
        asset["browser_download_url"],
        digest[7:] if digest.startswith("sha256:") else None,
        filename=asset["name"],
    )


def field(data, path):
    for part in path.split("."):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def resolve(package, http):
    s = package["source"]
    kind = s["type"]
    arch = package["architecture"][0]
    hosts = s["allowed_hosts"]
    if kind == "github_release":
        repo = s.get("repo") or s["owner"] + "/" + s["repository"]
        if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
            raise ValueError("Invalid GitHub repo")
        releases = http.json(
            f"https://api.github.com/repos/{repo}/releases?per_page=30",
            ["api.github.com"],
        )
        result = select_github(releases, s)
        if s.get("checksum_asset_regex"):
            release = next(
                r
                for r in releases
                if any(a["browser_download_url"] == result.url for a in r["assets"])
            )
            sums = [
                a for a in release["assets"] if re.fullmatch(s["checksum_asset_regex"], a["name"])
            ]
            if len(sums) != 1:
                raise ValueError("No unique checksum asset")
            checksum_text = http.get(sums[0]["browser_download_url"], hosts).decode()
            matches = re.findall(
                s.get("checksum_line_regex", r"^([a-fA-F0-9]{64})\s+\*?{filename}\s*$").replace(
                    "{filename}", re.escape(result.filename)
                ),
                checksum_text,
                re.MULTILINE,
            )
            if len(matches) != 1:
                raise ValueError("Checksum asset lacks selected installer")
            if result.sha256 and result.sha256.lower() != matches[0].lower():
                raise ValueError("GitHub checksum sources disagree")
            result = replace(result, sha256=matches[0].lower())
    elif kind == "mozilla":
        data = http.json(s["version_url"], hosts)
        version = str(field(data, s["version_field"]))
        result = Release(
            version,
            s["download_url_template"].format(version=version, architecture=arch),
        )
    elif kind == "microsoft":
        data = http.json(s["api_url"], hosts)
        result = Release(data["productVersion"], data["url"], data.get("sha256hash"))
    elif kind in ("vendor_json_api", "adoptium"):
        data = http.json(s["api_url"].format(java_version=s.get("java_version", "")), hosts)
        result = Release(
            str(field(data, s["version_field"])),
            str(field(data, s["url_field"])),
            str(field(data, s["sha256_field"])) if s.get("sha256_field") else None,
            detection_version=str(field(data, s["detection_version_field"]))
            if s.get("detection_version_field")
            else None,
        )
    elif kind in ("direct_url", "videolan", "documentfoundation"):
        text = http.get(s["version_url"], hosts).decode("utf-8")
        matches = re.findall(s["version_regex"], text)
        versions = [m if isinstance(m, str) else m[0] for m in matches]
        if s.get("track"):
            versions = [v for v in versions if v.startswith(s["track"] + ".")]
        if not versions:
            raise ValueError("No upstream versions found")
        version = max(versions, key=version_key)
        url = s["download_url_template"].format(
            version=version, version_compact=version.replace(".", ""), architecture=arch
        )
        sha = None
        if s.get("sha256_url_template"):
            sums = http.get(s["sha256_url_template"].format(version=version), hosts).decode()
            match = re.search(r"\b([a-fA-F0-9]{64})\b", sums)
            if not match:
                raise ValueError("No published SHA256 found")
            sha = match.group(1)
        result = Release(version, url, sha)
    elif kind == "winget_manifest":
        identifier = s["package_identifier"]
        base = "manifests/" + identifier[0].lower() + "/" + identifier.replace(".", "/")
        api = "https://api.github.com/repos/microsoft/winget-pkgs/contents/" + base
        entries = http.json(api, ["api.github.com"])
        versions = []
        for e in entries:
            if e["type"] == "dir":
                try:
                    v = version_key(e["name"])
                    if not v.is_prerelease and (
                        not s.get("track") or e["name"].startswith(s["track"] + ".")
                    ):
                        versions.append((v, e["name"]))
                except ValueError:
                    pass
        if not versions:
            raise ValueError("No stable WinGet versions")
        version = max(versions)[1]
        url = (
            "https://raw.githubusercontent.com/microsoft/winget-pkgs/master/"
            + base
            + "/"
            + quote(version, safe="")
            + "/"
            + identifier
            + ".installer.yaml"
        )
        data = yaml.safe_load(http.get(url, ["raw.githubusercontent.com"]))
        choices = []
        for entry in data["Installers"]:
            merged = {**data, **entry}
            if (
                merged["Architecture"] == arch
                and merged.get("InstallerType")
                in s.get("installer_types", [package["installer"]["type"]])
                and merged.get("Scope", "machine") == "machine"
            ):
                choices.append(merged)
        urls = {i["InstallerUrl"]: i for i in choices}
        if len(urls) != 1:
            raise ValueError("No unique machine-scope WinGet installer")
        item = next(iter(urls.values()))
        result = Release(version, item["InstallerUrl"], item["InstallerSha256"])
    else:
        raise ValueError("Unsupported source: " + kind)
    validate_url(result.url, hosts)
    if s.get("allowed_url_prefixes") and not any(
        result.url.startswith(prefix) for prefix in s["allowed_url_prefixes"]
    ):
        raise ValueError("Installer URL outside official project path")
    if s.get("checksum_url_template"):
        checksum_url = s["checksum_url_template"].format(version=result.version)
        filename = s.get(
            "checksum_filename_template",
            unquote(urlparse(result.url).path.rsplit("/", 1)[-1]),
        ).format(version=result.version)
        sums = http.get(checksum_url, hosts).decode("utf-8")
        matches = []
        for line in sums.splitlines():
            m = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(.+)", line.strip())
            if m and m[2] == filename:
                matches.append(m[1].lower())
        if len(set(matches)) != 1:
            raise ValueError("No unique published checksum for selected installer")
        if result.sha256 and result.sha256.lower() != matches[0]:
            raise ValueError("Upstream checksum sources disagree")
        result = replace(result, sha256=matches[0])
    version_key(result.version)
    return result
