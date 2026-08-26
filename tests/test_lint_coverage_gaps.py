"""Close three named test-coverage gaps against T01's forked, unmodified
lint/card-lint/commit-msg logic (plus whatever T03/T04 already changed):
no implementation code changes are needed or made by this file.

1. card_frontmatter_lint.py's _check_value() "list given where scalar
   required" branch (the mirror of test_card_frontmatter_lint.py's existing
   test_scalar_where_a_list_is_required, which covers the opposite branch).
2. lint.py's scan() ENCODING finding, asserted as a returned Finding object
   (severity/code/path/message), not only via a CLI-stdout substring (that
   CLI-stdout coverage already exists in test_lint_cli.py).
3. check_commit_msg.py's EXEMPT_PREFIXES fixup!/squash! exemptions, matching
   the existing Merge/Revert coverage pattern in test_commit_msg.py.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import Finding, SCHEMA_PATH, check_card, load_schema
from check_commit_msg import validate
from lint import scan

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"
FIXTURE_SCHEMA = (FIXTURE / SCHEMA_PATH).read_text(encoding="utf-8")
SCHEMA, _SCHEMA_ERRORS = load_schema(FIXTURE_SCHEMA)

PATH = "sources/cards/src-2024-01-15-001.md"

# Same card as test_card_frontmatter_lint.py's CARD, except 'origin' -- a key
# whose schema rule declares no 'list': true -- is given as a list value.
CARD_WITH_LIST_WHERE_SCALAR_REQUIRED = """---
id: src-2024-01-15-001
date: 2024-01-15
origin: [session, transcript]
trust: stated
topics: [widget-assembly]
---
## Claims
- a claim
"""


class CardValueListWhereScalarRequired(unittest.TestCase):
    """_check_value()'s other branch: `isinstance(value, list)` true but
    `rules.get("list")` falsy -> CARD_VALUE 'must be a single value, not a
    list'. No existing test supplied a list value for a non-list rule key."""

    def test_card_value_list_where_scalar_required(self):
        findings = check_card(PATH, CARD_WITH_LIST_WHERE_SCALAR_REQUIRED,
                              SCHEMA, lambda p: False)
        self.assertEqual(findings, [
            Finding("ERROR", "CARD_VALUE", PATH,
                    "'origin' must be a single value, not a list"),
        ])


class EncodingFindingIsAFindingObject(unittest.TestCase):
    """scan() returns (files, encoding_findings); a non-UTF-8 file produces
    Finding("ERROR", "ENCODING", rel, "file is not valid UTF-8"). Asserted
    directly on the returned Finding's fields, not by grepping CLI stdout
    for the string "ENCODING" (that coverage already exists in
    test_lint_cli.py's test_cli_exit_one_on_invalid_utf8)."""

    def test_encoding_finding_is_a_finding_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki").mkdir()
            (root / "wiki" / "bad.md").write_bytes(b"---\n\xff\xfe garbage")
            files, enc = scan(root)

        self.assertNotIn("wiki/bad.md", files)
        self.assertEqual(len(enc), 1)
        finding = enc[0]
        self.assertEqual(finding.severity, "ERROR")
        self.assertEqual(finding.code, "ENCODING")
        self.assertEqual(finding.path, "wiki/bad.md")
        self.assertEqual(finding.message, "file is not valid UTF-8")
        self.assertEqual(finding,
                         Finding("ERROR", "ENCODING", "wiki/bad.md",
                                 "file is not valid UTF-8"))


class FixupAndSquashExempt(unittest.TestCase):
    """check_commit_msg.py's EXEMPT_PREFIXES = ("Merge", "Revert", "fixup!",
    "squash!") -- test_commit_msg.py's ValidSubjects.test_merge_and_revert_are_exempt
    covers the first two; this covers the fixup!/squash! rebase-autosquash
    prefixes the same way."""

    def test_fixup_and_squash_exempt(self):
        self.assertEqual(validate("fixup! anything"), [])
        self.assertEqual(validate("squash! anything"), [])


if __name__ == "__main__":
    unittest.main()
