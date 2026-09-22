from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gap_ledger  # noqa: E402

SCHEMA_TEXT = (ROOT / "templates" / "gap-schema.default.json").read_text(encoding="utf-8")


def valid_gap(gid="gap-2024-01-15-001"):
    return {
        "type": "gap", "id": gid, "at": "2024-01-15T09:00:00+00:00",
        "service": "example-service", "session": "0000-session",
        "topics": ["concurrency"], "context": "reading a worker loop",
        "prompt_verbatim": "whats a channel",
        "question": "what is the difference between goroutines and channels in Go?",
        "wiki_answer": "no page covers this", "answer_given": "answered from general knowledge",
    }


class LoadSchema(unittest.TestCase):
    def test_loads_and_exposes_id_pattern(self):
        schema, err = gap_ledger.load_gap_schema(SCHEMA_TEXT)
        self.assertIsNone(err)
        self.assertEqual(gap_ledger.gap_id_pattern_from_schema(schema),
                         r"^gap-\d{4}-\d{2}-\d{2}-\d{3}$")

    def test_malformed_json_reports_error_and_no_schema(self):
        schema, err = gap_ledger.load_gap_schema("{not json")
        self.assertIsNone(schema)
        self.assertIn("could not be parsed", err)

    def test_missing_pattern_falls_back_to_default(self):
        self.assertEqual(gap_ledger.gap_id_pattern_from_schema({}),
                         gap_ledger.DEFAULT_GAP_ID_PATTERN)


class ParseLedger(unittest.TestCase):
    def test_parses_one_record_per_line(self):
        text = json.dumps(valid_gap()) + "\n"
        records, errors = gap_ledger.parse_ledger(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][0], 1)
        self.assertEqual(records[0][1]["id"], "gap-2024-01-15-001")

    def test_empty_text_is_clean(self):
        self.assertEqual(gap_ledger.parse_ledger(""), ([], []))

    def test_unparseable_line_is_an_error(self):
        records, errors = gap_ledger.parse_ledger("{nope\n")
        self.assertEqual(records, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][0], 1)

    def test_non_object_line_is_an_error(self):
        records, errors = gap_ledger.parse_ledger("[1, 2]\n")
        self.assertEqual(records, [])
        self.assertIn("must be a JSON object", errors[0][1])

    def test_missing_trailing_newline_is_an_error(self):
        records, errors = gap_ledger.parse_ledger(json.dumps(valid_gap()))
        self.assertTrue(any("newline" in m for _, m in errors))


class ValidateRecords(unittest.TestCase):
    def setUp(self):
        self.schema, _ = gap_ledger.load_gap_schema(SCHEMA_TEXT)
        self.pattern = gap_ledger.gap_id_pattern_from_schema(self.schema)

    def check(self, records):
        return gap_ledger.validate_records(
            [(i + 1, r) for i, r in enumerate(records)], self.schema, self.pattern)

    def test_valid_gap_passes(self):
        self.assertEqual(self.check([valid_gap()]), [])

    def test_unknown_key_is_rejected(self):
        rec = valid_gap()
        rec["severity"] = "high"
        errors = self.check([rec])
        self.assertTrue(any("severity" in m for _, m in errors))

    def test_missing_required_key_is_rejected(self):
        rec = valid_gap()
        del rec["question"]
        errors = self.check([rec])
        self.assertTrue(any("question" in m for _, m in errors))

    def test_unknown_type_is_rejected(self):
        errors = self.check([{"type": "note", "id": "gap-2024-01-15-001"}])
        self.assertTrue(any("unknown record type" in m for _, m in errors))

    def test_bad_id_shape_is_rejected(self):
        errors = self.check([valid_gap("gap-1")])
        self.assertTrue(any("does not match" in m for _, m in errors))

    def test_duplicate_id_is_rejected(self):
        errors = self.check([valid_gap(), valid_gap()])
        self.assertTrue(any("duplicate" in m for _, m in errors))

    def test_topics_must_be_a_non_empty_list(self):
        rec = valid_gap()
        rec["topics"] = []
        self.assertTrue(any("topics" in m for _, m in self.check([rec])))

    def test_ref_to_unknown_gap_is_rejected(self):
        ref = {"type": "measurement", "gap": "gap-2024-01-15-999",
               "at": "2024-01-16T09:00:00+00:00", "verdict": "answered",
               "wiki_answer": "now covered"}
        errors = self.check([valid_gap(), ref])
        self.assertTrue(any("unknown gap" in m for _, m in errors))

    def test_ref_before_its_gap_is_rejected(self):
        ref = {"type": "measurement", "gap": "gap-2024-01-15-001",
               "at": "2024-01-16T09:00:00+00:00", "verdict": "answered",
               "wiki_answer": "now covered"}
        errors = self.check([ref, valid_gap()])
        self.assertTrue(any("earlier" in m for _, m in errors))

    def test_bad_enum_value_is_rejected(self):
        ref = {"type": "measurement", "gap": "gap-2024-01-15-001",
               "at": "2024-01-16T09:00:00+00:00", "verdict": "maybe",
               "wiki_answer": "x"}
        errors = self.check([valid_gap(), ref])
        self.assertTrue(any("verdict" in m for _, m in errors))


