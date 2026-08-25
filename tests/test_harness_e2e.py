"""End-to-end tests against a real, temporary git repo -- not a fixture
dict. These close tests-inventory.md section 5 items 2-3: git_changes()
(the real `git diff HEAD --name-status` subprocess) and hooks_finding()'s
positive path had zero coverage anywhere before this file, in ogp-wiki or
here. Both tests build their own throwaway git repo (setUp per test) and
never touch wiki-harness's own .git.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import Finding
from lint import git_changes, hooks_finding, run, scan

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"

# A fully lint-clean tree (two cross-linking wiki pages, so neither is an
# ORPHAN -- same shape as test_lint_checks.py's good_files()) plus one
# sources/raw/ file this module adds and then modifies after commit.
FILES = {
    "index.md": "- [Widget assembly](./wiki/widget-assembly.md)\n"
                "- [Quality checks](./wiki/quality-checks.md)\n",
    "wiki/widget-assembly.md":
        "---\ntitle: Widget assembly\ntopics: [widget-assembly]\n---\n"
        "The weekly batch. Details in\n"
        "[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).\n"
        "See also [quality checks](./quality-checks.md).\n",
    "wiki/quality-checks.md":
        "---\ntitle: Quality checks\ntopics: [widget-assembly]\n---\n"
        "Run after the [widget assembly](./widget-assembly.md), per\n"
        "[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).\n",
    "sources/cards/src-2024-01-15-001.md":
        "---\nid: src-2024-01-15-001\ndate: 2024-01-15\norigin: session\n"
        "trust: stated\ntopics: [widget-assembly]\n---\n## Claims\n- a claim\n",
    "sources/cards/card-schema.json":
        (FIXTURE / "sources/cards/card-schema.json").read_text(encoding="utf-8"),
}


def _write_tree(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _git(root, *args):
    # Isolate every git invocation from the host's global/system config
    # (e.g. a commit.gpgsign=true policy with no usable signing key/agent,
    # which would otherwise make `git commit` below fail or hang on a
    # machine or CI runner that enforces it). Only this repo's own local
    # config -- set via the `git config` calls in each test -- applies.
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, check=True, env=env)


class GitChangesRawEndToEnd(unittest.TestCase):
    """git_changes() is the impure edge that runs the real `git diff HEAD
    --name-status` subprocess. This proves the real subprocess call, real
    git diff, and check_raw_immutability produce the RAW finding together
    -- not just that parse_name_status/check_raw_immutability agree on
    hand-built input, as every other test in the suite does."""

    def test_git_changes_raw_finding_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = dict(FILES)
            files["sources/raw/reading.xml"] = "<reading>1</reading>"
            _write_tree(root, files)

            _git(root, "init", "-q")
            _git(root, "config", "user.email", "test@example.com")
            _git(root, "config", "user.name", "Test")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", "initial (status A, allowed)")

            # Modify the raw file after the commit, uncommitted -- the
            # change git_changes()'s real subprocess call must surface.
            (root / "sources/raw/reading.xml").write_text(
                "<reading>2</reading>", encoding="utf-8")

            scanned_files, enc = scan(root)
            self.assertEqual(enc, [])
            findings = run(scanned_files, git_changes(root))

            self.assertEqual(findings, [
                Finding("ERROR", "RAW", "sources/raw/reading.xml",
                        "raw source changed (git status M) — sources/raw/ is immutable"),
            ])


class HooksFindingPositivePath(unittest.TestCase):
    """hooks_finding()'s positive path: a real temp git repo with
    core.hooksPath correctly set to .githooks. Before this test, only the
    negative path (hooksPath unset -> 1 finding, test_lint_cli.py's
    test_cli_exit_one_on_missing_hooks_path) had any coverage anywhere."""

    def test_hooks_finding_positive_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _git(root, "init", "-q")
            _git(root, "config", "core.hooksPath", ".githooks")

            self.assertEqual(hooks_finding(root), [])


class GitCommitHostConfigIsolation(unittest.TestCase):
    """_git() is the only place in the suite that runs `git commit` as a
    subprocess. Without an explicit env= override it inherits the host's
    GIT_CONFIG_GLOBAL/GIT_CONFIG_SYSTEM, so a host or CI runner enforcing
    commit.gpgsign=true (with no usable signing key/agent) makes the commit
    below fail with CalledProcessError -- or hang on a real signing prompt
    -- even though git_changes()/hooks_finding() are completely correct.
    This proves _git()'s own git invocations are immune to that: a hostile
    global gitconfig injected via the environment must not stop the
    commit from succeeding."""

    def test_git_commit_survives_hostile_global_gitconfig(self):
        with tempfile.TemporaryDirectory() as tmp:
            hostile_global = Path(tmp) / "hostile-gitconfig"
            hostile_global.write_text(
                "[commit]\n\tgpgsign = true\n"
                "[gpg]\n\tprogram = /nonexistent/gpg-that-does-not-exist\n",
                encoding="utf-8",
            )
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "f.txt").write_text("hello", encoding="utf-8")

            with mock.patch.dict(os.environ,
                                  {"GIT_CONFIG_GLOBAL": str(hostile_global)}):
                _git(repo, "init", "-q")
                _git(repo, "config", "user.email", "test@example.com")
                _git(repo, "config", "user.name", "Test")
                _git(repo, "add", "-A")
                # Must not raise CalledProcessError: the hostile
                # commit.gpgsign=true/missing-gpg config injected above
                # must never reach this commit.
                _git(repo, "commit", "-q", "-m", "initial")


if __name__ == "__main__":
    unittest.main()
