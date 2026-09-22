from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gap_ledger  # noqa: E402
import gap_lint  # noqa: E402

SCHEMA_TEXT = (ROOT / "templates" / "gap-schema.default.json").read_text(encoding="utf-8")


def gap_record(gid="gap-2024-01-15-001"):
    return {
        "type": "gap", "id": gid, "at": "2024-01-15T09:00:00+00:00",
        "service": "example-service", "session": "0000-session",
        "topics": ["concurrency"], "context": "reading a worker loop",
        "prompt_verbatim": "whats a channel",
        "question": "what is the difference between goroutines and channels in Go?",
        "wiki_answer": "no page covers this", "answer_given": "from general knowledge",
    }


def ledger_text(*records):
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)


def inputs(**overrides):
    records, _ = gap_ledger.parse_ledger(overrides.get("ledger_text", ""))
    base = dict(
        ledger_text=overrides.get("ledger_text", ""),
        view_text=gap_ledger.render_view(records),
        schema_text=SCHEMA_TEXT,
        head_bytes=b"",
        work_bytes=overrides.get("ledger_text", "").encode("utf-8"),
        deleted_lines=0,
        git_error=None,
        card_ids=frozenset(),
        page_paths=frozenset(),
    )
    base.update(overrides)
    return gap_lint.GapInputs(**base)


def codes(findings):
    return sorted({f.code for f in findings})


class AbsentLedgerIsClean(unittest.TestCase):
    def test_no_ledger_no_findings(self):
        self.assertEqual(gap_lint.check_gaps(inputs()), [])


class L1Parsing(unittest.TestCase):
    def test_unparseable_line_is_an_error(self):
        findings = gap_lint.check_gaps(inputs(ledger_text="{nope\n"))
        self.assertIn("GAP", codes(findings))
        self.assertTrue(all(f.severity == "ERROR" for f in findings))

    def test_missing_trailing_newline_is_an_error(self):
        text = json.dumps(gap_record(), sort_keys=True)
        self.assertTrue(any("newline" in f.message
                            for f in gap_lint.check_gaps(inputs(ledger_text=text))))


class L2L3SchemaAndIds(unittest.TestCase):
    def test_undeclared_key_is_an_error(self):
        rec = gap_record()
        rec["priority"] = "high"
        text = ledger_text(rec)
        findings = gap_lint.check_gaps(inputs(ledger_text=text, work_bytes=text.encode()))
        self.assertTrue(any("priority" in f.message for f in findings))

    def test_malformed_schema_is_its_own_error(self):
        findings = gap_lint.check_gaps(inputs(schema_text="{broken"))
        self.assertIn("GAP_SCHEMA", codes(findings))


class L5ReferenceTargets(unittest.TestCase):
    def build(self, card, page):
        res = {"type": "resolution", "gap": "gap-2024-01-15-001",
               "at": "2024-01-16T09:00:00+00:00", "card": card, "wiki_page": page}
        text = ledger_text(gap_record(), res)
        records, _ = gap_ledger.parse_ledger(text)
        return inputs(ledger_text=text, work_bytes=text.encode(),
                      view_text=gap_ledger.render_view(records),
                      card_ids=frozenset({"src-2024-01-16-001"}),
                      page_paths=frozenset({"wiki/widget-assembly.md"}))

    def test_existing_card_and_page_pass(self):
        found = self.build("src-2024-01-16-001", "wiki/widget-assembly.md")
        self.assertEqual(gap_lint.check_gaps(found), [])

    def test_missing_card_is_an_error(self):
        found = self.build("src-2099-01-01-001", "wiki/widget-assembly.md")
        self.assertTrue(any("src-2099-01-01-001" in f.message
                            for f in gap_lint.check_gaps(found)))

    def test_missing_page_is_an_error(self):
        found = self.build("src-2024-01-16-001", "wiki/nope.md")
        self.assertTrue(any("wiki/nope.md" in f.message
                            for f in gap_lint.check_gaps(found)))


