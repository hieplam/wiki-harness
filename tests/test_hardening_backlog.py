"""Regression guards for HARDENING-BACKLOG.md §A (A1-A9).

Every test here is written against a defect the two extraction campaigns
found and deliberately did not fix, because the extraction's premise was
byte-identical behaviour with ogp-wiki. The migration completed on
2026-09-03, so the freeze is over and these are now fixable.

Each test names its backlog id. All of them fail before their fix.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import card_frontmatter_lint as cfl  # noqa: E402
import lint as lint_module  # noqa: E402


# ----------------------------------------------------------------- A1

class GitChangesReadsTheStagedTree(unittest.TestCase):
    """A1. git_changes() drove the RAW check from `git diff HEAD`
    (worktree vs HEAD) rather than `git diff --cached` (index vs HEAD).
    The commit that lands is the INDEX, so a staged tamper whose worktree
    copy is reverted slipped through, and an unstaged edit blocked an
    otherwise unrelated commit."""

    def _repo(self, tmp):
        root = Path(tmp)
        env = dict(os.environ)
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_SYSTEM"] = os.devnull

        def git(*args):
            return subprocess.run(["git", "-C", str(root), *args],
                                  capture_output=True, text=True, env=env)

        git("init", "-q")
        git("config", "user.email", "t@example.invalid")
        git("config", "user.name", "t")
        (root / "sources").mkdir()
        (root / "sources" / "raw").mkdir()
        (root / "sources" / "raw" / "doc.txt").write_text("original\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "seed")
        return root, git

    def test_staged_raw_modification_is_seen(self):
        """The tamper that actually lands: stage an edit to a raw file,
        then restore the worktree copy. `git diff HEAD` sees nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            root, git = self._repo(tmp)
            raw = root / "sources" / "raw" / "doc.txt"
            raw.write_text("tampered\n", encoding="utf-8")
            git("add", "sources/raw/doc.txt")
            raw.write_text("original\n", encoding="utf-8")   # worktree reverted
            changes = lint_module.git_changes(root)
            self.assertIn(("M", "sources/raw/doc.txt"), changes,
                          "a staged raw-file modification must be visible")

    def test_unstaged_edit_does_not_block(self):
        """The mirror-image false positive: an unstaged edit is not part
        of the commit, so it must not appear as a change."""
        with tempfile.TemporaryDirectory() as tmp:
            root, git = self._repo(tmp)
            (root / "sources" / "raw" / "doc.txt").write_text("scratch\n", encoding="utf-8")
            changes = lint_module.git_changes(root)
            self.assertEqual([], changes,
                             "an unstaged edit is not in the commit")


# ----------------------------------------------------------------- A2

class CitationScanDoesNotPrefixMatch(unittest.TestCase):
    """A2. The scan pattern was the id.pattern with its anchors stripped,
    so a card id matched inside a LONGER token: src-2026-08-06-001 was
    'cited' by any page mentioning src-2026-08-06-0011."""

    def test_longer_token_does_not_count_as_a_citation(self):
        scan = cfl.card_id_scan_pattern(cfl.DEFAULT_CARD_ID_PATTERN)
        self.assertIsNone(re.search(scan, "src-2026-08-06-0011"),
                          "a longer id must not match a shorter one")

    def test_the_exact_id_still_matches(self):
        scan = cfl.card_id_scan_pattern(cfl.DEFAULT_CARD_ID_PATTERN)
        self.assertIsNotNone(re.search(scan, "src-2026-08-06-001"))

    def test_the_id_still_matches_inside_prose(self):
        scan = cfl.card_id_scan_pattern(cfl.DEFAULT_CARD_ID_PATTERN)
        for prose in ("see src-2026-08-06-001 for detail",
                      "(src-2026-08-06-001)",
                      "[src-2026-08-06-001](../sources/cards/src-2026-08-06-001.md)",
                      "src-2026-08-06-001."):
            with self.subTest(prose=prose):
                self.assertIsNotNone(re.search(scan, prose))


# ----------------------------------------------------------------- A3

