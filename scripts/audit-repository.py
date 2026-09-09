#!/usr/bin/env python3
"""Read-only integrity audit of published packages, provenance and metadata."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'repository'
metadata = json.loads((root / 'packages.json').read_text())
count = 0
for artifact in sorted(root.glob('*.opsi')):
    proof = json.loads(Path(str(artifact) + '.provenance.json').read_text())
    with artifact.open('rb') as f:
        assert hashlib.file_digest(f, 'sha256').hexdigest() == proof['package_sha256'], artifact
    with artifact.open('rb') as f:
        assert hashlib.file_digest(f, 'md5').hexdigest() == Path(str(artifact)+'.md5').read_text().strip(), artifact
    assert Path(str(artifact) + '.zsync').stat().st_size > 0, artifact
    count += 1
for product, versions in metadata['packages'].items():
    for version, entry in versions.items():
        path = root / entry['url']
        assert path.is_file() and path.stat().st_size == entry['size'], entry
        assert product == entry['product_id'] and version == entry['product_version']+'-'+entry['package_version']
print(f'Audit passed: {count} archives, SHA256/MD5/zsync/provenance and {len(metadata["packages"])} metadata products')