class L6AppendOnly(unittest.TestCase):
    """V2. One case per row of the spec's attack table."""

    def setUp(self):
        self.a = ledger_text(gap_record("gap-2024-01-15-001"))
        self.b = ledger_text(gap_record("gap-2024-01-15-001"),
                             gap_record("gap-2024-01-15-002"))

    def violation(self, head, work):
        return gap_ledger.append_only_violation(head, work)

    def test_append_is_allowed(self):
        self.assertIsNone(self.violation(self.a.encode(), self.b.encode()))

    def test_identical_is_allowed(self):
        self.assertIsNone(self.violation(self.a.encode(), self.a.encode()))

    def test_first_commit_with_no_head_is_allowed(self):
        self.assertIsNone(self.violation(b"", self.b.encode()))

    def test_delete_the_last_line(self):
        self.assertIsNotNone(self.violation(self.b.encode(), self.a.encode()))

    def test_delete_a_middle_line(self):
        head = ledger_text(gap_record("gap-2024-01-15-001"),
                           gap_record("gap-2024-01-15-002"),
                           gap_record("gap-2024-01-15-003"))
        work = ledger_text(gap_record("gap-2024-01-15-001"),
                           gap_record("gap-2024-01-15-003"))
        self.assertIsNotNone(self.violation(head.encode(), work.encode()))

    def test_truncate_to_empty(self):
        self.assertIsNotNone(self.violation(self.a.encode(), b""))

    def test_delete_the_file_and_rewrite_it(self):
        """The failure actually observed in the wild: an agent replaces the
        whole file with its own entries."""
        fresh = ledger_text(gap_record("gap-2024-06-01-001"))
        self.assertIsNotNone(self.violation(self.b.encode(), fresh.encode()))

    def test_reorder_lines(self):
        reordered = ledger_text(gap_record("gap-2024-01-15-002"),
                                gap_record("gap-2024-01-15-001"))
        self.assertIsNotNone(self.violation(self.b.encode(), reordered.encode()))

    def test_edit_one_byte_in_a_committed_line(self):
        edited = self.a.replace("example-service", "example-servicE")
        self.assertIsNotNone(self.violation(self.a.encode(), edited.encode()))

    def test_violation_surfaces_as_a_lint_error(self):
        found = inputs(ledger_text=self.a, work_bytes=self.a.encode(),
                       head_bytes=self.b.encode())
        self.assertTrue(any(f.code == "GAP_APPEND" for f in gap_lint.check_gaps(found)))

    def test_staged_deletion_count_is_an_independent_error(self):
        """Second mechanism: even if the prefix check somehow passed, a
        staged diff that removes lines is itself the violation."""
        found = inputs(ledger_text=self.a, work_bytes=self.a.encode(),
                       head_bytes=self.a.encode(), deleted_lines=3)
        self.assertTrue(any(f.code == "GAP_APPEND" for f in gap_lint.check_gaps(found)))


class V3FailClosed(unittest.TestCase):
    """VISION.md records the exact bug this guards: git_changes returns an
    empty change list when git fails, so 'unknown' reads as 'no changes'
    and a tampered file passes. A git error must ERROR, never pass."""

    def test_git_error_is_an_error_not_silence(self):
        findings = gap_lint.check_gaps(inputs(git_error="fatal: not a git repository"))
        self.assertTrue(findings)
        self.assertTrue(all(f.severity == "ERROR" for f in findings))
        self.assertIn("GAP_APPEND", codes(findings))


class L7ViewSync(unittest.TestCase):
    def test_stale_view_is_an_error(self):
        text = ledger_text(gap_record())
        found = inputs(ledger_text=text, work_bytes=text.encode(),
                       view_text="# Knowledge gaps\n\nstale\n")
        self.assertTrue(any(f.code == "GAP_VIEW" for f in gap_lint.check_gaps(found)))

    def test_fresh_view_passes(self):
        text = ledger_text(gap_record())
        records, _ = gap_ledger.parse_ledger(text)
        found = inputs(ledger_text=text, work_bytes=text.encode(),
                       view_text=gap_ledger.render_view(records))
        self.assertEqual(gap_lint.check_gaps(found), [])


if __name__ == "__main__":
    unittest.main()
