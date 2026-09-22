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


if __name__ == "__main__":
    unittest.main()
