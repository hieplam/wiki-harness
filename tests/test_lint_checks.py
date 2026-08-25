from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import SCHEMA_PATH, check_card, load_schema
from lint import (check_broken_links, check_card_citations, check_cards,
                  check_frontmatter, check_index_sync, check_orphans)

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "templates"

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"
FIXTURE_SCHEMA = (FIXTURE / SCHEMA_PATH).read_text(encoding="utf-8")
SCHEMA, _SCHEMA_ERRORS = load_schema(FIXTURE_SCHEMA)

GOOD_CARD = """---
id: src-2024-01-15-001
date: 2024-01-15
origin: session
trust: stated
topics: [widget-assembly]
---
## Claims
- a claim
"""

GOOD_PAGE = """---
title: Widget assembly
topics: [widget-assembly]
---
The weekly batch. Details in
[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).
See also [quality checks](./quality-checks.md).
"""

GOOD_PAGE_2 = """---
title: Quality checks
topics: [widget-assembly]
---
Run after the [widget assembly](./widget-assembly.md), per
[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).
"""


def good_files():
    return {
        "index.md": "- [Widget assembly](./wiki/widget-assembly.md)\n"
                    "- [Quality checks](./wiki/quality-checks.md)\n",
        "wiki/widget-assembly.md": GOOD_PAGE,
        "wiki/quality-checks.md": GOOD_PAGE_2,
        "sources/cards/src-2024-01-15-001.md": GOOD_CARD,
        SCHEMA_PATH: FIXTURE_SCHEMA,
    }


class BrokenLinks(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(check_broken_links(good_files()), [])

    def test_broken(self):
        files = good_files()
        files["wiki/widget-assembly.md"] += "\n[ghost](./ghost.md)\n"
        findings = check_broken_links(files)
        self.assertEqual([f.code for f in findings], ["LINK"])
        self.assertIn("./ghost.md", findings[0].message)


class Orphans(unittest.TestCase):
    def test_cross_linked_pages_are_not_orphans(self):
        self.assertEqual(check_orphans(good_files()), [])

    def test_unlinked_page_is_orphan_warning(self):
        files = good_files()
        files["wiki/lonely.md"] = "---\ntitle: Lonely\ntopics: [misc]\n---\nno one links me\n"
        findings = check_orphans(files)
        self.assertEqual([(f.severity, f.code, f.path) for f in findings],
                         [("WARN", "ORPHAN", "wiki/lonely.md")])

    def test_self_link_does_not_count(self):
        files = {"wiki/self.md": "---\ntitle: S\ntopics: [x]\n---\n[me](./self.md)\n"}
        self.assertEqual(len(check_orphans(files)), 1)


class CardCitations(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(check_card_citations(good_files(), SCHEMA), [])

    def test_cite_unknown_card(self):
        files = good_files()
        files["wiki/widget-assembly.md"] += "\nAlso src-2099-01-01-001 says so.\n"
        findings = check_card_citations(files, SCHEMA)
        self.assertEqual([f.code for f in findings], ["CITE"])

    def test_unfiled_card(self):
        files = good_files()
        files["sources/cards/src-2024-01-15-002.md"] = GOOD_CARD.replace(
            "src-2024-01-15-001", "src-2024-01-15-002")
        findings = check_card_citations(files, SCHEMA)
        self.assertEqual([f.code for f in findings], ["UNFILED"])
        self.assertEqual(findings[0].path, "sources/cards/src-2024-01-15-002.md")

    def test_link_format_citation_reports_once(self):
        files = good_files()
        files["wiki/widget-assembly.md"] += (
            "\n[src-2099-01-01-001](../sources/cards/src-2099-01-01-001.md)\n")
        findings = check_card_citations(files, SCHEMA)
        self.assertEqual([f.code for f in findings], ["CITE"])

    def test_mid_sentence_citation_still_found(self):
        """check_card_citations scans prose with an unanchored pattern (via
        card_id_scan_pattern), so a card id embedded mid-sentence -- not
        wrapped in a markdown link -- still counts as a citation."""
        files = good_files()
        files["sources/cards/src-2024-01-15-002.md"] = GOOD_CARD.replace(
            "src-2024-01-15-001", "src-2024-01-15-002")
        files["wiki/widget-assembly.md"] += (
            "\nAs discussed in src-2024-01-15-002, the batch runs weekly.\n")
        findings = check_card_citations(files, SCHEMA)
        self.assertEqual(findings, [])

    def test_falls_back_to_default_pattern_when_schema_is_none(self):
        """schema=None only when load_schema() could not load one at all --
        check_cards() already reports the CARD_SCHEMA finding for that case,
        so this check quietly falls back to DEFAULT_CARD_ID_PATTERN instead
        of reporting it a second time."""
        self.assertEqual(check_card_citations(good_files(), None), [])


class Frontmatter(unittest.TestCase):
    """Card frontmatter is checked by tests/test_card_frontmatter_lint.py; what
    remains here is the wiki-page half plus the routing between the two."""

    def test_clean(self):
        self.assertEqual(check_frontmatter(good_files()), [])

    def test_wiki_page_missing_title(self):
        files = good_files()
        files["wiki/widget-assembly.md"] = GOOD_PAGE.replace("title: Widget assembly\n", "")
        findings = check_frontmatter(files)
        self.assertTrue(any("title" in f.message for f in findings))

    def test_cards_are_routed_to_the_card_linter(self):
        files = good_files()
        files["sources/cards/src-2024-01-15-001.md"] = GOOD_CARD.replace(
            "---\n## Claims", "source_author: Michael\n---\n## Claims")
        findings = check_cards(files)
        self.assertEqual([f.code for f in findings], ["CARD_KEY"])

    def test_missing_schema_file_blocks_all_cards(self):
        files = good_files()
        del files[SCHEMA_PATH]
        findings = check_cards(files)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])


