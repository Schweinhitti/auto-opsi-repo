from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_exists_and_has_core_steps():
    workflow_path = ROOT / ".github/workflows/ci.yml"
    assert workflow_path.exists()

    workflow = yaml.safe_load(workflow_path.read_text())
    assert workflow["name"] == "CI"
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "push" in triggers
    assert "pull_request" in triggers

    steps = workflow["jobs"]["test"]["steps"]
    uses = [step.get("uses") for step in steps if "uses" in step]
    runs = [step.get("run", "") for step in steps]

    assert any(use and use.startswith("actions/checkout@") for use in uses)
    assert any(use and use.startswith("actions/setup-python@") for use in uses)
    assert any("ruff check ." in cmd for cmd in runs)
    assert any("pytest -q" in cmd for cmd in runs)

    assert workflow["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    setup_python = next(step for step in steps if (step.get("uses") or "").startswith("actions/setup-python@"))
    assert setup_python["with"]["cache"] == "pip"
    assert setup_python["with"]["cache-dependency-path"] == "builder/requirements.txt"


def test_dependabot_config_covers_pip_and_actions():
    dependabot_path = ROOT / ".github/dependabot.yml"
    assert dependabot_path.exists()

    config = yaml.safe_load(dependabot_path.read_text())
    assert config["version"] == 2

    updates = config["updates"]
    targets = {(item["package-ecosystem"], item["directory"]) for item in updates}

    assert ("pip", "/") in targets
    assert ("pip", "/builder") in targets
    assert ("github-actions", "/") in targets
