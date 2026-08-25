from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import load_schema
from check_commit_msg import validate
from lint import check_card_citations

CUSTOM_SCHEMA_TEXT = json.dumps(
    {"keys": {"id": {"pattern": r"^ai-\d{4}-\d{2}-\d{2}-\d{3}$"}}})


class CustomizedSchemaIdPatternHonoredZeroCodeChange(unittest.TestCase):
    """The card schema's id.pattern is the single, sole declaration of
    card-id shape: a wiki that customizes it to a totally different id
    family (e.g. 'ai-YYYY-MM-DD-NNN' instead of 'src-YYYY-MM-DD-NNN') must
    be honored by BOTH check_card_citations() and check_commit_msg.py's
    validate() with no further library code change -- the direct proof
    this redesign delivers genericity."""

    def setUp(self):
        self.schema, findings = load_schema(CUSTOM_SCHEMA_TEXT)
        self.assertEqual(findings, [])

    def test_check_card_citations_honors_customized_id_pattern(self):
        files = {
            "wiki/notes.md": "---\ntitle: Notes\ntopics: [x]\n---\n"
                             "As discussed in ai-2024-01-15-001, the model shipped.\n",
            "sources/cards/ai-2024-01-15-001.md": "---\nid: ai-2024-01-15-001\n---\n",
        }
        self.assertEqual(check_card_citations(files, self.schema), [])

    def test_validate_honors_customized_id_pattern(self):
        pattern = self.schema["id"]["pattern"]
        self.assertEqual(
            validate("ingest(ai-2024-01-15-001): summary", card_id_pattern=pattern), [])

    def test_validate_rejects_the_old_default_shape_under_customized_pattern(self):
        """Proves this is genuinely schema-driven, not merely permissive:
        once the schema declares 'ai-...' ids, the library's own former
        default shape ('src-...') is no longer accepted."""
        pattern = self.schema["id"]["pattern"]
        self.assertTrue(
            validate("ingest(src-2026-08-06-001): summary", card_id_pattern=pattern))


if __name__ == "__main__":
    unittest.main()
