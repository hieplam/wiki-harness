from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from string import Template

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import parse_frontmatter
from lint import check_broken_links, extract_links, resolve, run, scan

ROOT = Path(__file__).resolve().parent.parent
LINT_PY = ROOT / "scripts" / "lint.py"
TEMPLATE_ROOT = ROOT / "templates"
CARDS_AGENTS_TEMPLATE = ROOT / "templates" / "sources.cards.AGENTS.md"
RECIPES_TEMPLATE = ROOT / "templates" / "recipes.md"
FIXTURE = ROOT / "tests" / "fixtures" / "sample-wiki"


def render(text, variables):
    """T12's own minimal renderer: fills a TEMPLATE-class source's ${var}
    placeholders (stdlib string.Template) from `variables`. Pure -- text
    and a dict in, text out. Test-only: init.py's real rendering step is
    T13's job (out of scope here); this exists only so this task's own
    render-determinism/README tests can exercise the .tmpl SOURCE files
    this task authors without waiting on init.py to exist."""
    return Template(text).substitute(variables)


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


class TemplateRenderDeterminism(unittest.TestCase):
    """T12: rendering the same TEMPLATE-class source with the same variable
    dict twice must produce byte-identical output -- init.py's future
    rendering step (T13) can safely be invoked any number of times (init,
    then every later upgrade) without ever depending on hidden state."""

    VARS = {
        "wiki_title": "Sample Wiki",
        "org_name": "Sample Org",
        "content_language": "English",
        "repo_name": "sample-wiki",
    }

    def test_templates_render_deterministically(self):
        for name in ("AGENTS.root.md.tmpl", "README.md.tmpl"):
            text = (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
            first = render(text, self.VARS)
            second = render(text, self.VARS)
            self.assertEqual(first, second)
            # Proves this is a real substitution, not an identity no-op on
            # text that happens to carry no placeholders.
            self.assertNotIn("${", first)


class ReadmeNoHandCreatedClaudeMd(unittest.TestCase):
    """README.md.tmpl v3 (A7): init seeds CLAUDE.md directly, tracked,
    every time, so the template must never instruct a human to create it
    by hand -- the exact ogp-wiki README.md:13 line this plan retires
    ('Claude Code users: create a local CLAUDE.md containing the single
    line @AGENTS.md')."""

    HAND_CREATION_RE = re.compile(
        r"create\s+(?:a\s+)?(?:local\s+)?`?CLAUDE\.md`?", re.IGNORECASE)

    def test_readme_has_no_claude_md_hand_creation_instruction(self):
        text = render((TEMPLATE_ROOT / "README.md.tmpl").read_text(encoding="utf-8"),
                      TemplateRenderDeterminism.VARS)
        self.assertNotRegex(text, self.HAND_CREATION_RE)


class GitignoreSnippetNoClaudeMd(unittest.TestCase):
    """templates/gitignore.snippet v3 (A7): CLAUDE.md is now tracked, so
    the seeded .gitignore must no longer list it (was .gitignore:3 in
    ogp-wiki today)."""

    def test_gitignore_snippet_has_no_claude_md_line(self):
        text = (TEMPLATE_ROOT / "gitignore.snippet").read_text(encoding="utf-8")
        self.assertNotIn("CLAUDE.md", text)


class ClaudeTemplatesSingleLineImport(unittest.TestCase):
    """CLAUDE.root.tmpl / CLAUDE.nested.tmpl (both MANAGED, v3 A7): each
    renders to the exact single line '@AGENTS.md' and nothing else --
    Claude Code's own relative-to-importer resolution means a nested stub
    never needs to also re-import the root file."""

    def test_claude_templates_are_single_line_import(self):
        for name in ("CLAUDE.root.tmpl", "CLAUDE.nested.tmpl"):
            text = (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
            self.assertEqual(text, "@AGENTS.md\n")


class SeededClaudeMdZeroFindings(unittest.TestCase):
    """T08 pre-emptively added 'CLAUDE.md' to RULES_FILES so a nested,
    tracked CLAUDE.md stub never trips FM/INDEX/ORPHAN/CARD_FM -- this
    proves that promise against the real, rendered CLAUDE.nested.tmpl
    bytes, seeded into the two nested dirs lint treats as wiki-page/card
    content (wiki/ and sources/cards/). If this test fails, the fix
    belongs in T08's lint.py, not in this task's templates."""

    ATTRIBUTABLE_CODES = frozenset({"FM", "INDEX", "ORPHAN", "CARD_FM"})
    TARGET_PATHS = frozenset({"wiki/CLAUDE.md", "sources/cards/CLAUDE.md"})

    def test_seeded_claude_md_produces_zero_wiki_page_and_card_findings(self):
        files, encoding_findings = scan(FIXTURE)
        self.assertEqual(encoding_findings, [])
        claude_text = (TEMPLATE_ROOT / "CLAUDE.nested.tmpl").read_text(encoding="utf-8")
        files["wiki/CLAUDE.md"] = claude_text
        files["sources/cards/CLAUDE.md"] = claude_text

        findings = run(files, [])

        attributable = [f for f in findings
                        if f.code in self.ATTRIBUTABLE_CODES
                        and f.path in self.TARGET_PATHS]
        self.assertEqual(attributable, [])


if __name__ == "__main__":
    unittest.main()
