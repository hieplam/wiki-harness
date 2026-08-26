from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from string import Template
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import card_frontmatter_lint
import lint
from card_frontmatter_lint import SCHEMA_PATH, check_card, load_schema
from lint import (MANIFEST_FILENAME, check_broken_links, check_card_citations,
                  check_cards, check_frontmatter, check_index_sync,
                  check_orphans, run)
from manifest import compute_manifest, write_manifest

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

    def test_falls_back_to_default_pattern_when_schema_has_no_id_pattern(self):
        """load_schema() only requires a non-empty 'keys' object whose entries
        use recognized rule names -- it never requires an 'id' key or a
        'pattern' rule under 'id'. A schema that load_schema() accepts as
        fully valid but that omits 'id' entirely, or declares 'id' with no
        'pattern' rule, must not crash this check with a KeyError; it falls
        back to DEFAULT_CARD_ID_PATTERN exactly like the schema=None case."""
        for schema_text in ('{"keys": {"title": {"required": true}}}',
                            '{"keys": {"id": {"required": true}}}'):
            schema, findings = load_schema(schema_text)
            self.assertEqual(findings, [])
            self.assertEqual(check_card_citations(good_files(), schema), [])

    def test_syntactically_invalid_id_pattern_is_rejected_by_load_schema(self):
        """load_schema() now validates that a 'pattern' rule's string value
        is syntactically valid regex, so this schema fails closed there --
        schema is None, and this check falls back to DEFAULT_CARD_ID_PATTERN
        exactly like the schema=None case, never reaching an unguarded
        re.compile() with the bad pattern."""
        schema, findings = load_schema(
            json.dumps({"keys": {"id": {"pattern": "^src-["}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])
        self.assertEqual(check_card_citations(good_files(), schema), [])

    def test_id_pattern_with_capturing_groups_extracts_whole_match(self):
        """A schema id.pattern may declare ordinary regex capturing groups
        (e.g. (\\d{4}) instead of the non-capturing (?:\\d{4})) -- an
        entirely common way to author a pattern. re.findall() would return
        tuples of the captured subgroups instead of the whole match,
        silently misreporting every citation as unknown/unfiled. The scan
        must extract the whole match regardless of how many groups the
        pattern has."""
        schema, findings = load_schema(json.dumps(
            {"keys": {"id": {"pattern": r"^ai-(\d{4})-(\d{2})-(\d{2})-(\d{3})$"}}}))
        self.assertEqual(findings, [])
        files = {
            "wiki/notes.md": "---\ntitle: Notes\ntopics: [x]\n---\n"
                             "As discussed in ai-2024-01-15-001, the model shipped.\n",
            "sources/cards/ai-2024-01-15-001.md": "---\nid: ai-2024-01-15-001\n---\n",
        }
        self.assertEqual(check_card_citations(files, schema), [])

    def test_escaped_trailing_dollar_in_id_pattern_is_rejected_before_scanning(self):
        """A schema id.pattern ending in an escaped literal '\\$' (an odd
        number of immediately preceding backslashes, not the regex
        end-anchor) does not satisfy the id.pattern anchor contract --
        load_schema() rejects it with a CARD_SCHEMA finding instead of
        letting check_card_citations() ever derive a scan pattern from it."""
        schema, findings = load_schema(json.dumps(
            {"keys": {"id": {"pattern": r"^src-\d{4}-\d{2}-\d{2}-\d{3}\$"}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])

    def test_uncompilable_derived_scan_pattern_fails_closed_not_crashes(self):
        """check_card_citations() must not let re.compile() raise uncaught
        for whatever the derived scan pattern turns out to be -- it fails
        closed with a single CARD_SCHEMA finding and skips the scan,
        rather than crashing the whole lint CLI with a traceback."""
        with patch("lint.card_id_scan_pattern", return_value="[unclosed"):
            findings = check_card_citations(good_files(), SCHEMA)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].code, "CARD_SCHEMA")

    def test_anchor_only_id_pattern_is_rejected_before_scanning(self):
        """An id.pattern of '^$' is syntactically valid regex -- it is not
        None, not a non-string, not empty -- but its body between the
        anchors is empty, so stripping them (card_id_scan_pattern) would
        yield the empty string, which matches every position in every
        string. load_schema()'s anchor contract rejects it with a
        CARD_SCHEMA finding before check_card_citations() ever sees it."""
        schema, findings = load_schema(json.dumps({"keys": {"id": {"pattern": "^$"}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])

    def test_flags_before_leading_anchor_no_longer_silently_defeats_the_scan(self):
        """Regression guard for the reported defect: an id.pattern such as
        '(?i)^src-...$' places an inline flag group before the literal
        '^'. The pre-fix card_id_scan_pattern() only stripped a leading '^'
        when it was the pattern's literal FIRST character, so the embedded
        '^' survived into the derived scan pattern -- and without
        re.MULTILINE, '^' only matches true position 0 of the searched
        text, so a real, mid-file citation was never found: the cited card
        was misreported UNFILED and no CITE finding was ever raised either.
        load_schema() now rejects the pattern outright (CARD_SCHEMA
        finding) instead of silently mis-scanning, and check_card_citations
        falls back to DEFAULT_CARD_ID_PATTERN, which finds the citation."""
        files = good_files()
        files[SCHEMA_PATH] = json.dumps(
            {"keys": {"id": {"pattern": r"(?i)^src-\d{4}-\d{2}-\d{2}-\d{3}$"}}})
        findings = run(files, [])
        codes = [f.code for f in findings]
        self.assertIn("CARD_SCHEMA", codes)
        self.assertNotIn("UNFILED", codes)
        self.assertNotIn("CITE", codes)

    def test_scoped_inline_flag_inside_anchors_scans_case_insensitively(self):
        """The contract's own fix hint for a case-insensitive id family --
        write the flag inside the anchors, e.g. ^(?i:src-...)$ -- must
        actually work end to end: load_schema() accepts it, and the
        derived scan pattern finds an upper-case citation of an upper-case
        card id."""
        schema, findings = load_schema(json.dumps(
            {"keys": {"id": {
                "pattern": r"^(?i:src-\d{4}-\d{2}-\d{2}-\d{3})$"}}}))
        self.assertEqual(findings, [])
        files = {
            "wiki/notes.md": "---\ntitle: Notes\ntopics: [x]\n---\n"
                             "As discussed in SRC-2024-01-15-001, "
                             "the model shipped.\n",
            "sources/cards/SRC-2024-01-15-001.md": "---\nid: SRC-2024-01-15-001\n---\n",
        }
        self.assertEqual(check_card_citations(files, schema), [])


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

    def test_non_string_pattern_on_any_key_fails_closed_run_never_crashes(self):
        """End-to-end proof that load_schema() closes the crash class at
        the root for every key, not only 'id': a schema whose 'date' rule
        declares a non-string 'pattern' value previously loaded with zero
        findings, then crashed run()'s own check_cards()/check_card() with
        an unhandled TypeError the moment a real card with a 'date' field
        was checked. Now the whole orchestrator fails closed with a
        CARD_SCHEMA finding instead."""
        files = good_files()
        files[SCHEMA_PATH] = json.dumps({"keys": {"date": {"pattern": None}}})
        findings = run(files, [])
        self.assertIn("CARD_SCHEMA", [f.code for f in findings])


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


class RulesFilesGeneralization(unittest.TestCase):
    """RULES_FILES generalizes lint.py's single-hardcoded-filename
    "this is rules, not content" exclusion (previously != "AGENTS.md" only)
    into a small named set, {"AGENTS.md", "recipes.md", "CLAUDE.md"}, so
    the upcoming sources/cards/recipes.md split (T10) and the tracked
    CLAUDE.md files (A7) are never wrongly checked as cards/wiki pages."""

    RECIPES_PROSE = (
        "# Recipe: how to file a card\n\n"
        "This file holds prose instructions for authoring cards, not a "
        "card itself. It has no frontmatter block at all, and if it were "
        "ever routed into check_card() it would also declare a key, "
        "'source_author', that no card-schema.json in this suite's "
        "fixtures ever declares.\n"
    )

    CLAUDE_MD_CONTENT = "@AGENTS.md\n"

    def test_recipes_md_produces_zero_card_findings(self):
        files = good_files()
        files["sources/cards/recipes.md"] = self.RECIPES_PROSE
        findings = check_cards(files)
        self.assertEqual([f for f in findings if f.path == "sources/cards/recipes.md"], [])
        self.assertEqual([f.code for f in findings
                          if f.code in ("CARD_FM", "CARD_KEY", "CARD_VALUE", "CARD_REF")
                          and f.path == "sources/cards/recipes.md"], [])

    def test_recipes_md_link_from_cards_agents_resolves(self):
        files = good_files()
        files["sources/cards/recipes.md"] = self.RECIPES_PROSE
        files["sources/cards/AGENTS.md"] = (
            "# Rules\nSee [recipes](./recipes.md) for card-writing guidance.\n")
        findings = check_broken_links(files)
        self.assertEqual([f for f in findings if f.code == "LINK"], [])

    def test_recipes_md_absent_produces_no_error(self):
        files = good_files()
        self.assertNotIn("sources/cards/recipes.md", files)
        findings = run(files, [])
        self.assertEqual(findings, [])

    def test_claude_md_paths_produce_zero_wiki_page_and_card_findings(self):
        files = good_files()
        files["wiki/CLAUDE.md"] = self.CLAUDE_MD_CONTENT
        files["sources/cards/CLAUDE.md"] = self.CLAUDE_MD_CONTENT
        findings = run(files, [])
        offending = [f for f in findings
                     if f.path in ("wiki/CLAUDE.md", "sources/cards/CLAUDE.md")
                     and f.code in ("FM", "INDEX", "ORPHAN", "CARD_FM")]
        self.assertEqual(offending, [])

    def test_rules_files_single_declaration(self):
        """RULES_FILES is declared exactly once, in card_frontmatter_lint.py
        (lint.py already imports from that module, so the reverse import is
        impossible); lint.py imports it rather than keeping a second copy,
        so the wiki-wide lint and the standalone card-lint CLI can never
        drift apart on which filenames hold rules, not content."""
        self.assertIs(lint.RULES_FILES, card_frontmatter_lint.RULES_FILES)
        self.assertEqual(lint.RULES_FILES, {"AGENTS.md", "recipes.md", "CLAUDE.md"})


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


class LinksInsideCode(unittest.TestCase):
    """Amendment A10: extract_links() (shared by check_broken_links,
    check_orphans and check_index_sync) must ignore a markdown link that
    sits inside a fenced code block or an inline code span -- it is a
    documentation example, not a real link."""

    def test_link_inside_fenced_block_is_not_a_link(self):
        files = {
            "wiki/page.md": (
                "# Page\n"
                "```python\n"
                "See [ghost](./ghost.md) for context.\n"
                "```\n"
            ),
        }
        self.assertEqual(check_broken_links(files), [])

    def test_link_inside_inline_code_is_not_a_link(self):
        files = {
            "wiki/page.md": "Note: `[ghost](./ghost.md)` is just an example.\n",
        }
        self.assertEqual(check_broken_links(files), [])

    def test_link_outside_code_is_still_checked(self):
        """Regression guard: a REAL link and a neighbouring inline code span
        on the SAME line must not let stripping the code span swallow the
        real link too."""
        files = {
            "wiki/page.md": "See [ghost](./ghost.md) and also `inline code` here.\n",
        }
        findings = check_broken_links(files)
        self.assertEqual([f.code for f in findings], ["LINK"])
        self.assertIn("./ghost.md", findings[0].message)

    def test_multiline_inline_code_span_is_not_a_link(self):
        """CommonMark allows an inline code span's opening and closing
        backtick run to sit on DIFFERENT lines (a line ending inside the
        span becomes a space, it does not close the span). A regex applied
        independently per line would leave the link inside this still-open
        span unstripped -- reproduce that exact false positive."""
        files = {
            "wiki/page.md": (
                "# Page\n"
                "Run `python script.py\n"
                "See [ghost](./ghost.md) for context` to enable logging.\n"
            ),
        }
        self.assertEqual(check_broken_links(files), [])

    def test_stray_backtick_does_not_swallow_a_later_paragraphs_link(self):
        """A single unmatched backtick in one paragraph must not pair with
        an unrelated backtick run in a LATER paragraph and blank everything
        (including a real broken link) in between -- inline code spans do
        not cross a blank-line paragraph boundary."""
        files = {
            "wiki/page.md": (
                "# Page\n"
                "This has a stray backtick ` in prose text like a typo.\n"
                "\n"
                "## Another section\n"
                "See [ghost](./ghost.md) for details.\n"
                "\n"
                "## Yet another\n"
                "code example uses a single backtick ` too.\n"
            ),
        }
        findings = check_broken_links(files)
        self.assertEqual([f.code for f in findings], ["LINK"])
        self.assertIn("./ghost.md", findings[0].message)

    def test_tilde_fence_and_longer_closing_fence(self):
        """A ~~~ fence is honoured exactly like a ``` fence, and a closing
        fence LONGER than the opening one still closes the block (per
        CommonMark, the closing fence need only be at least as long) -- the
        real link right after it proves scanning actually resumed rather
        than the whole rest of the file being silently swallowed."""
        files = {
            "wiki/page.md": (
                "~~~\n"
                "[ghost](./ghost.md)\n"
                "~~~~~\n"
                "[real-ghost](./real-ghost.md)\n"
            ),
        }
        findings = check_broken_links(files)
        self.assertEqual([f.code for f in findings], ["LINK"])
        self.assertIn("./real-ghost.md", findings[0].message)

    def test_orphans_and_index_ignore_links_in_code(self):
        # check_orphans: an inbound link that exists only inside a fenced
        # code block must not count -- the target page is still an orphan.
        files = good_files()
        files["wiki/lonely.md"] = (
            "---\ntitle: Lonely\ntopics: [misc]\n---\nNo real inbound link exists.\n")
        files["wiki/widget-assembly.md"] += "\n```\n[lonely](./lonely.md)\n```\n"
        orphan_findings = check_orphans(files)
        self.assertEqual([(f.severity, f.code, f.path) for f in orphan_findings],
                         [("WARN", "ORPHAN", "wiki/lonely.md")])

        # check_index_sync: an index.md entry that exists only inside a
        # fenced code block must not count as the page being listed.
        files2 = good_files()
        files2["wiki/real.md"] = "---\ntitle: Real\ntopics: [x]\n---\ncontent\n"
        files2["index.md"] += "\n```\n- [Real](./wiki/real.md)\n```\n"
        index_findings = check_index_sync(files2)
        self.assertEqual([(f.code, f.message) for f in index_findings],
                         [("INDEX", "wiki page not listed: wiki/real.md")])

    def test_rules_file_example_links_do_not_fail_a_fresh_scaffold(self):
        """The REAL templates/wiki.AGENTS.md and the REAL, rendered
        templates/AGENTS.root.md.tmpl both carry documentation-example links
        inside code (A10's whole motivation). A freshly scaffolded wiki --
        these two files, the seeded index.md header, and an empty manifest,
        nothing else -- must lint with zero LINK findings even though none
        of the example targets (./wiki/widget-assembly.md,
        ../sources/cards/src-2024-01-15-001.md, ./quality-checks.md) exist
        anywhere in the tree."""
        variables = {
            "wiki_title": "Sample Wiki",
            "org_name": "Sample Org",
            "content_language": "English",
            "repo_name": "sample-wiki",
        }
        rendered_root_agents = Template(
            (TEMPLATE_ROOT / "AGENTS.root.md.tmpl").read_text(encoding="utf-8")
        ).substitute(variables)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree = {
                "AGENTS.md": rendered_root_agents,
                "wiki/AGENTS.md": (TEMPLATE_ROOT / "wiki.AGENTS.md").read_text(encoding="utf-8"),
                "sources/AGENTS.md": "# Rules for sources/\n",
                "sources/cards/AGENTS.md": "# Rules for sources/cards/\n",
                "sources/cards/card-schema.json": FIXTURE_SCHEMA,
                "VISION.md": "# Deferred work\n",
                "index.md": (TEMPLATE_ROOT / "index.md.header.tmpl").read_text(encoding="utf-8"),
            }
            for rel, text in tree.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            write_manifest(root / MANIFEST_FILENAME, compute_manifest(
                {}, {}, "git@example.com:hieplam/wiki-harness.git",
                harness_version="1.0.0", source_ref="v1.0.0",
                source_commit="0" * 40, initialised_at="2026-08-26"))

            lint_py = Path(__file__).resolve().parent.parent / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertEqual(result.stderr, "", result.stderr)
            self.assertNotRegex(result.stdout, r"(?m)^(ERROR|WARN) LINK ")


if __name__ == "__main__":
    unittest.main()
