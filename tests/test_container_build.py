from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_compose_passes_opsi_base_image_build_arg():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    arg = compose["services"]["repo-builder"]["build"]["args"]["OPSI_BASE_IMAGE"]
    assert arg == "${OPSI_BASE_IMAGE:-uibmz/opsi-server:4.3}"


def test_builder_dockerfile_uses_opsi_base_image_arg_for_from():
    lines = (ROOT / "builder/Dockerfile").read_text().splitlines()
    arg_idx = next(i for i, line in enumerate(lines) if line.startswith("ARG OPSI_BASE_IMAGE="))
    from_idx = next(i for i, line in enumerate(lines) if line.startswith("FROM "))
    assert arg_idx < from_idx
    assert lines[arg_idx] == "ARG OPSI_BASE_IMAGE=uibmz/opsi-server:4.3"
    assert lines[from_idx] == "FROM ${OPSI_BASE_IMAGE}"
