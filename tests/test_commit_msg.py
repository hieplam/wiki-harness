import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_commit_msg import validate


class ValidSubjects(unittest.TestCase):
    def test_ingest_with_card_ref(self):
        self.assertEqual(validate("ingest(src-2026-08-06-001): pay-run quarantine basics"), [])

    def test_lint_without_ref(self):
        self.assertEqual(validate("lint: fix broken link in pay-run"), [])

    def test_schema_and_chore(self):
        self.assertEqual(validate("schema: define card trust levels"), [])
        self.assertEqual(validate("chore: add lint script"), [])

    def test_merge_and_revert_are_exempt(self):
        self.assertEqual(validate("Merge branch 'feature/x'"), [])
        self.assertEqual(validate("Revert \"chore: add lint script\""), [])

    def test_body_and_comment_lines_ignored(self):
        msg = "chore: add hook\n\nTouched: scripts/x.py\n# comment line from git"
        self.assertEqual(validate(msg), [])


class InvalidSubjects(unittest.TestCase):
    def test_unknown_op(self):
        self.assertTrue(validate("feat: add thing"))

    def test_ingest_missing_ref(self):
        self.assertTrue(validate("ingest: pay-run quarantine basics"))

    def test_ingest_malformed_ref(self):
        self.assertTrue(validate("ingest(src-123): bad ref"))

    def test_empty_message(self):
        self.assertTrue(validate(""))

    def test_missing_summary(self):
        self.assertTrue(validate("chore: "))


if __name__ == "__main__":
    unittest.main()
