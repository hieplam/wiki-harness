from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lint import check_index_sync, check_raw_immutability, parse_name_status, run, scan

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"

FILES = {
    "index.md": "- [Widget assembly](./wiki/widget-assembly.md)\n",
    "wiki/widget-assembly.md": "---\ntitle: Widget assembly\ntopics: [widget-assembly]\n---\n"
                       "[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md)\n",
    "sources/cards/src-2024-01-15-001.md":
        "---\nid: src-2024-01-15-001\ndate: 2024-01-15\norigin: session\n"
        "trust: stated\ntopics: [widget-assembly]\n---\n## Claims\n- a claim\n",
    "sources/cards/card-schema.json":
        (FIXTURE / "sources/cards/card-schema.json").read_text(encoding="utf-8"),
}


class IndexSync(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(check_index_sync(dict(FILES)), [])

    def test_page_not_listed(self):
        files = dict(FILES)
        files["wiki/unlisted.md"] = "---\ntitle: U\ntopics: [x]\n---\nhi\n"
        findings = check_index_sync(files)
        self.assertEqual([f.code for f in findings], ["INDEX"])
        self.assertIn("wiki/unlisted.md", findings[0].message)

    def test_ghost_entry(self):
        files = dict(FILES)
        files["index.md"] += "- [Ghost](./wiki/ghost.md)\n"
        findings = check_index_sync(files)
        self.assertTrue(any("ghost.md" in f.message for f in findings))

    def test_missing_index(self):
        files = dict(FILES)
        del files["index.md"]
        self.assertEqual([f.code for f in check_index_sync(files)], ["INDEX"])


class RawImmutability(unittest.TestCase):
    def test_add_is_allowed(self):
        self.assertEqual(check_raw_immutability([("A", "sources/raw/x.xml")]), [])

    def test_modify_delete_rename_rejected(self):
        for status in ("M", "D", "R100"):
            findings = check_raw_immutability([(status, "sources/raw/x.xml")])
            self.assertEqual([f.code for f in findings], ["RAW"], status)

    def test_other_paths_ignored(self):
        self.assertEqual(check_raw_immutability([("M", "wiki/widget-assembly.md")]), [])


class RunAndScan(unittest.TestCase):
    def test_run_aggregates_clean(self):
        findings = run(dict(FILES), [])
        self.assertEqual([f for f in findings if f.severity == "ERROR"], [])

    def test_scan_reads_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in FILES.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            (root / "sources/raw").mkdir(parents=True)
            (root / "sources/raw/a.xml").write_text("<x/>", encoding="utf-8")
            files, enc = scan(root)
            self.assertIn("wiki/widget-assembly.md", files)
            self.assertEqual(files["sources/raw/a.xml"], "")
            self.assertEqual(enc, [])

    def test_bom_is_stripped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in FILES.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                if rel == "wiki/widget-assembly.md":
                    p.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
                else:
                    p.write_text(text, encoding="utf-8")
            files, enc = scan(root)
            self.assertEqual(enc, [])
            self.assertTrue(files["wiki/widget-assembly.md"].startswith("---"))
            self.assertEqual(
                [f for f in run(files, []) if f.severity == "ERROR"], [])

    def test_cli_exit_zero_on_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in FILES.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            lint_py = Path(__file__).resolve().parent.parent / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_exit_one_on_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in FILES.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            (root / "wiki" / "bad.md").write_bytes(b"---\n\xff\xfe garbage")
            lint_py = Path(__file__).resolve().parent.parent / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("ENCODING", result.stdout)

    def test_cli_exit_one_on_missing_hooks_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in FILES.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            lint_py = Path(__file__).resolve().parent.parent / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("HOOKS", result.stdout)


class ParseNameStatus(unittest.TestCase):
    def test_rename_emits_delete_of_old_path(self):
        out = "R100\tsources/raw/x.xml\twiki/notes.md"
        self.assertEqual(parse_name_status(out),
                         [("D", "sources/raw/x.xml"), ("A", "wiki/notes.md")])

    def test_plain_lines_pass_through(self):
        self.assertEqual(parse_name_status("M\twiki/widget-assembly.md\nA\tsources/raw/a.xml"),
                         [("M", "wiki/widget-assembly.md"), ("A", "sources/raw/a.xml")])

    def test_rename_into_raw_is_allowed(self):
        changes = parse_name_status("R100\tstaging/y.xml\tsources/raw/y.xml")
        self.assertEqual(check_raw_immutability(changes), [])

    def test_rename_out_of_raw_still_caught(self):
        changes = parse_name_status("R100\tsources/raw/x.xml\twiki/notes.md")
        findings = check_raw_immutability(changes)
        self.assertEqual([f.code for f in findings], ["RAW"])


class PreCommitHook(unittest.TestCase):
    """The hooks are the hard gate: they are the only thing that makes lint
    and commit-msg validation unskippable for an agent that never reads its
    own output. The library keeps its hook sources at githooks/ (no leading
    dot); `init` is what copies them into a wiki's .githooks/."""

    def test_pre_commit_hook_exists_and_runs_lint(self):
        hook = ROOT / "githooks" / "pre-commit"
        self.assertTrue(hook.is_file(), "missing githooks/pre-commit")
        self.assertTrue(os.access(hook, os.X_OK), "hook is not executable")
        self.assertEqual(
            hook.read_text(encoding="utf-8"),
            '#!/bin/sh\n'
            'exec python3 "$(git rev-parse --show-toplevel)/scripts/lint.py"\n')

    def test_commit_msg_hook_exists_and_runs_check(self):
        hook = ROOT / "githooks" / "commit-msg"
        self.assertTrue(hook.is_file(), "missing githooks/commit-msg")
        self.assertTrue(os.access(hook, os.X_OK), "hook is not executable")
        self.assertEqual(
            hook.read_text(encoding="utf-8"),
            '#!/bin/sh\n'
            'exec python3 "$(git rev-parse --show-toplevel)/scripts/check_commit_msg.py" "$1"\n')


if __name__ == "__main__":
    unittest.main()
