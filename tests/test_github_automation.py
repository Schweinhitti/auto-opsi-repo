import re
import shlex
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
SHELL_ENTRYPOINTS = {
    "add-package.sh",
    "builder/entrypoint.sh",
    "helper/build.sh",
    "helper/cleanup.sh",
    "helper/dry-run.sh",
    "helper/logs.sh",
    "helper/run.sh",
    "helper/status.sh",
    "helper/test.sh",
}


def _load_yaml(path):
    """Load YAML from a repository path."""
    return yaml.safe_load(path.read_text())


def _triggers(workflow):
    """Return workflow triggers across YAML 1.1 and 1.2 parsers."""
    return workflow.get("on", workflow.get(True, {}))


def _workflow_uses(value):
    """Yield every action reference from a nested workflow value."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "uses":
                yield child
            else:
                yield from _workflow_uses(child)
    elif isinstance(value, list):
        for child in value:
            yield from _workflow_uses(child)


def _workflow_paths():
    """Return all YAML workflow paths in deterministic order."""
    return sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")))


def _ci_runs():
    """Return the shell commands configured for the CI test job."""
    workflow = _load_yaml(WORKFLOWS / "ci.yml")
    return [step.get("run", "") for step in workflow["jobs"]["test"]["steps"]]


def test_ci_workflow_exists_and_has_core_contract():
    """Require CI triggers, permissions, concurrency, checkout, and Python setup."""
    workflow_path = WORKFLOWS / "ci.yml"
    assert workflow_path.exists(), "CI workflow must exist"

    workflow = _load_yaml(workflow_path)
    assert workflow["name"] == "CI"
    assert {"push", "pull_request"} <= set(_triggers(workflow))
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": True,
    }

    steps = workflow["jobs"]["test"]["steps"]
    uses = [step["uses"] for step in steps if "uses" in step]
    assert any(use.startswith("actions/checkout@") for use in uses)
    setup_python = next(use for use in steps if use.get("uses", "").startswith("actions/setup-python@"))
    assert setup_python["with"]["cache"] == "pip"
    assert setup_python["with"]["cache-dependency-path"] == "builder/requirements.txt"


def test_ci_verifies_action_pins_and_version_comments():
    """Configure pinact to check immutable pins and their release comments."""
    workflow = _load_yaml(WORKFLOWS / "ci.yml")
    pinact = next(
        step
        for step in workflow["jobs"]["test"]["steps"]
        if step.get("uses", "").startswith("suzuki-shunsuke/pinact-action@")
    )
    assert pinact["with"] == {"fix": "false", "verify": "true"}


def _assert_ci_runs(command):
    """Assert that the CI test job includes a shell command."""
    assert any(command in run for run in _ci_runs()), f"CI must run `{command}`"


def test_ci_compiles_python_sources():
    """Compile Python sources during CI."""
    _assert_ci_runs("python -m compileall -q builder scripts tests")


def test_ci_runs_ruff():
    """Run Ruff during CI."""
    _assert_ci_runs("ruff check .")


def test_ci_runs_pytest():
    """Run the pytest suite during CI."""
    _assert_ci_runs("pytest -q")


def test_ci_validates_docker_compose():
    """Validate the Docker Compose configuration during CI."""
    _assert_ci_runs("docker compose config --quiet")


def test_ci_shell_syntax_check_covers_tracked_shell_entrypoints():
    """Syntax-check every tracked shell entry point during CI."""
    syntax_checks = [shlex.split(run) for run in _ci_runs() if "bash -n" in run]
    assert len(syntax_checks) == 1, "CI must have one bash -n command for tracked shell scripts"
    assert syntax_checks[0][:2] == ["bash", "-n"]
    assert SHELL_ENTRYPOINTS <= set(syntax_checks[0][2:]), (
        "CI bash -n command must cover every tracked shell entrypoint and helper"
    )


def test_dependabot_targets_exact_maintained_manifests():
    """Limit Dependabot to manifests maintained by the repository."""
    config = _load_yaml(ROOT / ".github/dependabot.yml")
    assert config["version"] == 2

    targets = {(item["package-ecosystem"], item["directory"]) for item in config["updates"]}
    assert targets == {
        ("pip", "/builder"),
        ("github-actions", "/"),
        ("docker", "/builder"),
    }, "Dependabot must not target root pip because no root Python manifest exists"


def _assert_dependabot_groups_minor_and_patch(ecosystem, directory):
    """Assert that a Dependabot target groups minor and patch updates."""
    config = _load_yaml(ROOT / ".github/dependabot.yml")
    update = next(
        item
        for item in config["updates"]
        if (item["package-ecosystem"], item["directory"]) == (ecosystem, directory)
    )
    grouped_update_types = {
        frozenset(group["update-types"]) for group in update.get("groups", {}).values()
    }
    assert frozenset({"minor", "patch"}) in grouped_update_types, (
        f"Dependabot target {ecosystem}:{directory} must group minor and patch updates"
    )


def test_dependabot_groups_builder_pip_minor_and_patch_updates():
    """Group minor and patch updates for builder Python dependencies."""
    _assert_dependabot_groups_minor_and_patch("pip", "/builder")


def test_dependabot_groups_root_actions_minor_and_patch_updates():
    """Group minor and patch updates for repository actions."""
    _assert_dependabot_groups_minor_and_patch("github-actions", "/")


def test_dependabot_groups_builder_docker_minor_and_patch_updates():
    """Group minor and patch updates for the builder image."""
    _assert_dependabot_groups_minor_and_patch("docker", "/builder")


def test_dependabot_uses_existing_repository_labels():
    """Restrict Dependabot labels to labels that already exist."""
    config = _load_yaml(ROOT / ".github/dependabot.yml")
    allowed_labels = {"dependencies", "github_actions"}
    configured_labels = {
        label for update in config["updates"] for label in update.get("labels", [])
    }
    assert configured_labels <= allowed_labels, (
        "Dependabot labels must exist in the repository; ecosystem-specific labels are not configured"
    )


def test_workflow_actions_are_pinned_to_full_commit_sha():
    """Pin every workflow action to a full lowercase commit SHA."""
    violations = [
        f"{workflow_path.name}: {uses}"
        for workflow_path in _workflow_paths()
        for uses in _workflow_uses(_load_yaml(workflow_path))
        if not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", uses)
    ]
    assert not violations, f"workflow actions must use full lowercase commit SHAs: {violations}"


def test_workflows_do_not_use_pull_request_target():
    """Disallow privileged pull-request-target workflow triggers."""
    violations = [
        workflow_path.name
        for workflow_path in _workflow_paths()
        if "pull_request_target" in _triggers(_load_yaml(workflow_path))
    ]
    assert not violations, f"workflows must not use pull_request_target: {violations}"
