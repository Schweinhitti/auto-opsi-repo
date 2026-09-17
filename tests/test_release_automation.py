from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"


def test_release_config_has_parseable_categories_and_exclusions():
    path = GITHUB / "release.yml"
    assert path.is_file(), "required release.yml must exist"
    config = yaml.safe_load(path.read_text())

    excluded_labels = config["changelog"]["exclude"]["labels"]
    assert isinstance(excluded_labels, list) and excluded_labels
    assert all(isinstance(label, str) and label for label in excluded_labels)

    categories = config["changelog"]["categories"]
    assert isinstance(categories, list) and categories
    assert all(
        isinstance(category.get("title"), str)
        and category["title"].strip()
        and isinstance(category.get("labels"), list)
        and category["labels"]
        and all(isinstance(label, str) and label for label in category["labels"])
        for category in categories
    )
    configured_labels = {label for category in categories for label in category["labels"]}
    assert configured_labels <= {
        "*",
        "bug",
        "dependencies",
        "documentation",
        "enhancement",
        "github_actions",
    }, "release-note categories must use labels configured in the repository"