class NestedAgentsFiles(unittest.TestCase):
    """A nested AGENTS.md holds rules, not content, so the card and wiki-page checks
    must skip it — otherwise progressive disclosure is impossible."""

    def files_with_rules(self):
        files = good_files()
        rules = "# Rules\nSee [widget assembly](./widget-assembly.md).\n"   # no frontmatter on purpose
        files["wiki/AGENTS.md"] = rules
        files["sources/cards/AGENTS.md"] = "# Rules\nCard format lives here.\n"
        return files

    def test_not_treated_as_card_or_page(self):
        files = self.files_with_rules()
        self.assertEqual(check_frontmatter(files), [])
        self.assertEqual(check_index_sync(files), [])
        self.assertEqual(check_card_citations(files, SCHEMA), [])
        self.assertEqual(check_orphans(files), [])

    def test_links_are_still_checked(self):
        files = self.files_with_rules()
        files["wiki/AGENTS.md"] = "# Rules\nSee [gone](./no-such-page.md).\n"
        findings = check_broken_links(files)
        self.assertTrue(any(f.path == "wiki/AGENTS.md" for f in findings))


class TestCardKeyDoc(unittest.TestCase):
    """templates/sources.cards.AGENTS.md's CARD_KEY worked example must byte-match
    the real runtime message check_card() produces for the same fixture input -
    including the "Declared keys: ..." suffix the doc used to omit."""

    TEMPLATE = TEMPLATE_ROOT / "sources.cards.AGENTS.md"

    def _doc_worked_example(self):
        """Extract (path, message) from the plain-fenced ERROR CARD_KEY block,
        rejoining its wrapped continuation lines into the single-line form
        check_card() actually produces."""
        text = self.TEMPLATE.read_text(encoding="utf-8")
        blocks = re.findall(r"```\n(.*?ERROR CARD_KEY.*?)```", text, re.DOTALL)
        self.assertEqual(len(blocks), 1,
                         "expected exactly one ERROR CARD_KEY worked example block")
        lines = [ln for ln in blocks[0].splitlines() if ln.strip()]
        m = re.match(r"^ERROR CARD_KEY (\S+): (.*)$", lines[0])
        self.assertIsNotNone(
            m, "worked example's first line must read 'ERROR CARD_KEY <path>: <msg>'")
        path, first_segment = m.group(1), m.group(2)
        message = " ".join([first_segment] + [ln.strip() for ln in lines[1:]])
        return path, message

    def test_card_key_worked_example_matches_runtime_message(self):
        schema, schema_findings = load_schema(FIXTURE_SCHEMA)
        self.assertEqual(schema_findings, [])
        card_text = (
            "---\n"
            "id: src-2024-01-15-003\n"
            "date: 2024-01-15\n"
            "origin: session\n"
            "trust: stated\n"
            "topics: [widget-assembly]\n"
            "source_author: Michael\n"
            "---\n"
            "## Claims\n- a claim\n"
        )
        findings = check_card("sources/cards/src-2024-01-15-003.md", card_text,
                              schema, lambda p: True)
        card_key = [f for f in findings if f.code == "CARD_KEY"]
        self.assertEqual(len(card_key), 1, findings)

        doc_path, doc_message = self._doc_worked_example()
        self.assertEqual(doc_path, card_key[0].path)
        self.assertEqual(doc_message, card_key[0].message)


if __name__ == "__main__":
    unittest.main()
