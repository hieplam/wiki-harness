from __future__ import annotations

import contextlib
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gap  # noqa: E402
import gap_ledger  # noqa: E402

SCHEMA_TEXT = (ROOT / "templates" / "gap-schema.default.json").read_text(encoding="utf-8")
NOW = datetime.datetime(2024, 1, 15, 9, 0, 0,
                        tzinfo=datetime.timezone.utc)

ADD_ARGS = [
    "add", "--service", "example-service", "--session", "0000-session",
    "--context", "reading a worker loop", "--prompt", "whats a channel",
    "--question", "what is the difference between goroutines and channels in Go?",
    "--wiki-answer", "no page covers this",
    "--answer-given", "answered from general knowledge",
    "--topics", "concurrency",
]


def _git(root, *args):
    """Isolated exactly like test_gap_lint.py's own _git() helper: the
    host's global/system gitconfig (commit.gpgsign=true with no usable key,
    an unusual default branch name, etc.) must never change whether these
    assertions hold."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, env=env, check=True)


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "gaps").mkdir()
        (self.root / "gaps" / "gap-schema.json").write_text(SCHEMA_TEXT, encoding="utf-8")
        (self.root / "sources" / "cards").mkdir(parents=True)
        (self.root / "wiki").mkdir()
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.invalid")
        _git(self.root, "config", "user.name", "t")
        self.addCleanup(self._tmp.cleanup)

    def run_cli(self, args, now=NOW, env=None):
        return gap.main(args, root=self.root, now=now, env=env)

    @staticmethod
    @contextlib.contextmanager
    def quiet():
        """Swallows argparse usage/error text and the CLI's own diagnostic
        prints, so a test asserting a rejection does not also spam the
        suite's console output with expected-and-checked stderr/stdout."""
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            yield

    @property
    def ledger(self):
        path = self.root / gap_ledger.LEDGER_PATH
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def records(self):
        return [json.loads(line) for line in self.ledger.splitlines()]


class AddWritesOneValidLine(CliCase):
    def test_add_creates_the_ledger_on_demand(self):
        self.assertFalse((self.root / gap_ledger.LEDGER_PATH).is_file())
        self.assertEqual(self.run_cli(ADD_ARGS + ["--no-commit"]), 0)
        self.assertTrue((self.root / gap_ledger.LEDGER_PATH).is_file())

    def test_the_line_is_a_valid_gap_record(self):
        self.run_cli(ADD_ARGS + ["--no-commit"])
        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["type"], "gap")
        self.assertEqual(records[0]["id"], "gap-2024-01-15-001")
        self.assertEqual(records[0]["topics"], ["concurrency"])
        self.assertEqual(records[0]["at"], "2024-01-15T09:00:00+00:00")

    def test_the_line_ends_with_a_newline(self):
        self.run_cli(ADD_ARGS + ["--no-commit"])
        self.assertTrue(self.ledger.endswith("\n"))

    def test_the_view_is_regenerated(self):
        self.run_cli(ADD_ARGS + ["--no-commit"])
        view = (self.root / gap_ledger.VIEW_PATH).read_text(encoding="utf-8")
        records, _ = gap_ledger.parse_ledger(self.ledger)
        self.assertEqual(view, gap_ledger.render_view(records))

    def test_second_add_on_the_same_day_increments(self):
        self.run_cli(ADD_ARGS + ["--no-commit"])
        self.run_cli(ADD_ARGS + ["--no-commit"])
        self.assertEqual([r["id"] for r in self.records()],
                         ["gap-2024-01-15-001", "gap-2024-01-15-002"])

    def test_add_on_a_new_day_rolls_over(self):
        self.run_cli(ADD_ARGS + ["--no-commit"])
        later = datetime.datetime(2024, 1, 16, 9, 0, 0, tzinfo=datetime.timezone.utc)
        self.run_cli(ADD_ARGS + ["--no-commit"], now=later)
        self.assertEqual([r["id"] for r in self.records()],
                         ["gap-2024-01-15-001", "gap-2024-01-16-001"])


class MissingFlagWritesNothing(CliCase):
    """V5: the CLI is the only tunnel, and a bad call must leave no trace."""

    def test_missing_question_exits_non_zero(self):
        args = [a for a in ADD_ARGS]
        idx = args.index("--question")
        del args[idx:idx + 2]
        with self.quiet(), self.assertRaises(SystemExit) as raised:
            self.run_cli(args + ["--no-commit"])
        self.assertNotEqual(raised.exception.code, 0)

    def test_missing_question_writes_zero_bytes(self):
        args = [a for a in ADD_ARGS]
        idx = args.index("--question")
        del args[idx:idx + 2]
        with self.quiet():
            try:
                self.run_cli(args + ["--no-commit"])
            except SystemExit:
                pass
        self.assertEqual(self.ledger, "")

    def test_empty_topics_is_rejected_and_writes_nothing(self):
        args = [a for a in ADD_ARGS]
        args[args.index("--topics") + 1] = ""
        with self.quiet():
            code = self.run_cli(args + ["--no-commit"])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.ledger, "")


