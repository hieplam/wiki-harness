import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import parse_frontmatter, resolve
from lint import extract_links

CARD = """---
id: src-2026-08-06-001
date: 2026-08-06
origin: session
trust: stated
topics: [partner-commissions, pay-run]
---
## Claims
- something
"""


class ParseFrontmatter(unittest.TestCase):
    def test_valid_card(self):
        meta, errors = parse_frontmatter(CARD)
        self.assertEqual(errors, [])
        self.assertEqual(meta["id"], "src-2026-08-06-001")
        self.assertEqual(meta["topics"], ["partner-commissions", "pay-run"])

    def test_missing_frontmatter(self):
        meta, errors = parse_frontmatter("# just a page\n")
        self.assertIsNone(meta)
        self.assertTrue(errors)

    def test_unclosed_frontmatter(self):
        meta, errors = parse_frontmatter("---\nid: x\n")
        self.assertTrue(any("not closed" in e for e in errors))

    def test_malformed_line(self):
        _, errors = parse_frontmatter("---\nnot a kv line\n---\n")
        self.assertTrue(any("line 2" in e for e in errors))


class ExtractLinks(unittest.TestCase):
    def test_relative_links_kept_anchors_stripped(self):
        text = "See [pay run](./pay-run.md#quarantine) and [card](../sources/cards/src-2026-08-06-001.md)."
        self.assertEqual(
            extract_links(text),
            ["./pay-run.md", "../sources/cards/src-2026-08-06-001.md"],
        )

    def test_external_and_anchor_links_skipped(self):
        text = "[gh](https://github.com) [mail](mailto:a@b.c) [top](#top)"
        self.assertEqual(extract_links(text), [])


class Resolve(unittest.TestCase):
    def test_sibling(self):
        self.assertEqual(resolve("wiki/pay-run.md", "./partner-commissions.md"),
                         "wiki/partner-commissions.md")

    def test_updir(self):
        self.assertEqual(
            resolve("wiki/pay-run.md", "../sources/cards/src-2026-08-06-001.md"),
            "sources/cards/src-2026-08-06-001.md",
        )

    def test_from_root_file(self):
        self.assertEqual(resolve("index.md", "./wiki/pay-run.md"), "wiki/pay-run.md")

    def test_updir_past_root_is_out_of_root(self):
        self.assertEqual(resolve("wiki/pay-run.md", "../../index.md"),
                         "<out-of-root>/../../index.md")


if __name__ == "__main__":
    unittest.main()
