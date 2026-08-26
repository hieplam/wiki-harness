"""End-to-end tests for init.py's full 16-step flow (plan-v3 section 3.1,
T13): no --ci flag anywhere, CLAUDE.md (root) and its 3 nested stubs seeded
as ordinary MANAGED, TRACKED files. Every test here drives init.py as a
real subprocess against a throwaway temp directory -- never against
wiki-harness's own checkout -- and inspects the resulting on-disk wiki
instance and its git history.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_PY = ROOT / "init.py"

sys.path.insert(0, str(ROOT / "scripts"))
from manifest import hash_tree  # noqa: E402

VARS_ARGS = (
    "--wiki-title", "Sample Wiki",
    "--org-name", "Sample Org",
    "--content-language", "English",
    "--repo-name", "sample-wiki",
)


def _run_init(target, extra_args=()):
    args = [sys.executable, str(INIT_PY), str(target),
           *VARS_ARGS, "--non-interactive", *extra_args]
    return subprocess.run(args, capture_output=True, text=True)


def _git(root, *args):
    """Isolates the test's own git calls from the host's global/system
    config, matching test_harness_e2e.py's _git() -- a hostile or merely
    unusual host gitconfig (commit.gpgsign=true with no usable key, for
    instance) must never change whether these assertions hold."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, env=env)


class InitOnEmptyDirLintsClean(unittest.TestCase):
    def test_init_on_empty_dir_lints_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            lint_result = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint_result.returncode, 0, lint_result.stdout)


class InitSetsHookspath(unittest.TestCase):
    def test_init_sets_hookspath(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            hooks = _git(target, "config", "--get", "core.hooksPath")
            self.assertEqual(hooks.stdout.strip(), ".githooks")


class InitWritesManifestMatchingDisk(unittest.TestCase):
    def test_init_writes_manifest_matching_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            manifest = json.loads(
                (target / ".wiki-harness-manifest.json").read_text(encoding="utf-8"))
            recorded = manifest["files"]
            self.assertTrue(recorded)
            self.assertNotEqual(manifest["source_url"], "")

            actual = hash_tree(target, list(recorded))
            for path, entry in recorded.items():
                self.assertEqual(actual.get(path), entry["sha256"], path)


class InitRefusesNonemptyWithoutForce(unittest.TestCase):
    def test_init_refuses_nonempty_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            target.mkdir()
            (target / "keep.txt").write_text("pre-existing", encoding="utf-8")

            result = _run_init(target)

            self.assertEqual(result.returncode, 2)
            self.assertIn("is not empty", result.stderr)
            self.assertIn("--force", result.stderr)
            self.assertEqual(list(target.iterdir()), [target / "keep.txt"])


class InitFirstCommitGoesThroughRealHooks(unittest.TestCase):
    """Subprocess-level proof that .githooks/* are real, live hooks on the
    freshly-scaffolded repo, not merely files copied to disk: a second,
    deliberately invalid-subject `git commit` -- a real subprocess, not an
    in-process call to check_commit_msg.py -- must be refused by the wired
    core.hooksPath, and the one commit init.py's own step 14 made (also a
    real subprocess git commit, per init.py's commit_scaffold()) must be
    the only commit that ever lands."""

    def test_init_first_commit_goes_through_real_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            log_before = _git(target, "log", "--oneline")
            self.assertEqual(len(log_before.stdout.splitlines()), 1)

            bad_commit = _git(target, "commit", "--allow-empty",
                              "-m", "not a valid conventional subject")
            self.assertNotEqual(bad_commit.returncode, 0)

            log_after = _git(target, "log", "--oneline")
            self.assertEqual(log_after.stdout, log_before.stdout)


class InitSeedsClaudeMdStubsTracked(unittest.TestCase):
    CLAUDE_PATHS = ("CLAUDE.md", "sources/CLAUDE.md",
                    "sources/cards/CLAUDE.md", "wiki/CLAUDE.md")
    ATTRIBUTABLE_CODES = ("FM", "INDEX", "ORPHAN", "CARD_FM")

    def test_init_seeds_claude_md_stubs_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            for rel in self.CLAUDE_PATHS:
                self.assertTrue((target / rel).is_file(), rel)

            show = _git(target, "show", "--stat", "HEAD")
            for rel in self.CLAUDE_PATHS:
                self.assertIn(rel, show.stdout, rel)

            # T08 pre-emptively added "CLAUDE.md" to lint.py's RULES_FILES
            # so a tracked CLAUDE.md stub never trips FM/INDEX/ORPHAN/
            # CARD_FM -- this proves that promise against the real,
            # post-scaffold lint run, not merely "lint exits 0 overall".
            lint_result = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint_result.returncode, 0, lint_result.stdout)
            for path in self.CLAUDE_PATHS:
                for code in self.ATTRIBUTABLE_CODES:
                    self.assertNotIn(f" {code} {path}:", lint_result.stdout,
                                     f"{code} finding attributable to {path}")


class InitScaffoldHasNoTestsDir(unittest.TestCase):
    def test_init_scaffold_has_no_tests_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            found = [p for p in target.rglob("tests") if p.is_dir()]
            self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
