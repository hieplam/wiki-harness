from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import parse_frontmatter
from lint import check_broken_links, extract_links, resolve

ROOT = Path(__file__).resolve().parent.parent
LINT_PY = ROOT / "scripts" / "lint.py"
CARDS_AGENTS_TEMPLATE = ROOT / "templates" / "sources.cards.AGENTS.md"
RECIPES_TEMPLATE = ROOT / "templates" / "recipes.md"


def _module_docstring(path):
    """path -> the text of its first triple-quoted docstring. Pure string
    parsing; the caller supplies the already-read-from-disk text via `path`
    only for this module's tests, which read it themselves (impure edge)."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r'"""(.*?)"""', text, re.DOTALL)
    return m.group(1) if m else ""


class NoDanglingSpecReference(unittest.TestCase):
    """scripts/lint.py's module docstring used to cite a numbered spec section
    (plan-v3.md is a task plan, not a numbered spec - the reference was a
    stale fork-over artifact pointing at nothing this library has)."""

    def test_no_dangling_spec_reference(self):
        docstring = _module_docstring(LINT_PY)
        self.assertNotIn("section 7.1", docstring.lower())
        self.assertNotIn("§7.1", docstring)


class WorkedExampleConsistency(unittest.TestCase):
    """The frontmatter Example block in templates/sources.cards.AGENTS.md must not
    cite a real ogp-wiki card id, and its raw: presence must match its origin's
    real-world pattern (origin: session -> no raw artifact, since wiki-born
    knowledge has nothing to point at)."""

    # Real ogp-wiki card ids as of T03 -- hardcoded rather than read from the
    # ogp-wiki checkout at test time, per the library's own self-contained
    # suite rule (see test_genericity.SyntheticFixtureNotOgpCorpus).
    KNOWN_REAL_CARD_IDS = ("src-2026-08-06-001",)

    def _example_frontmatter(self):
        text = CARDS_AGENTS_TEMPLATE.read_text(encoding="utf-8")
        blocks = re.findall(r"```markdown\n(.*?)\n```", text, re.DOTALL)
        self.assertEqual(len(blocks), 1,
                         "expected exactly one frontmatter Example block")
        meta, errors = parse_frontmatter(blocks[0])
        self.assertEqual(errors, [])
        return meta

    def test_worked_example_is_self_consistent(self):
        meta = self._example_frontmatter()
        self.assertNotIn(meta["id"], self.KNOWN_REAL_CARD_IDS)
        if meta.get("origin") == "session":
            self.assertNotIn("raw", meta)


class SourceCardsAgentsRecipesSplit(unittest.TestCase):
    """T10: sources/cards/AGENTS.md splits into a MANAGED mechanism file
    (templates/sources.cards.AGENTS.md) plus a SEEDED templates/recipes.md
    holding the trust-meanings table and the per-origin recipes table that
    used to live inline, linked by one plain relative markdown link -- see
    plan/briefs/T10.md. Depends on T08's RULES_FILES generalization
    already covering sources/cards/recipes.md with zero CARD_* findings
    (see test_lint_checks.RulesFilesGeneralization)."""

    # The exact table blocks that lived inline in sources/cards/AGENTS.md
    # before the split (T03's fixed wording), captured here so the test
    # proves recipes.md's content is byte-equivalent to what was cut, not
    # merely that "some table" exists.
    TRUST_TABLE = (
        "| trust | meaning |\n"
        "|---|---|\n"
        "| `verified-in-code` | Confirmed against source code or observed system behaviour |\n"
        "| `stated` | Asserted by a person or document, unverified |\n"
        "| `hearsay` | Second-hand |"
    )

    PER_ORIGIN_TABLE = (
        "| origin | extract |\n"
        "|---|---|\n"
        "| `session` | Verified findings, decisions made, gotchas discovered |\n"
        "| `transcript` | Speakers/personas, decisions + owners, commitments |\n"
        "| `jira` | Problem → root cause → fix → affected services |\n"
        "| `slack` | The question + the tribal answer |\n"
        "| `confluence` / `research` | Concepts, definitions, procedures |"
    )

    def test_split_files_produce_zero_link_findings(self):
        """Assembles the rendered mechanism file + recipes.md directly from
        template source (no init.py involved -- it does not exist yet at
        this point in the task sequence) and runs lint.py's own
        check_broken_links against that hand-built minimal file set. The
        mechanism file's other, pre-existing link targets are stubbed in as
        empty existence-only entries, derived from the mechanism file's own
        links rather than hardcoded, so the assertion below is about the
        recipes.md split specifically, not an artifact of an incomplete
        fixture."""
        mechanism_text = CARDS_AGENTS_TEMPLATE.read_text(encoding="utf-8")
        files = {
            "sources/cards/AGENTS.md": mechanism_text,
            "sources/cards/recipes.md": RECIPES_TEMPLATE.read_text(encoding="utf-8"),
        }
        for target in extract_links(mechanism_text):
            files.setdefault(resolve("sources/cards/AGENTS.md", target), "")
        findings = check_broken_links(files)
        self.assertEqual(findings, [])

    def test_recipes_md_content_matches_split_source(self):
        recipes_text = RECIPES_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn(self.TRUST_TABLE, recipes_text)
        self.assertIn(self.PER_ORIGIN_TABLE, recipes_text)

        # The mechanism file no longer carries the tables themselves -- only
        # a plain relative markdown link where they used to be.
        mechanism_text = CARDS_AGENTS_TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn(self.TRUST_TABLE, mechanism_text)
        self.assertNotIn(self.PER_ORIGIN_TABLE, mechanism_text)
        self.assertIn("(./recipes.md)", mechanism_text)


if __name__ == "__main__":
    unittest.main()