class ReadsProseFromFileAndStdin(CliCase):
    def test_at_path_reads_the_file(self):
        answer = self.root / "answer.txt"
        answer.write_text("a long multi-paragraph answer\n", encoding="utf-8")
        args = [a for a in ADD_ARGS]
        args[args.index("--wiki-answer") + 1] = "@" + str(answer)
        self.assertEqual(self.run_cli(args + ["--no-commit"]), 0)
        self.assertEqual(self.records()[0]["wiki_answer"],
                         "a long multi-paragraph answer")


class ResolveMeasureRatify(CliCase):
    def setUp(self):
        super().setUp()
        (self.root / "sources" / "cards" / "src-2024-01-16-001.md").write_text(
            "x", encoding="utf-8")
        (self.root / "wiki" / "widget-assembly.md").write_text("x", encoding="utf-8")
        self.run_cli(ADD_ARGS + ["--no-commit"])

    def test_resolve_appends_a_resolution(self):
        code = self.run_cli(["resolve", "gap-2024-01-15-001",
                             "--card", "src-2024-01-16-001",
                             "--page", "wiki/widget-assembly.md", "--no-commit"])
        self.assertEqual(code, 0)
        self.assertEqual(self.records()[-1]["type"], "resolution")

    def test_measure_appends_and_changes_folded_status(self):
        self.run_cli(["measure", "gap-2024-01-15-001", "--verdict", "answered",
                      "--wiki-answer", "now covered", "--no-commit"])
        records, _ = gap_ledger.parse_ledger(self.ledger)
        self.assertEqual(gap_ledger.fold_status(records),
                         {"gap-2024-01-15-001": "answered"})

    def test_ratify_requires_a_reason(self):
        with self.quiet(), self.assertRaises(SystemExit):
            self.run_cli(["ratify", "gap-2024-01-15-001",
                          "--verdict", "unrelated", "--no-commit"])

    def test_unknown_gap_id_is_rejected_and_writes_nothing(self):
        before = self.ledger
        with self.quiet():
            code = self.run_cli(
                ["measure", "gap-2099-01-01-001", "--verdict", "answered",
                 "--wiki-answer", "x", "--no-commit"])
        self.assertNotEqual(code, 0)
        self.assertEqual(self.ledger, before)

    def test_bad_verdict_is_rejected(self):
        with self.quiet(), self.assertRaises(SystemExit):
            self.run_cli(["measure", "gap-2024-01-15-001", "--verdict", "sortof",
                          "--wiki-answer", "x", "--no-commit"])


class RenderAndList(CliCase):
    def test_render_is_idempotent(self):
        self.run_cli(ADD_ARGS + ["--no-commit"])
        self.run_cli(["render"])
        first = (self.root / gap_ledger.VIEW_PATH).read_bytes()
        self.run_cli(["render"])
        self.assertEqual(first, (self.root / gap_ledger.VIEW_PATH).read_bytes())

    def test_list_filters_by_status(self):
        self.run_cli(ADD_ARGS + ["--no-commit"])
        with self.quiet():
            code = self.run_cli(["list", "--status", "opened"])
        self.assertEqual(code, 0)


def _isolated_env():
    """The same isolation `_git()` gives its own git calls, threaded
    through to `gap.commit()` -- so a host's global gitconfig
    (commit.gpgsign=true with no usable key, an unusual core.hooksPath)
    can never change whether these two commit-through-the-CLI tests
    hold."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return env


class CommitBehaviour(CliCase):
    def test_add_makes_its_own_commit(self):
        _git(self.root, "commit", "-q", "--allow-empty", "-m", "chore: base")
        self.assertEqual(self.run_cli(ADD_ARGS, env=_isolated_env()), 0)
        log = _git(self.root, "log", "--oneline").stdout
        self.assertIn("gap(gap-2024-01-15-001):", log)

    def test_a_failed_commit_still_leaves_the_line_on_disk(self):
        """pre-commit may fail for unrelated reasons. The append already
        happened, so nothing is lost -- the CLI reports and moves on."""
        hooks = self.root / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        _git(self.root, "commit", "-q", "--allow-empty", "--no-verify",
            "-m", "chore: base")
        with self.quiet():
            code = self.run_cli(ADD_ARGS, env=_isolated_env())
        self.assertNotEqual(code, 0)
        self.assertEqual(len(self.records()), 1)


class PiiIsAdvisoryOnly(CliCase):
    def test_a_record_with_an_email_still_writes_and_exits_zero(self):
        args = [a for a in ADD_ARGS]
        args[args.index("--context") + 1] = "raised by someone@example.com"
        with self.quiet():
            code = self.run_cli(args + ["--no-commit"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.records()), 1)


if __name__ == "__main__":
    unittest.main()
