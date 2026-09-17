import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow():
    """Load the GHCR publication workflow."""
    return yaml.safe_load((ROOT / ".github/workflows/ghcr-publish.yml").read_text())


def test_ghcr_pull_request_job_is_build_only():
    """Keep pull-request image builds read-only and unpublished."""
    pull_request_build = _workflow()["jobs"]["build-pr"]
    assert pull_request_build["if"] == "github.event_name == 'pull_request'"
    assert pull_request_build["permissions"] == {"contents": "read"}

    steps = pull_request_build["steps"]
    assert not any("docker/login-action@" in step.get("uses", "") for step in steps)
    image_build = next(step for step in steps if step.get("name") == "Build Docker image")
    assert image_build["with"]["push"] is False


def test_ghcr_publish_job_has_provenance_permissions():
    """Grant the publisher only the permissions needed for provenance and packages."""
    publisher = _workflow()["jobs"]["publish"]
    assert publisher["if"] == "github.event_name == 'push'"
    assert publisher["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
        "packages": "write",
    }, "GHCR publisher must grant only contents read and provenance/package write permissions"


def test_ghcr_publish_attests_the_pushed_image_digest():
    """Attest the digest produced by the image publication step."""
    steps = _workflow()["jobs"]["publish"]["steps"]
    assert any("docker/login-action@" in step.get("uses", "") for step in steps)

    image_build = next(step for step in steps if step.get("name") == "Build and push Docker image")
    assert image_build["with"]["push"] is True
    assert image_build.get("id"), "GHCR publish build step must have an id for digest consumption"

    provenance = next(
        (step for step in steps if step.get("uses", "").startswith("actions/attest-build-provenance@")),
        None,
    )
    assert provenance is not None, "GHCR publisher must attest build provenance"
    assert re.fullmatch(r"actions/attest-build-provenance@[0-9a-f]{40}", provenance["uses"])
    assert provenance["with"]["subject-digest"] == (
        f"${{{{ steps.{image_build['id']}.outputs.digest }}}}"
    )


def test_defender_workflow_has_permissions_for_sarif_upload():
    """Allow the Defender workflow to upload its SARIF results."""
    workflow = yaml.safe_load((ROOT / ".github/workflows/defender-for-devops.yml").read_text())
    msdo_job = workflow["jobs"]["MSDO"]
    assert msdo_job["permissions"] == {
        "actions": "read",
        "contents": "read",
        "security-events": "write",
    }
