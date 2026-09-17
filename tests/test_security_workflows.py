from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def _load_required_workflow(filename):
    """Load a required security workflow by filename."""
    path = WORKFLOWS / filename
    assert path.exists(), f"required security workflow {filename} must exist"
    return yaml.safe_load(path.read_text())


def _triggers(workflow):
    """Return workflow triggers across YAML 1.1 and 1.2 parsers."""
    return workflow.get("on", workflow.get(True, {}))


def _steps(workflow):
    """Flatten the steps from every workflow job."""
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def _assert_main_branch_event(triggers, event):
    """Assert that an event is restricted to the main branch."""
    assert triggers[event]["branches"] == ["main"], f"{event} must target only main"


def test_dependency_review_runs_only_for_main_pull_requests():
    """Restrict dependency review to main-bound pull requests with read access."""
    workflow = _load_required_workflow("dependency-review.yml")
    triggers = _triggers(workflow)
    assert set(triggers) == {"pull_request"}
    _assert_main_branch_event(triggers, "pull_request")
    assert workflow["permissions"] == {"contents": "read"}

    review_step = next(
        step
        for step in _steps(workflow)
        if step.get("uses", "").startswith("actions/dependency-review-action@")
    )
    assert review_step["with"]["fail-on-severity"] == "high"


def test_scorecard_has_non_pr_triggers_and_job_scoped_permissions():
    """Run Scorecard only on trusted events with job-scoped permissions."""
    workflow = _load_required_workflow("scorecard.yml")
    triggers = _triggers(workflow)
    assert set(triggers) == {"push", "schedule", "workflow_dispatch"}
    _assert_main_branch_event(triggers, "push")
    assert triggers["schedule"], "Scorecard must run on a schedule"
    assert any(
        job.get("permissions")
        == {"contents": "read", "security-events": "write", "id-token": "write"}
        for job in workflow["jobs"].values()
    ), "Scorecard job must grant only contents read, security-events write, and id-token write"
