from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"


def test_release_config_has_parseable_categories_and_exclusions():
    """Require valid release-note categories, labels, and exclusions."""
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


def test_release_config_uses_a_single_final_catch_all_category():
    """Keep unmatched changes visible without shadowing specific categories."""
    config = yaml.safe_load((GITHUB / "release.yml").read_text())
    categories = config["changelog"]["categories"]
    wildcard_categories = [category for category in categories if "*" in category["labels"]]
    assert wildcard_categories == [categories[-1]]
    assert categories[-1]["labels"] == ["*"]

    specific_labels = [label for category in categories[:-1] for label in category["labels"]]
    assert len(specific_labels) == len(set(specific_labels)), (
        "specific release-note labels must not appear in multiple categories"
    )