class ListValuedKeysAreValidated(unittest.TestCase):
    """A3. _check_value() returned [] for any list-valued key, so enum,
    pattern, path and card_ref rules declared on a `list: true` key were
    silently never enforced."""

    def test_enum_is_enforced_per_item(self):
        rules = {"list": True, "enum": ["a", "b"]}
        findings = cfl._check_value("sources/cards/c.md", "topics",
                                    ["a", "nope"], rules, lambda p: True)
        self.assertTrue(any("nope" in f.message for f in findings))

    def test_pattern_is_enforced_per_item(self):
        rules = {"list": True, "pattern": r"^[a-z]+$"}
        findings = cfl._check_value("sources/cards/c.md", "topics",
                                    ["ok", "N0PE"], rules, lambda p: True)
        self.assertTrue(any("N0PE" in f.message for f in findings))

    def test_a_clean_list_still_passes(self):
        rules = {"list": True, "enum": ["a", "b"]}
        self.assertEqual([], cfl._check_value("sources/cards/c.md", "topics",
                                              ["a", "b"], rules, lambda p: True))

    def test_card_ref_is_enforced_per_item(self):
        rules = {"list": True, "card_ref": True}
        findings = cfl._check_value("sources/cards/c.md", "parents",
                                    ["src-2026-01-01-001"], rules, lambda p: False)
        self.assertTrue(any("missing card" in f.message for f in findings))


# ----------------------------------------------------------------- A4

class ProtocolRelativeLinksAreNotRepoPaths(unittest.TestCase):
    """A4. resolve() treated a protocol-relative URL (//host/path) as a
    repo-relative path, producing a nonsense target."""

    def test_protocol_relative_is_reported_as_external(self):
        out = cfl.resolve("wiki/page.md", "//example.com/thing")
        self.assertEqual("<external>//example.com/thing", out)

    def test_ordinary_relative_paths_are_unchanged(self):
        self.assertEqual("wiki/sub/x.md", cfl.resolve("wiki/page.md", "sub/x.md"))
        self.assertEqual("x.md", cfl.resolve("wiki/page.md", "../x.md"))


# ----------------------------------------------------------------- A5

class SubprocessCallsAreBounded(unittest.TestCase):
    """A5. A subprocess with no timeout is an unbounded hang inside a git
    hook, indistinguishable from a broken one. fail-closed-edges.md
    obligation 3."""

    def test_every_subprocess_run_in_scripts_passes_timeout(self):
        offenders = []
        for py in sorted((ROOT / "scripts").glob("*.py")):
            src = py.read_text(encoding="utf-8")
            for match in re.finditer(r"subprocess\.run\(", src):
                tail = src[match.start():match.start() + 600]
                depth, end = 0, None
                for i, ch in enumerate(tail):
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                call = tail[:end] if end else tail
                if "timeout=" not in call:
                    line = src[:match.start()].count("\n") + 1
                    offenders.append(f"{py.name}:{line}")
        self.assertEqual([], offenders,
                         f"subprocess.run without timeout=: {offenders}")


# ----------------------------------------------------------------- A6

class RulesFilesAreScopedNotBasenameMatched(unittest.TestCase):
    """A6. RULES_FILES was matched by BASENAME anywhere in the tree, so a
    genuine wiki page named recipes.md was silently treated as a rules
    file and skipped."""

    def test_a_wiki_page_named_like_a_rules_file_is_still_a_page(self):
        self.assertFalse(lint_module.is_rules_file("wiki/recipes.md"))

    def test_the_real_rules_file_is_still_excluded(self):
        self.assertTrue(lint_module.is_rules_file("sources/cards/recipes.md"))

    def test_agents_md_is_excluded_at_any_container_root(self):
        self.assertTrue(lint_module.is_rules_file("AGENTS.md"))
        self.assertTrue(lint_module.is_rules_file("wiki/AGENTS.md"))


# ----------------------------------------------------------------- A7

class CardLintCliReadsSchemaFailClosed(unittest.TestCase):
    """A7. The CLI path read card-schema.json without the fail-closed
    guard the library path uses, so a malformed schema raised out of the
    hook as a traceback instead of a finding."""

    def test_malformed_schema_exits_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Built from the shared synthetic fixture, never the ogp
            # corpus (tests/test_genericity.py enforces this), then its
            # schema is deliberately corrupted.
            root = Path(tmp) / "wiki"
            shutil.copytree(ROOT / "tests" / "fixtures" / "sample-wiki", root)
            (root / "sources" / "cards" / "card-schema.json").write_text(
                "{ not json", encoding="utf-8")
            card = next((root / "sources" / "cards").glob("src-*.md"))
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "card_frontmatter_lint.py"),
                 str(card), "--root", str(root)],
                capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertNotIn("Traceback", result.stderr)


