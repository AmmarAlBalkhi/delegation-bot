from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ISSUE_TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"


def _load_front_matter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise AssertionError(f"{path} is missing front matter")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise AssertionError(f"{path} front matter is not a mapping")
    return data


class GitHubMetadataTests(unittest.TestCase):
    def test_label_source_contains_public_triage_labels(self) -> None:
        labels = yaml.safe_load((ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))

        self.assertIsInstance(labels, list)
        names = {label["name"] for label in labels}
        self.assertTrue(
            {
                "adapter",
                "eval",
                "playbook",
                "trust-layer",
                "live-gate",
                "github-app",
                "good first issue",
                "roadmap",
            }.issubset(names)
        )

    def test_issue_template_labels_exist_in_label_source(self) -> None:
        labels = yaml.safe_load((ROOT / ".github" / "labels.yml").read_text(encoding="utf-8"))
        known_labels = {label["name"] for label in labels}

        for path in ISSUE_TEMPLATE_DIR.glob("*.md"):
            front_matter = _load_front_matter(path)
            for label in front_matter.get("labels", []):
                self.assertIn(label, known_labels, f"{path.name} uses unknown label {label}")

    def test_issue_template_chooser_points_to_curated_roadmap(self) -> None:
        config = yaml.safe_load((ISSUE_TEMPLATE_DIR / "config.yml").read_text(encoding="utf-8"))

        self.assertFalse(config["blank_issues_enabled"])
        contact_names = {link["name"] for link in config["contact_links"]}
        self.assertIn("Public roadmap issue drafts", contact_names)

    def test_public_contribution_docs_exist(self) -> None:
        for relative_path in [
            "docs/public-roadmap-issues.md",
            "docs/issue-labels.md",
            "docs/github-app-installation.md",
        ]:
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
