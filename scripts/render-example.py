#!/usr/bin/env python3
# ruff: noqa: E402
"""Render inspectable OPSI sources without downloading an installer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'builder'))
from builder.catalog import load_catalog
from builder.models import Release
from builder.opsi import generate
from builder.versions import normalize

product = next(p for p in load_catalog(ROOT / 'catalog/packages.yaml') if p['id'] == 'firefox')
version = '155.0.1'
destination = ROOT / 'work/example-source/auto-firefox'
if destination.exists():
    raise SystemExit('Example already exists: ' + str(destination))
generate(product, Release(version, 'https://archive.mozilla.org/'), normalize(version),
         destination, ROOT / 'builder/templates', ROOT / 'catalog/overrides')
print(destination)
print('Source example only: add a verified installer before packaging. No dummy payload is provided.')
