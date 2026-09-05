"""Tests for the release automation's own configuration.

release-please computes the next version from the last released one, which
it reads from .release-please-manifest.json -- not from VERSION. When the
two disagree the bot silently releases from the wrong base, and the first
symptom is a tag that skips or repeats a version. Nothing else in the repo
checks that, so it is checked here.

The workflow files are asserted at TEXT level: parsing YAML would need a
third-party import, which rule-stdlib-only-py39 forbids. These assertions
are therefore about presence, not semantics -- they catch a workflow that
lost its test run or its recovery path, not one whose expressions are
subtly wrong.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "release-please-config.json"
MANIFEST = ROOT / ".release-please-manifest.json"
WORKFLOWS = ROOT / ".github" / "workflows"


class ManifestTracksTheVersionFile(unittest.TestCase):
    def test_the_manifest_and_version_agree(self):
        """release-please bumps both in the same release PR, so they drift
        apart only when a human edits one by hand."""
        recorded = json.loads(MANIFEST.read_text(encoding="utf-8"))["."]
        version = (ROOT / "VERSION").read_text(encoding="utf-8").split()[0]

        self.assertEqual(recorded, version)

    def test_the_version_is_a_plain_semver(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").split()[0]

        self.assertRegex(version, r"^\d+\.\d+\.\d+$")


class ConfigPointsAtThisRepositorysFiles(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_the_version_file_is_ours(self):
        """`simple` defaults to version.txt; this repo's version has always
        lived in VERSION, which init.py reads to stamp every manifest."""
        self.assertEqual(self.config["release-type"], "simple")
        self.assertEqual(self.config["version-file"], "VERSION")
        self.assertTrue((ROOT / self.config["version-file"]).is_file())

    def test_tags_stay_bare_vX_Y_Z(self):
        """Consumers and upgrade.py's --to both spell versions as vX.Y.Z;
        a component prefix would break every existing tag reference."""
        self.assertFalse(self.config["include-component-in-tag"])

    def test_the_changelog_path_exists(self):
        path = self.config["packages"]["."]["changelog-path"]

        self.assertTrue((ROOT / path).is_file())


class WorkflowsCarryTheirLoadBearingParts(unittest.TestCase):
    def _text(self, name):
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_the_test_workflow_runs_the_real_suite(self):
        text = self._text("test.yml")

        self.assertIn("./run_tests.sh", text)
        self.assertIn("pull_request", text)
        # The floor the harness promises consumers.
        self.assertIn('"3.9"', text)

    def test_the_release_workflow_verifies_before_it_publishes(self):
        """The tag is what a consumer installs; the asset job must prove it
        rather than trusting the release PR's own checks."""
        text = self._text("release-please.yml")

        self.assertIn("./run_tests.sh", text)
        self.assertIn("tools/build_release.py", text)

    def test_the_release_workflow_keeps_its_recovery_path(self):
        """release-please reports release_created: false once a release
        exists, so a failed asset upload can only be retried by dispatch."""
        text = self._text("release-please.yml")

        self.assertIn("workflow_dispatch", text)
        self.assertIn("inputs.tag", text)
        self.assertIn("!cancelled()", text)

    def test_the_release_workflow_names_the_config_files(self):
        text = self._text("release-please.yml")

        self.assertIn("release-please-config.json", text)
        self.assertIn(".release-please-manifest.json", text)


if __name__ == "__main__":
    unittest.main()
