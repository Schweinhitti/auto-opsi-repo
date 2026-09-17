from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"


def _assert_issue_form(filename, expected_label):
    """Assert that an issue form has required input and its expected label."""
    path = GITHUB / "ISSUE_TEMPLATE" / filename
    assert path.is_file(), f"required issue form {filename} must exist"
    form = yaml.safe_load(path.read_text())

    assert isinstance(form.get("name"), str) and form["name"].strip()
    assert isinstance(form.get("description"), str) and form["description"].strip()
    assert isinstance(form.get("body"), list) and form["body"]
    assert expected_label in form.get("labels", []), (
        f"{filename} must apply the existing {expected_label} label"
    )
    assert any(
        item.get("type") in {"input", "textarea", "dropdown"}
        and item.get("validations", {}).get("required") is True
        for item in form["body"]
    ), f"{filename} must contain at least one required user input"


def test_bug_report_form_has_required_structure_and_label():
    """Require a structured bug report form with the bug label."""
    _assert_issue_form("bug_report.yml", "bug")


def test_feature_request_form_has_required_structure_and_label():
    """Require a structured feature request form with the enhancement label."""
    _assert_issue_form("feature_request.yml", "enhancement")


def test_issue_template_config_disables_blanks_and_links_private_reports():
    """Disable blank issues and direct vulnerability reports to advisories."""
    path = GITHUB / "ISSUE_TEMPLATE/config.yml"
    assert path.is_file(), "required issue template config.yml must exist"
    config = yaml.safe_load(path.read_text())

    assert config["blank_issues_enabled"] is False
    links = config.get("contact_links", [])
    assert any(
        isinstance(link.get("url"), str)
        and link["url"].startswith("https://github.com/")
        and link["url"].endswith("/security/advisories/new")
        for link in links
    ), "issue template config must link to GitHub private vulnerability reporting"
