from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ghcr_workflow_separates_pull_request_build_from_publish():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ghcr-publish.yml").read_text())
    jobs = workflow["jobs"]

    pull_request_build = jobs["build-pr"]
    assert pull_request_build["if"] == "github.event_name == 'pull_request'"
    assert pull_request_build["permissions"] == {"contents": "read"}
    pull_request_steps = pull_request_build["steps"]
    assert not any("docker/login-action@" in step.get("uses", "") for step in pull_request_steps)
    pull_request_image_build = next(
        step for step in pull_request_steps if step.get("name") == "Build Docker image"
    )
    assert pull_request_image_build["with"]["push"] is False

    publisher = jobs["publish"]
    assert publisher["if"] == "github.event_name == 'push'"
    assert publisher["permissions"] == {"contents": "read", "packages": "write"}
    publish_steps = publisher["steps"]
    assert any("docker/login-action@" in step.get("uses", "") for step in publish_steps)
    publish_image_build = next(
        step for step in publish_steps if step.get("name") == "Build and push Docker image"
    )
    assert publish_image_build["with"]["push"] is True