class FoldStatus(unittest.TestCase):
    """The spec's normative rule: fold in FILE ORDER, never by 'at'."""

    def fold(self, records):
        return gap_ledger.fold_status([(i + 1, r) for i, r in enumerate(records)])

    def measurement(self, verdict, at="2024-01-16T09:00:00+00:00"):
        return {"type": "measurement", "gap": "gap-2024-01-15-001", "at": at,
                "verdict": verdict, "wiki_answer": "text"}

    def test_a_lone_gap_is_opened(self):
        self.assertEqual(self.fold([valid_gap()]), {"gap-2024-01-15-001": "opened"})

    def test_resolution_alone_does_not_change_status(self):
        res = {"type": "resolution", "gap": "gap-2024-01-15-001",
               "at": "2024-01-16T09:00:00+00:00", "card": "src-2024-01-16-001",
               "wiki_page": "wiki/widget-assembly.md"}
        self.assertEqual(self.fold([valid_gap(), res]),
                         {"gap-2024-01-15-001": "opened"})

    def test_measurement_answered_marks_answered(self):
        self.assertEqual(self.fold([valid_gap(), self.measurement("answered")]),
                         {"gap-2024-01-15-001": "answered"})

    def test_still_missing_reopens_an_answered_gap(self):
        records = [valid_gap(), self.measurement("answered"),
                   self.measurement("still-missing")]
        self.assertEqual(self.fold(records), {"gap-2024-01-15-001": "opened"})

    def test_partial_reopens_an_answered_gap(self):
        records = [valid_gap(), self.measurement("answered"),
                   self.measurement("partial")]
        self.assertEqual(self.fold(records), {"gap-2024-01-15-001": "opened"})

    def test_ratification_marks_unrelated(self):
        rat = {"type": "ratification", "gap": "gap-2024-01-15-001",
               "at": "2024-01-17T09:00:00+00:00", "verdict": "unrelated",
               "reason": "a general language question, not wiki knowledge"}
        self.assertEqual(self.fold([valid_gap(), self.measurement("answered"), rat]),
                         {"gap-2024-01-15-001": "unrelated"})

    def test_fold_uses_file_order_not_timestamps(self):
        """The whole point of the rule. The LAST LINE is 'still-missing' but
        carries an EARLIER 'at' than the line above it. File order wins, so
        the gap is opened; an 'at'-ordered fold would say answered."""
        records = [
            valid_gap(),
            self.measurement("answered", at="2024-02-01T09:00:00+00:00"),
            self.measurement("still-missing", at="2024-01-20T09:00:00+00:00"),
        ]
        self.assertEqual(self.fold(records), {"gap-2024-01-15-001": "opened"})

    def test_independent_gaps_do_not_interfere(self):
        other = valid_gap("gap-2024-01-15-002")
        records = [valid_gap(), other, self.measurement("answered")]
        self.assertEqual(self.fold(records), {"gap-2024-01-15-001": "answered",
                                              "gap-2024-01-15-002": "opened"})


class NextGapId(unittest.TestCase):
    def test_first_of_the_day(self):
        self.assertEqual(gap_ledger.next_gap_id([], "2024-01-15"),
                         "gap-2024-01-15-001")

    def test_nth_of_the_day(self):
        existing = ["gap-2024-01-15-001", "gap-2024-01-15-002"]
        self.assertEqual(gap_ledger.next_gap_id(existing, "2024-01-15"),
                         "gap-2024-01-15-003")

    def test_rolls_over_to_a_new_day(self):
        existing = ["gap-2024-01-15-001", "gap-2024-01-15-002"]
        self.assertEqual(gap_ledger.next_gap_id(existing, "2024-01-16"),
                         "gap-2024-01-16-001")

    def test_ignores_gaps_from_other_days_when_counting(self):
        existing = ["gap-2024-01-14-009", "gap-2024-01-15-001"]
        self.assertEqual(gap_ledger.next_gap_id(existing, "2024-01-15"),
                         "gap-2024-01-15-002")

    def test_fills_after_the_highest_not_the_count(self):
        """A hand-deleted middle id must never cause a collision."""
        existing = ["gap-2024-01-15-001", "gap-2024-01-15-007"]
        self.assertEqual(gap_ledger.next_gap_id(existing, "2024-01-15"),
                         "gap-2024-01-15-008")


