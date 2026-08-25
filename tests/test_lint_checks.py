import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import SCHEMA_PATH
from lint import (check_broken_links, check_card_citations, check_cards,
                  check_frontmatter, check_index_sync, check_orphans)

GOOD_CARD = """---
id: src-2026-08-06-001
date: 2026-08-06
origin: session
trust: stated
topics: [pay-run]
---
## Claims
- a claim
"""

GOOD_PAGE = """---
title: Pay run
topics: [pay-run]
---
The Friday batch. Details in
[src-2026-08-06-001](../sources/cards/src-2026-08-06-001.md).
See also [partner commissions](./partner-commissions.md).
"""

GOOD_PAGE_2 = """---
title: Partner commissions
topics: [pay-run]
---
Paid via the [pay run](./pay-run.md), per
[src-2026-08-06-001](../sources/cards/src-2026-08-06-001.md).
"""


def good_files():
    return {
        "index.md": "- [Pay run](./wiki/pay-run.md)\n"
                    "- [Partner commissions](./wiki/partner-commissions.md)\n",
        "wiki/pay-run.md": GOOD_PAGE,
        "wiki/partner-commissions.md": GOOD_PAGE_2,
        "sources/cards/src-2026-08-06-001.md": GOOD_CARD,
        SCHEMA_PATH: (Path(__file__).resolve().parent.parent
                      / SCHEMA_PATH).read_text(encoding="utf-8"),
    }


class BrokenLinks(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(check_broken_links(good_files()), [])

    def test_broken(self):
        files = good_files()
        files["wiki/pay-run.md"] += "\n[ghost](./ghost.md)\n"
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
        self.assertEqual(check_card_citations(good_files()), [])

    def test_cite_unknown_card(self):
        files = good_files()
        files["wiki/pay-run.md"] += "\nAlso src-2099-01-01-001 says so.\n"
        findings = check_card_citations(files)
        self.assertEqual([f.code for f in findings], ["CITE"])

    def test_unfiled_card(self):
        files = good_files()
        files["sources/cards/src-2026-08-06-002.md"] = GOOD_CARD.replace(
            "src-2026-08-06-001", "src-2026-08-06-002")
        findings = check_card_citations(files)
        self.assertEqual([f.code for f in findings], ["UNFILED"])
        self.assertEqual(findings[0].path, "sources/cards/src-2026-08-06-002.md")

    def test_link_format_citation_reports_once(self):
        files = good_files()
        files["wiki/pay-run.md"] += (
            "\n[src-2099-01-01-001](../sources/cards/src-2099-01-01-001.md)\n")
        findings = check_card_citations(files)
        self.assertEqual([f.code for f in findings], ["CITE"])


class Frontmatter(unittest.TestCase):
    """Card frontmatter is checked by tests/test_card_frontmatter_lint.py; what
    remains here is the wiki-page half plus the routing between the two."""

    def test_clean(self):
        self.assertEqual(check_frontmatter(good_files()), [])

    def test_wiki_page_missing_title(self):
        files = good_files()
        files["wiki/pay-run.md"] = GOOD_PAGE.replace("title: Pay run\n", "")
        findings = check_frontmatter(files)
        self.assertTrue(any("title" in f.message for f in findings))

    def test_cards_are_routed_to_the_card_linter(self):
        files = good_files()
        files["sources/cards/src-2026-08-06-001.md"] = GOOD_CARD.replace(
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
        rules = "# Rules\nSee [pay run](./pay-run.md).\n"   # no frontmatter on purpose
        files["wiki/AGENTS.md"] = rules
        files["sources/cards/AGENTS.md"] = "# Rules\nCard format lives here.\n"
        return files

    def test_not_treated_as_card_or_page(self):
        files = self.files_with_rules()
        self.assertEqual(check_frontmatter(files), [])
        self.assertEqual(check_index_sync(files), [])
        self.assertEqual(check_card_citations(files), [])
        self.assertEqual(check_orphans(files), [])

    def test_links_are_still_checked(self):
        files = self.files_with_rules()
        files["wiki/AGENTS.md"] = "# Rules\nSee [gone](./no-such-page.md).\n"
        findings = check_broken_links(files)
        self.assertTrue(any(f.path == "wiki/AGENTS.md" for f in findings))


if __name__ == "__main__":
    unittest.main()
