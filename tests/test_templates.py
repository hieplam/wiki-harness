from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent
LINT_PY = ROOT / "scripts" / "lint.py"
CARDS_AGENTS_TEMPLATE = ROOT / "templates" / "sources.cards.AGENTS.md"


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


if __name__ == "__main__":
    unittest.main()