class RenderView(unittest.TestCase):
    def test_empty_ledger_renders_a_stable_header(self):
        out = gap_ledger.render_view([])
        self.assertTrue(out.startswith("# Knowledge gaps"))
        self.assertTrue(out.endswith("\n"))
        self.assertIn("No gaps recorded yet.", out)

    def test_render_is_deterministic(self):
        records = [(1, valid_gap())]
        self.assertEqual(gap_ledger.render_view(records),
                         gap_ledger.render_view(records))

    def test_a_gap_appears_with_its_status_and_question(self):
        out = gap_ledger.render_view([(1, valid_gap())])
        self.assertIn("gap-2024-01-15-001", out)
        self.assertIn("opened", out)
        self.assertIn("goroutines and channels", out)

    def test_pipes_in_prose_do_not_break_the_table(self):
        rec = valid_gap()
        rec["question"] = "is it a | or a b?"
        out = gap_ledger.render_view([(1, rec)])
        row = [ln for ln in out.splitlines() if "gap-2024-01-15-001" in ln][0]
        self.assertIn(r"\|", row)
        # Seven columns means eight delimiter pipes. The escaped pipe from
        # the prose contributes to count("|") too, so subtract it back out.
        self.assertEqual(row.count("|") - row.count(r"\|"), 8)

    def test_newlines_in_prose_do_not_break_the_table(self):
        rec = valid_gap()
        rec["question"] = "line one\nline two"
        out = gap_ledger.render_view([(1, rec)])
        self.assertIn("line one line two", out)

    def test_crlf_and_bare_cr_in_prose_do_not_break_the_table(self):
        rec = valid_gap()
        rec["question"] = "line one\r\nline two\rline three"
        out = gap_ledger.render_view([(1, rec)])
        self.assertNotIn("\r\n", out)
        self.assertNotIn("\r", out)
        self.assertIn("line one line two line three", out)

    def test_topics_are_rendered_as_a_comma_separated_cell(self):
        rec = valid_gap()
        rec["topics"] = ["concurrency", "goroutines"]
        out = gap_ledger.render_view([(1, rec)])
        row = [ln for ln in out.splitlines() if "gap-2024-01-15-001" in ln][0]
        self.assertIn("concurrency, goroutines", row)

    def test_absent_resolution_and_ratification_render_empty_not_none(self):
        out = gap_ledger.render_view([(1, valid_gap())])
        self.assertNotIn("None", out)

    def test_resolution_card_is_shown_for_an_answered_gap(self):
        res = {"type": "resolution", "gap": "gap-2024-01-15-001",
               "at": "2024-01-16T09:00:00+00:00", "card": "src-2024-01-16-001",
               "wiki_page": "wiki/widget-assembly.md"}
        meas = {"type": "measurement", "gap": "gap-2024-01-15-001",
                "at": "2024-01-16T10:00:00+00:00", "verdict": "answered",
                "wiki_answer": "covered now"}
        out = gap_ledger.render_view([(1, valid_gap()), (2, res), (3, meas)])
        self.assertIn("src-2024-01-16-001", out)
        self.assertIn("answered", out)

    def test_unrelated_reason_is_shown(self):
        rat = {"type": "ratification", "gap": "gap-2024-01-15-001",
               "at": "2024-01-17T09:00:00+00:00", "verdict": "unrelated",
               "reason": "general language question"}
        out = gap_ledger.render_view([(1, valid_gap()), (2, rat)])
        self.assertIn("general language question", out)


class PiiWarnings(unittest.TestCase):
    def test_clean_record_warns_nothing(self):
        self.assertEqual(gap_ledger.pii_warnings(valid_gap()), [])

    def test_an_email_address_is_flagged(self):
        rec = valid_gap()
        rec["context"] = "raised by someone@example.com"
        self.assertTrue(gap_ledger.pii_warnings(rec))

    def test_a_long_digit_run_is_flagged(self):
        rec = valid_gap()
        rec["prompt_verbatim"] = "why did account 1234567890123 fail"
        self.assertTrue(gap_ledger.pii_warnings(rec))

    def test_short_numbers_are_not_flagged(self):
        rec = valid_gap()
        rec["prompt_verbatim"] = "what does error 404 mean"
        self.assertEqual(gap_ledger.pii_warnings(rec), [])

    def test_the_timestamp_is_never_flagged(self):
        """'at' is a machine field full of digits; flagging it would make
        every single record warn, and a warning that always fires is noise."""
        self.assertEqual(gap_ledger.pii_warnings(valid_gap()), [])

    def test_non_prose_fields_are_not_scanned(self):
        rec = valid_gap()
        rec["session"] = "1234567890123456"
        self.assertEqual(gap_ledger.pii_warnings(rec), [])

    def test_a_package_version_pin_is_not_flagged_as_an_email(self):
        """'name@1.2.3' is common pip-style version-pin prose, not an email:
        its final segment is digits, not a TLD-shaped word. A regex that
        cannot tell the two apart would warn on routine tooling questions,
        and a warning that fires on ordinary prose is noise that gets
        ignored."""
        rec = valid_gap()
        rec["context"] = "why does examplepkg@1.2.3 fail to install"
        self.assertEqual(gap_ledger.pii_warnings(rec), [])


if __name__ == "__main__":
    unittest.main()
