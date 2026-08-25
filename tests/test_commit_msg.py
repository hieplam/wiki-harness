import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_commit_msg import validate

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_commit_msg.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"


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
    INGEST_REF_ERROR = ["ingest commits require ref = card id, e.g. "
                        "'ingest(src-2026-08-06-001): summary'"]

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

    def test_two_id_ref_rejected(self):
        """A ref citing two card ids must still be rejected with the existing
        ingest-ref error -- proves validate() keeps using the schema's
        anchored, whole-value id.pattern (not an unanchored scan) even after
        the pattern becomes schema-driven."""
        self.assertEqual(
            validate("ingest(src-2026-08-06-001 src-2026-08-06-002): two ids"),
            self.INGEST_REF_ERROR)

    def test_suffix_garbage_ref_rejected(self):
        """A ref with trailing garbage after an otherwise-valid id must still
        fail the anchored match."""
        self.assertEqual(
            validate("ingest(src-2026-08-06-001x): garbage suffix"),
            self.INGEST_REF_ERROR)


class CustomCardIdPattern(unittest.TestCase):
    """validate()'s card_id_pattern parameter defaults to
    DEFAULT_CARD_ID_PATTERN (byte-identical to the old hardcoded CARD_ID_RE,
    so every existing 1-arg call above stays green unmodified) but can be
    overridden with any schema-declared id.pattern."""

    CUSTOM_PATTERN = r"^ai-\d{4}-\d{2}-\d{2}-\d{3}$"

    def test_customized_pattern_accepts_its_own_shape(self):
        self.assertEqual(
            validate("ingest(ai-2024-01-15-001): summary",
                     card_id_pattern=self.CUSTOM_PATTERN),
            [])

    def test_customized_pattern_rejects_the_old_default_shape(self):
        self.assertTrue(
            validate("ingest(src-2026-08-06-001): summary",
                     card_id_pattern=self.CUSTOM_PATTERN))


class RootFlagSchemaDriven(unittest.TestCase):
    """main()'s new --root edge reads <root>/sources/cards/card-schema.json
    and threads its id.pattern into validate(), so the CLI itself -- not
    just the pure function -- is schema-driven, never a second hardcoded
    declaration of card-id shape."""

    def run_cli(self, root, message):
        with tempfile.TemporaryDirectory() as msg_dir:
            msg_file = Path(msg_dir) / "COMMIT_EDITMSG"
            msg_file.write_text(message, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), str(msg_file)],
                capture_output=True, text=True)

    def test_customized_schema_id_pattern_is_honored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(FIXTURE / "sources", root / "sources")
            (root / "sources" / "cards" / "card-schema.json").write_text(
                json.dumps({"keys": {"id": {"pattern": r"^ai-\d{4}-\d{2}-\d{2}-\d{3}$"}}}),
                encoding="utf-8")
            result = self.run_cli(root, "ingest(ai-2024-01-15-001): sample summary")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_schema_falls_back_to_default_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_cli(root, "ingest(src-2026-08-06-001): sample summary")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schema_missing_id_key_falls_back_to_default_pattern(self):
        """load_schema() never requires an 'id' key -- a schema that is
        otherwise fully valid but declares no 'id' rules at all must not
        crash main() with a KeyError; it falls back to
        DEFAULT_CARD_ID_PATTERN exactly like a missing schema file."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources" / "cards").mkdir(parents=True)
            (root / "sources" / "cards" / "card-schema.json").write_text(
                json.dumps({"keys": {"title": {"required": True}}}), encoding="utf-8")
            result = self.run_cli(root, "ingest(src-2026-08-06-001): sample summary")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_schema_id_without_pattern_falls_back_to_default_pattern(self):
        """load_schema() never requires a 'pattern' rule under 'id' -- an
        'id' key with only 'required' declared is a legal, real-world schema
        shape (other real keys, e.g. origin/trust, ship with no 'pattern' at
        all). It must not crash main() with a KeyError; it falls back to
        DEFAULT_CARD_ID_PATTERN."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources" / "cards").mkdir(parents=True)
            (root / "sources" / "cards" / "card-schema.json").write_text(
                json.dumps({"keys": {"id": {"required": True}}}), encoding="utf-8")
            result = self.run_cli(root, "ingest(src-2026-08-06-001): sample summary")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
