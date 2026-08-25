from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from card_frontmatter_lint import (DEFAULT_CARD_ID_PATTERN, SCHEMA_PATH,
                                   card_id_pattern_from_schema,
                                   card_id_scan_pattern, load_schema)

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"
FIXTURE_SCHEMA = (FIXTURE / SCHEMA_PATH).read_text(encoding="utf-8")


class CardIdScanPattern(unittest.TestCase):
    """card_id_scan_pattern() is a pure string transform, not a second
    declaration of card-id shape: it derives lint.py's unanchored
    citation-scan regex from card-schema.json's own anchored, whole-value
    id.pattern by stripping exactly one leading '^' and trailing '$'."""

    def test_card_id_scan_pattern_strips_anchors(self):
        self.assertEqual(
            card_id_scan_pattern(r"^src-\d{4}-\d{2}-\d{2}-\d{3}$"),
            r"src-\d{4}-\d{2}-\d{2}-\d{3}")

    def test_no_anchors_present_returns_pattern_unchanged(self):
        """'if present' -- an already-unanchored pattern passes through as-is."""
        self.assertEqual(card_id_scan_pattern(r"src-\d{4}-\d{2}-\d{2}-\d{3}"),
                         r"src-\d{4}-\d{2}-\d{2}-\d{3}")

    def test_escaped_trailing_dollar_is_not_stripped(self):
        """An escaped literal '\\$' at the end of the pattern (an odd
        number of immediately preceding backslashes) is not the regex
        end-anchor and must be left untouched, not stripped as if it were
        the anchor '$' -- stripping it would dangle an unescaped backslash
        and crash re.compile() downstream."""
        self.assertEqual(
            card_id_scan_pattern(r"^src-\d{4}-\d{2}-\d{2}-\d{3}\$"),
            r"src-\d{4}-\d{2}-\d{2}-\d{3}\$")

    def test_even_backslashes_before_dollar_is_still_a_genuine_anchor(self):
        """An even number of trailing backslashes means the last one is
        itself an escaped literal backslash, so the following '$' is the
        genuine end-anchor and must still be stripped."""
        self.assertEqual(card_id_scan_pattern(r"^abc\\$"), r"abc\\")


