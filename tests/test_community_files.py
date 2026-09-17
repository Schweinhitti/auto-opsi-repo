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
