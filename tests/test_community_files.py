from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"


def test_required_community_files_exist():
    """Require the standard community health files under ``.github``."""
    required = [
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "SUPPORT.md",
        "CODEOWNERS",
        "pull_request_template.md",
    ]
    missing = [filename for filename in required if not (GITHUB / filename).is_file()]
    assert not missing, f"required community files must exist under .github: {missing}"


def test_codeowners_covers_repository_and_sensitive_paths():
    """Require maintainer review globally and for security-sensitive areas."""
    rules = {}
    for line in (GITHUB / "CODEOWNERS").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pattern, *owners = line.split()
            rules[pattern] = owners

    required_patterns = {
        "*",
        "/.github/",
        "/.github/workflows/",
        "/builder/",
        "/catalog/",
        "/docker-compose.yml",
        "/scripts/",
    }
    assert required_patterns <= set(rules)
    assert all(rules[pattern] == ["@Schweinhitti"] for pattern in required_patterns)


def test_pull_request_template_requires_risk_and_validation_evidence():
    """Prompt contributors for validation, security, and client acceptance evidence."""
    template = (GITHUB / "pull_request_template.md").read_text()
    headings = {
        line.removeprefix("## ").strip()
        for line in template.splitlines()
        if line.startswith("## ")
    }
    assert {"Summary", "Validation", "Security and Redistribution", "Windows Acceptance"} <= (
        headings
    )
    assert template.count("- [ ]") >= 4
    assert "No secrets" in template
