"""Tests for tools/build_release.py -- the release payload builder the
`assets` job of .github/workflows/release-please.yml runs against a tag.

The payload is what a consumer actually installs, so these tests assert its
CONTENTS, not just that a tarball appeared: a missing template or a missing
scripts/*.py file would produce a release that scaffolds a broken wiki, and
that defect is invisible until someone runs `init` from it.

`tools/` is deliberately not `scripts/`: init.py's copy_scripts() vendors
every scripts/*.py into each consumer wiki, so a build tool living there
would ship into every wiki and change every consumer's manifest.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_RELEASE = ROOT / "tools" / "build_release.py"

sys.path.insert(0, str(ROOT / "tools"))
import build_release  # noqa: E402


class PayloadContentsArePure(unittest.TestCase):
    """The decisions about what goes in the payload are pure: a path list
    and a refusal, both computable without touching a filesystem."""

    def test_payload_names_every_directory_a_wiki_needs(self):
        """A consumer wiki is assembled from these four trees plus the two
        entry points; dropping any one silently breaks `init`."""
        for required in ("scripts", "githooks", "templates", "init.py",
                         "upgrade.py", "VERSION", "bin"):
            self.assertIn(required, build_release.PAYLOAD_PATHS)

    def test_payload_excludes_what_a_consumer_never_runs(self):
        for excluded in ("tests", "docs", ".c3", "tools", "run_tests.sh"):
            self.assertNotIn(excluded, build_release.PAYLOAD_PATHS)

    def test_tag_and_version_must_agree(self):
        self.assertIsNone(build_release.version_mismatch("v1.2.0", "1.2.0"))
        message = build_release.version_mismatch("v1.3.0", "1.2.0")
        self.assertIn("v1.3.0", message)
        self.assertIn("1.2.0", message)

    def test_a_tag_without_the_v_prefix_is_refused(self):
        self.assertIsNotNone(build_release.version_mismatch("1.2.0", "1.2.0"))

    def test_archive_name_is_derived_from_the_version(self):
        self.assertEqual(build_release.archive_name("1.2.0"),
                         "wiki-harness-1.2.0.tar.gz")


class BuiltPayloadIsUsable(unittest.TestCase):
    """Builds the real payload from this checkout and inspects it. The
    tarball is the artifact a consumer downloads, so it is checked as a
    tarball, not as the directory it was made from."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        out = Path(cls._tmp.name)
        version = (ROOT / "VERSION").read_text(encoding="utf-8").split()[0]
        result = subprocess.run(
            [sys.executable, str(BUILD_RELEASE), "--tag", f"v{version}",
             "--out-dir", str(out)],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        cls.version = version
        cls.archive = out / build_release.archive_name(version)
        cls.checksum = Path(str(cls.archive) + ".sha256")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _members(self):
        with tarfile.open(self.archive) as tar:
            return sorted(tar.getnames())

    def test_the_archive_and_its_checksum_exist(self):
        self.assertTrue(self.archive.is_file())
        self.assertTrue(self.checksum.is_file())

    def test_the_checksum_matches_the_archive(self):
        recorded = self.checksum.read_text(encoding="utf-8").split()[0]
        actual = hashlib.sha256(self.archive.read_bytes()).hexdigest()

        self.assertEqual(recorded, actual)

    def test_every_member_sits_under_one_top_level_directory(self):
        """Unpacking must never scatter files into the caller's cwd, and
        the launcher resolves the payload root by name."""
        prefix = f"wiki-harness-{self.version}"
        for name in self._members():
            self.assertTrue(name == prefix or name.startswith(prefix + "/"),
                            f"{name} escapes {prefix}/")

    def test_the_entry_points_and_every_vendored_tree_are_present(self):
        names = self._members()
        prefix = f"wiki-harness-{self.version}"

        for expected in (f"{prefix}/init.py", f"{prefix}/upgrade.py",
                         f"{prefix}/bin/wiki-harness",
                         f"{prefix}/VERSION", f"{prefix}/RELEASE.json",
                         f"{prefix}/scripts/lint.py",
                         f"{prefix}/scripts/manifest.py",
                         f"{prefix}/githooks/pre-commit",
                         f"{prefix}/githooks/commit-msg",
                         f"{prefix}/templates/AGENTS.root.md.tmpl"):
            self.assertIn(expected, names)

    def test_every_scripts_py_and_template_ships(self):
        """init.py discovers scripts/*.py and templates off disk, so a file
        present in the repo but absent from the payload scaffolds a wiki
        whose manifest records a path that is not there."""
        names = set(self._members())
        prefix = f"wiki-harness-{self.version}"

        for source in sorted((ROOT / "scripts").glob("*.py")):
            self.assertIn(f"{prefix}/scripts/{source.name}", names)
        for source in sorted((ROOT / "templates").iterdir()):
            if source.is_file():
                self.assertIn(f"{prefix}/templates/{source.name}", names)

    def test_the_payload_carries_no_tests_or_governance(self):
        for name in self._members():
            for excluded in ("/tests/", "/docs/", "/.c3/", "/tools/"):
                self.assertNotIn(excluded, name)

    def test_release_json_records_the_provenance_git_would_have(self):
        """An unpacked tarball has no .git, so init.py's read_source_*
        edges have nothing to ask. RELEASE.json is what replaces them."""
        with tarfile.open(self.archive) as tar:
            handle = tar.extractfile(f"wiki-harness-{self.version}/RELEASE.json")
            release = json.loads(handle.read().decode("utf-8"))

        self.assertEqual(release["version"], self.version)
        self.assertEqual(release["tag"], f"v{self.version}")
        self.assertRegex(release["commit"], r"^[0-9a-f]{40}$")
        self.assertIn("wiki-harness", release["source_url"])

    def test_the_build_is_reproducible(self):
        """Two builds of the same tag produce byte-identical archives, so a
        re-run of the dispatch recovery path cannot publish a different
        payload under a tag someone already installed."""
        with tempfile.TemporaryDirectory() as second:
            result = subprocess.run(
                [sys.executable, str(BUILD_RELEASE), "--tag",
                 f"v{self.version}", "--out-dir", second],
                capture_output=True, text=True, cwd=str(ROOT), timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            rebuilt = Path(second) / build_release.archive_name(self.version)

            self.assertEqual(hashlib.sha256(rebuilt.read_bytes()).hexdigest(),
                             hashlib.sha256(self.archive.read_bytes()).hexdigest())


class BuilderRefusesCleanly(unittest.TestCase):
    """The builder runs inside a release workflow, where a traceback is a
    failed release nobody can read."""

    def test_a_tag_that_disagrees_with_version_exits_2(self):
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run(
                [sys.executable, str(BUILD_RELEASE), "--tag", "v99.99.99",
                 "--out-dir", out],
                capture_output=True, text=True, cwd=str(ROOT), timeout=120)

            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("v99.99.99", result.stderr)
            self.assertEqual(list(Path(out).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
