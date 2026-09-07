import hashlib
import os
import re
import stat
import subprocess
import time
import zipfile
from pathlib import Path, PureWindowsPath
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def validate_url(url, hosts):
    p = urlparse(url)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.port not in (None, 443)
    ):
        raise ValueError("Only credential-free HTTPS URLs are accepted")
    if not any(
        p.hostname.lower() == h.lower()
        or (h.startswith("*.") and p.hostname.lower().endswith(h[1:].lower()))
        for h in hosts
    ):
        raise ValueError(f"Untrusted source host: {p.hostname}")
    return url


class HTTP:
    def __init__(self):
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers["User-Agent"] = "opsi-auto-repo/1.0"
        self.session.verify = os.getenv("REQUESTS_CA_BUNDLE") or True

    def get(self, url, hosts, limit=8 * 1024 * 1024):
        chunks = []
        for chunk in self.stream(url, hosts, limit):
            chunks.append(chunk)
        return b"".join(chunks)

    def json(self, url, hosts):
        import json

        return json.loads(self.get(url, hosts))

    def stream(self, url, hosts, limit):
        start = time.monotonic()
        for _ in range(10):
            validate_url(url, hosts)
            headers = {}
            if urlparse(url).hostname == "api.github.com" and os.getenv("GITHUB_TOKEN"):
                headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                allow_redirects=False,
                timeout=(15, 90),
            )
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                response.close()
                continue
            with response:
                if response.status_code in (403, 429):
                    raise RuntimeError(
                        f"Upstream access/rate limit; retry next cycle (reset={response.headers.get('X-RateLimit-Reset', 'unknown')})"
                    )
                response.raise_for_status()
                if int(response.headers.get("Content-Length", 0)) > limit:
                    raise ValueError("Download exceeds size limit")
                size = 0
                for chunk in response.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > limit or time.monotonic() - start > 1800:
                        raise ValueError("Download exceeds size/time limit")
                    yield chunk
                return
        raise ValueError("Too many redirects")


def verify_checksum(actual, expected):
    if expected and (
        not re.fullmatch(r"[a-fA-F0-9]{64}", expected) or actual.lower() != expected.lower()
    ):
        raise ValueError("SHA256 verification FAILED")


def protect_checksum(previous, actual, allow=False):
    if previous and previous != actual and not allow:
        raise ValueError(
            "IMMUTABLE VERSION CHECKSUM CHANGED; refusing rebuild (ALLOW_CHANGED_CHECKSUM=false)"
        )


def safe_extract_zip(path, destination, limit=4 * 1024**3):
    destination = Path(destination)
    with zipfile.ZipFile(path) as archive:
        size = 0
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            size += info.file_size
            if (
                name.startswith("/")
                or ".." in Path(name).parts
                or PureWindowsPath(name).drive
                or ":" in name
                or stat.S_ISLNK(info.external_attr >> 16)
                or size > limit
            ):
                raise ValueError("Unsafe ZIP entry")
        archive.extractall(destination)


def _download_once(http, release, package, destination):
    kind = package["installer"]["type"]
    path = Path(destination) / ("installer." + kind)
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("wb") as f:
            for chunk in http.stream(
                release.url,
                package["source"]["allowed_hosts"],
                int(os.getenv("MAX_DOWNLOAD_BYTES", str(2 * 1024**3))),
            ):
                f.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        verify_checksum(digest.hexdigest(), release.sha256)
        with path.open("rb") as f:
            magic = f.read(8)
        if (
            size < 1024
            or (kind == "exe" and not magic.startswith(b"MZ"))
            or (kind == "msi" and magic != bytes.fromhex("d0cf11e0a1b11ae1"))
            or (kind in ("zip", "msix") and not zipfile.is_zipfile(path))
        ):
            raise ValueError("Installer format/size validation failed")
        signature = "UNKNOWN"
        if kind in ("exe", "msi"):
            try:
                proc = subprocess.run(
                    ["osslsigncode", "verify", "-in", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if proc.returncode == 0:
                    signature = "SIGNED"
                elif "No signature found" in proc.stdout + proc.stderr:
                    signature = "UNSIGNED"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        return path, digest.hexdigest(), size, signature
    except Exception:
        path.unlink(missing_ok=True)
        raise


def download(http, release, package, destination):
    # Retry interrupted response bodies from scratch, never append partial installers.
    for attempt in range(3):
        try:
            return _download_once(http, release, package, destination)
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2**attempt)