# ----------------------------------------------------------------- A8

class IdPatternContractAcceptsCharacterClassCaret(unittest.TestCase):
    """A8. _violates_id_pattern_contract() read a '^' inside a character
    class as an anchor, rejecting the valid pattern ^src-[^/]+$."""

    def test_caret_inside_a_character_class_is_not_an_anchor(self):
        self.assertFalse(cfl._violates_id_pattern_contract(r"^src-[^/]+$"))

    def test_a_real_inner_anchor_is_still_rejected(self):
        self.assertTrue(cfl._violates_id_pattern_contract(r"^src-^more$"))

    def test_ordinary_patterns_still_pass(self):
        self.assertFalse(cfl._violates_id_pattern_contract(
            cfl.DEFAULT_CARD_ID_PATTERN))


# ----------------------------------------------------------------- A9

class LintCliUsesArgparse(unittest.TestCase):
    """A9. --root was parsed by hand via argv.index(), which raised
    IndexError when --root was the last argument."""

    def test_root_as_last_argument_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lint.py"), "--root"],
            capture_output=True, text=True)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotEqual(0, result.returncode)

    def test_unknown_flag_is_rejected_cleanly(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "lint.py"), "--nope"],
            capture_output=True, text=True)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- A10

class UpgradeRefusesMissingOrMalformedTo(unittest.TestCase):
    """A10. `upgrade.py <target> --report` without `--to` crashed with a
    TypeError traceback (`parse_to_version(None)` returned None and the
    caller unpacked it). A traceback from a user-facing CLI is a crash,
    not a verdict; the edge must refuse with one line and exit 2."""

    def _wiki(self, tmp):
        sys.path.insert(0, str(ROOT))
        from tests.test_upgrade import _make_wiki  # noqa: E402
        return _make_wiki(Path(tmp) / "target")

    def _run(self, target, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "upgrade.py"), str(target), *args],
            capture_output=True, text=True, timeout=60)

    def test_report_without_to_refuses_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(self._wiki(tmp), "--report")
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 2, combined)
            self.assertNotIn("Traceback", combined)
            self.assertIn("--to", combined)

    def test_malformed_to_refuses_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(self._wiki(tmp), "--to", "latest", "--report")
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 2, combined)
            self.assertNotIn("Traceback", combined)
            self.assertIn("latest", combined)

    def test_check_still_needs_no_to(self):
        """--check is the standalone branch and must be unaffected."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(self._wiki(tmp), "--check")
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            self.assertNotIn("--to", result.stderr)


# ---------------------------------------------------------------- A11

class DirtyTreeRefusalNamesThePaths(unittest.TestCase):
    """A11. The clean-tree gate is `git status --porcelain` == empty, so an
    UNTRACKED file (a `.claude/` settings directory, say) blocks the upgrade
    with a message that only says "commit or stash local changes". The
    refusal must keep its verbatim first line and then name each path,
    flagging the untracked ones, so the user knows what to move aside."""

    def test_format_dirty_tree_lists_paths_and_flags_untracked(self):
        sys.path.insert(0, str(ROOT))
        import upgrade  # noqa: E402
        text = upgrade.format_dirty_tree(" M wiki/AGENTS.md\n?? .claude/\n")
        self.assertTrue(text.startswith(upgrade.DIRTY_TREE_MESSAGE))
        self.assertIn("wiki/AGENTS.md", text)
        self.assertIn(".claude/ (untracked)", text)

    def test_untracked_directory_is_named_in_the_refusal(self):
        sys.path.insert(0, str(ROOT))
        from tests.test_upgrade import _make_wiki  # noqa: E402
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_wiki(Path(tmp) / "target")
            (target / "notes").mkdir()
            (target / "notes" / "todo.txt").write_text("scratch\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "upgrade.py"), str(target), "--to", "v1.1.0"],
                capture_output=True, text=True, timeout=60)
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 2, combined)
            self.assertIn("commit or stash local changes before running upgrade", combined)
            self.assertIn("notes/ (untracked)", combined)