class CardIdPatternFromSchema(unittest.TestCase):
    """card_id_pattern_from_schema() must fall back to
    DEFAULT_CARD_ID_PATTERN not only when the schema is None or omits
    id.pattern, but whenever load_schema() accepts id.pattern as valid JSON
    yet it is not a usable regex string -- load_schema() only validates rule
    *names* (that 'pattern' is a known rule key), never rule *value types*,
    so a schema it reports zero findings for can still declare id.pattern as
    null, a number, a list, or the empty string."""

    def test_null_pattern_falls_back_to_default(self):
        """load_schema() now rejects a null id.pattern at the root (see
        LoadSchema.test_null_pattern_value_is_an_error_for_any_key below),
        so this exercises card_id_pattern_from_schema()'s own defensive
        fallback directly, against a schema dict shaped this way by some
        other route -- the structural guard stays as defense in depth even
        though the normal load_schema() pipeline can no longer produce it."""
        self.assertEqual(card_id_pattern_from_schema({"id": {"pattern": None}}),
                         DEFAULT_CARD_ID_PATTERN)

    def test_number_pattern_falls_back_to_default(self):
        self.assertEqual(card_id_pattern_from_schema({"id": {"pattern": 42}}),
                         DEFAULT_CARD_ID_PATTERN)

    def test_list_pattern_falls_back_to_default(self):
        self.assertEqual(card_id_pattern_from_schema({"id": {"pattern": ["a", "b"]}}),
                         DEFAULT_CARD_ID_PATTERN)

    def test_empty_string_pattern_falls_back_to_default(self):
        """An empty string is rejected by load_schema() too (see
        LoadSchema.test_empty_string_pattern_value_is_an_error below); this
        exercises card_id_pattern_from_schema()'s own defensive fallback
        directly. As a regex it matches every position in every string --
        left unguarded it would silently defeat both call sites' validation
        rather than reject or scan for anything real."""
        self.assertEqual(card_id_pattern_from_schema({"id": {"pattern": ""}}),
                         DEFAULT_CARD_ID_PATTERN)

    def test_syntactically_invalid_regex_pattern_is_rejected_by_load_schema(self):
        """load_schema() itself now validates that every 'pattern' rule
        value is a syntactically valid regex (see LoadSchema.
        test_invalid_regex_pattern_value_is_an_error below), so a non-empty
        string that is not valid regex (e.g. an unclosed character class)
        never reaches card_id_pattern_from_schema() as part of a
        'successfully loaded' schema -- it fails closed at load_schema()
        itself, and card_id_pattern_from_schema() falls back to
        DEFAULT_CARD_ID_PATTERN exactly like the schema=None case."""
        schema, findings = load_schema(
            json.dumps({"keys": {"id": {"pattern": "^src-["}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])
        self.assertEqual(card_id_pattern_from_schema(schema), DEFAULT_CARD_ID_PATTERN)

    def test_anchor_only_pattern_falls_back_to_default(self):
        """card_id_scan_pattern() strips exactly one leading '^' and
        trailing '$'. A schema id.pattern of '^$' (or degenerating to only
        '^' or only '$') is a syntactically valid regex -- it passes every
        other guard here -- but its derived scan pattern is the empty
        string, which matches every position in every string. Left
        unguarded, check_card_citations() would report every wiki page as
        citing an unknown card and every card as UNFILED: a permanent,
        unfixable false-positive caused by the pattern derivation itself,
        not by the wiki content. It must fall back to
        DEFAULT_CARD_ID_PATTERN instead."""
        for degenerate in ("^$", "^", "$"):
            with self.subTest(pattern=degenerate):
                schema, findings = load_schema(
                    json.dumps({"keys": {"id": {"pattern": degenerate}}}))
                self.assertEqual(findings, [])
                self.assertEqual(card_id_pattern_from_schema(schema),
                                 DEFAULT_CARD_ID_PATTERN)


class LoadSchema(unittest.TestCase):
    """The schema file is the single source of truth, so a schema that cannot be
    trusted must block every card rather than wave them through."""

    def test_real_schema_loads(self):
        schema, findings = load_schema(FIXTURE_SCHEMA)
        self.assertEqual(findings, [])
        self.assertTrue(schema["id"]["required"])
        self.assertIn("session", schema["origin"]["enum"])

    def test_missing_file_is_an_error(self):
        schema, findings = load_schema(None)
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])

    def test_invalid_json_is_an_error(self):
        schema, findings = load_schema("{not json")
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])

    def test_empty_keys_is_an_error(self):
        schema, findings = load_schema('{"keys": {}}')
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])

    def test_unknown_rule_name_is_an_error(self):
        """'regex' instead of 'pattern' must not silently retire the date check."""
        schema, findings = load_schema(json.dumps({"keys": {"date": {"regex": "^x$"}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])
        self.assertIn("regex", findings[0].message)

    def test_invalid_regex_pattern_value_is_an_error(self):
        """A 'pattern' rule whose string value is not syntactically valid
        regex (e.g. an unclosed character class) must not be handed
        straight to re.match/re.compile downstream -- _check_value()'s
        per-card pattern check would otherwise crash with an unhandled
        re.error. load_schema() fails closed exactly like an unknown rule
        name: it never trusts a schema it cannot validate."""
        schema, findings = load_schema(
            json.dumps({"keys": {"id": {"pattern": "[unclosed"}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])
        self.assertIn("pattern", findings[0].message)

    def test_non_string_pattern_value_is_an_error_for_any_key_not_just_id(self):
        """load_schema() validates rule *names* everywhere already, but a
        'pattern' rule whose value is not a string at all (None, a number,
        a list, a bool) previously slipped through with zero findings for
        EVERY key, not only 'id' -- _check_value()'s generic per-card
        check (re.match(rules['pattern'], value)) would then raise an
        unhandled TypeError the moment any real card was checked against
        it. This must fail closed at load_schema() itself, exactly like an
        unknown rule name, regardless of which key declares the bad
        pattern."""
        for key, bad_pattern in (("date", None), ("id", 42),
                                 ("origin", ["a", "b"]), ("trust", True)):
            with self.subTest(key=key, pattern=bad_pattern):
                schema, findings = load_schema(
                    json.dumps({"keys": {key: {"pattern": bad_pattern}}}))
                self.assertIsNone(schema)
                self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])
                self.assertIn("pattern", findings[0].message)

    def test_empty_string_pattern_value_is_an_error(self):
        """An empty string is syntactically valid regex (re.compile('')
        does not raise) but matches every position in every string --
        previously accepted with zero findings, silently defeating
        whatever check declared it."""
        schema, findings = load_schema(json.dumps({"keys": {"id": {"pattern": ""}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])
        self.assertIn("pattern", findings[0].message)

    def test_non_string_pattern_crash_is_closed_before_check_card_ever_runs(self):
        """The end-to-end proof: before this fix, a card checked against a
        schema with a non-string 'pattern' value crashed with an unhandled
        TypeError inside _check_value()'s re.match(). Now load_schema()
        itself fails closed, so check_card() is never even reached with
        such a schema."""
        schema, findings = load_schema(json.dumps({"keys": {"id": {"pattern": None}}}))
        self.assertIsNone(schema)
        self.assertEqual([f.code for f in findings], ["CARD_SCHEMA"])


from card_frontmatter_lint import check_card

SCHEMA, _SCHEMA_ERRORS = load_schema(FIXTURE_SCHEMA)

PATH = "sources/cards/src-2024-01-15-001.md"
CARD = """---
id: src-2024-01-15-001
date: 2024-01-15
origin: session
trust: stated
topics: [widget-assembly]
---
## Claims
- a claim
"""

TREE = {
    "sources/cards/src-2024-01-15-001.md",
    "sources/cards/src-2024-01-15-002.md",
    "sources/raw/src-2024-01-15-001-artifact.html",
}


def exists(rel):
    return rel in TREE


def card(*, add="", replace=None):
    text = CARD
    if replace:
        text = text.replace(*replace)
    if add:
        text = text.replace("---\n## Claims", add + "---\n## Claims")
    return text


class CheckCard(unittest.TestCase):
    def codes(self, text, path=PATH):
        return [f.code for f in check_card(path, text, SCHEMA, exists)]

    def test_clean_card(self):
        self.assertEqual(check_card(PATH, CARD, SCHEMA, exists), [])

    def test_undeclared_key_is_blocked(self):
        findings = check_card(PATH, card(add="source_author: Michael\n"), SCHEMA, exists)
        self.assertEqual([f.code for f in findings], ["CARD_KEY"])

    def test_undeclared_key_message_names_the_key_and_the_way_out(self):
        """The message is the whole fix hint an agent gets, so it must name the
        offending key, where the rule lives, and both legal exits."""
        message = check_card(PATH, card(add="source_author: Michael\n"),
                             SCHEMA, exists)[0].message
        self.assertIn("source_author", message)
        self.assertIn(SCHEMA_PATH, message)
        self.assertIn("schema:", message)
        self.assertIn("trust", message)  # the declared-key list, so a typo is visible

    def test_typo_of_a_required_key_is_reported_twice(self):
        """'trsut' is both an undeclared key and a missing required one."""
        codes = self.codes(card(replace=("trust: stated", "trsut: stated")))
        self.assertEqual(codes, ["CARD_KEY", "CARD_KEY"])

    def test_missing_required_key(self):
        findings = check_card(PATH, card(replace=("trust: stated\n", "")),
                              SCHEMA, exists)
        self.assertEqual([f.code for f in findings], ["CARD_KEY"])
        self.assertIn("trust", findings[0].message)

    def test_empty_topics_list_counts_as_missing(self):
        self.assertEqual(self.codes(card(replace=("topics: [widget-assembly]", "topics: []"))),
                         ["CARD_KEY"])

    def test_bad_origin_enum(self):
        findings = check_card(PATH, card(replace=("origin: session", "origin: email")),
                              SCHEMA, exists)
        self.assertEqual([f.code for f in findings], ["CARD_VALUE"])
        self.assertIn("confluence", findings[0].message)  # lists the legal values

    def test_bad_date_pattern(self):
        self.assertEqual(self.codes(card(replace=("date: 2024-01-15", "date: 15/01/2024"))),
                         ["CARD_VALUE"])

    def test_scalar_where_a_list_is_required(self):
        self.assertEqual(self.codes(card(replace=("topics: [widget-assembly]", "topics: widget-assembly"))),
                         ["CARD_VALUE"])

    def test_id_must_match_the_filename(self):
        """src-2024-01-15-999 satisfies the pattern, so only the filename rule
        can catch it - which is the point of having both rules."""
        findings = check_card(PATH, card(replace=("id: src-2024-01-15-001",
                                                  "id: src-2024-01-15-999")),
                              SCHEMA, exists)
        self.assertEqual([f.code for f in findings], ["CARD_REF"])

    def test_id_that_is_not_a_card_id_at_all(self):
        self.assertEqual(self.codes(card(replace=("id: src-2024-01-15-001", "id: banana")),
                                    path="sources/cards/banana.md"),
                         ["CARD_VALUE"])

    def test_raw_pointer_must_exist(self):
        self.assertEqual(self.codes(card(add="raw: ../raw/missing.html\n")), ["CARD_REF"])

    def test_raw_pointer_that_exists_is_clean(self):
        self.assertEqual(
            self.codes(card(add="raw: ../raw/src-2024-01-15-001-artifact.html\n")), [])

    def test_parent_must_point_at_a_real_card(self):
        self.assertEqual(self.codes(card(add="parent: src-2024-01-15-404\n")), ["CARD_REF"])

    def test_parent_that_exists_is_clean(self):
        self.assertEqual(self.codes(card(add="parent: src-2024-01-15-002\n")), [])

    def test_provenance_keys_are_accepted(self):
        self.assertEqual(self.codes(card(add="source_id: 4960321655\n"
                                             "source_url: https://example.com/x\n"
                                             "source_version: 16\n"
                                             "source_space: ENG\n"
                                             "source_parent_id: 4952719362\n")), [])

    def test_missing_frontmatter(self):
        self.assertEqual(self.codes("## Claims\n- a claim\n"), ["CARD_FM"])


class Primitives(unittest.TestCase):
    def test_parse_frontmatter_reads_scalars_and_lists(self):
        from card_frontmatter_lint import parse_frontmatter
        meta, errors = parse_frontmatter(CARD)
        self.assertEqual(errors, [])
        self.assertEqual(meta["id"], "src-2024-01-15-001")
        self.assertEqual(meta["topics"], ["widget-assembly"])

    def test_resolve_walks_up(self):
        from card_frontmatter_lint import resolve
        self.assertEqual(resolve("sources/cards/a.md", "../raw/b.html"),
                         "sources/raw/b.html")


import subprocess


class Cli(unittest.TestCase):
    """The CLI is what a git hook or a future write-time hook will call, so its
    exit code carries the whole verdict."""

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "card_frontmatter_lint.py"), *args],
            capture_output=True, text=True)

    def test_fixture_cards_are_clean(self):
        """Pins the zero-migration claim: every card in the fixture wiki already
        obeys the schema, so closing the key set breaks nothing."""
        result = self.run_cli("--root", str(FIXTURE))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_named_card_is_clean(self):
        result = self.run_cli("--root", str(FIXTURE),
                              str(FIXTURE / "sources" / "cards" / "src-2024-01-15-001.md"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bad_card_exits_1_and_names_the_key(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources" / "cards").mkdir(parents=True)
            (root / SCHEMA_PATH).write_text(FIXTURE_SCHEMA, encoding="utf-8")
            card_path = root / "sources" / "cards" / "src-2024-01-15-001.md"
            card_path.write_text(CARD.replace("---\n## Claims",
                                              "source_author: Michael\n---\n## Claims"),
                                 encoding="utf-8")
            result = self.run_cli("--root", str(root), str(card_path))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("source_author", result.stdout)

    def test_root_relative_path_resolves_against_root_not_cwd(self):
        """AGENTS.md documents this exact invocation with a repo-root-relative
        path; it must not depend on which directory the caller happens to be
        standing in."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "card_frontmatter_lint.py"),
             "--root", str(FIXTURE), "sources/cards/src-2024-01-15-001.md"],
            capture_output=True, text=True, cwd=str(ROOT / "scripts"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_schema_blocks_everything(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources" / "cards").mkdir(parents=True)
            result = self.run_cli("--root", str(root))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("CARD_SCHEMA", result.stdout)

    def test_default_discovery_finds_cards_whose_id_does_not_start_with_src(self):
        """The CLI's default-discovery mode (no explicit file args) must
        find every card under sources/cards/, not only files matching the
        library's former 'src-*.md' naming convention -- once a wiki
        customizes card-schema.json's id.pattern away from that prefix, a
        real, invalid card sitting right there must still be caught, not
        silently skipped and reported clean."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources" / "cards").mkdir(parents=True)
            schema = {"keys": {
                "id": {"pattern": r"^ai-\d{4}-\d{2}-\d{2}-\d{3}$", "required": True},
                "title": {"required": True},
            }}
            (root / SCHEMA_PATH).write_text(json.dumps(schema), encoding="utf-8")
            (root / "sources" / "cards" / "ai-2024-01-15-001.md").write_text(
                "---\nid: ai-2024-01-15-001\n---\n", encoding="utf-8")
            result = self.run_cli("--root", str(root))
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("missing required field 'title'", result.stdout)


if __name__ == "__main__":
    unittest.main()
