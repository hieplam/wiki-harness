"""End-to-end tests against a real, temporary git repo -- not a fixture
dict. These close tests-inventory.md section 5 items 2-3: git_changes()
(the real `git diff HEAD --name-status` subprocess) and hooks_finding()'s
positive path had zero coverage anywhere before this file, in ogp-wiki or
here. Both tests build their own throwaway git repo (setUp per test) and
never touch wiki-harness's own .git.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
    return subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, check=True)


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


if __name__ == "__main__":
    unittest.main()
