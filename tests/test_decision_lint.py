from __future__ import annotations

import sys
import unittest
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import lint
from card_frontmatter_lint import Finding, parse_frontmatter
from decision_lint import check_decisions

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"

SECTIONS = ("## Context\nWhy.\n\n## Decision\nWhat.\n\n"
            "## Rejected options\nNone considered.\n\n## Consequences\nThen.\n")


def page(body=SECTIONS, **meta):
    """A wiki page: title and topics, then `meta` as frontmatter lines in
    the order given, then `body`."""
    lines = ["---", "title: A page", "topics: [widgets]"]
    lines += [f"{key}: {value}" for key, value in meta.items()]
    return "\n".join(lines + ["---"]) + "\n" + body


def decision(body=SECTIONS, **meta):
    return page(body, kind="decision", **meta)


def wiki(pages, index=None):
    """`pages` maps a page name to its text. Unless `index` is given, adds
    an index.md that lists every page under a topic and every decision page
    under `## Decisions` with its status -- so the index checks stay quiet
    in tests that are about something else."""
    files = {f"wiki/{name}.md": text for name, text in pages.items()}
    if index is None:
        topic, decisions = [], []
        for name, text in sorted(pages.items()):
            topic.append(f"- [{name}](./wiki/{name}.md) — a page")
            meta, _ = parse_frontmatter(text)
            kind = (meta or {}).get("kind", "")
            kinds = kind if isinstance(kind, list) else [kind]
            if any(k.casefold() == "decision" for k in kinds):
                status = meta.get("status") or "no status"
                decisions.append(f"- [{name}](./wiki/{name}.md) — {status}")
        index = ("# Index\n\n## widgets\n\n" + "\n".join(topic) + "\n\n"
                 "## Decisions\n\n" + "\n".join(decisions) + "\n")
    files["index.md"] = index
    return files


def run(files):
    return sorted(check_decisions(files, lint._wiki_pages(files),
                                  lint._strip_code, lint.extract_links))


def err(name, message):
    path = name if name == "index.md" else f"wiki/{name}.md"
    return Finding("ERROR", "DECISION", path, message)


class OptIn(unittest.TestCase):
    def test_no_decision_pages_no_findings(self):
        files, _ = lint.scan(FIXTURE)
        self.assertEqual(run(files), [])

    def test_other_kind_and_lookalike_keys_ignored(self):
        files = wiki({
            "runbook": page(kind="runbook", status="draft", supersedes="x"),
            "plain": page(status="draft", superseded_by="[y]"),
        })
        self.assertEqual(run(files), [])

    def test_kind_is_case_insensitive(self):
        files = wiki({"d": page(kind="Decision")})
        self.assertEqual(run(files), [err("d", "missing required field 'status'")])

    def test_kind_list_opts_in(self):
        files = wiki({"d": page(kind="[decision, note]")})
        self.assertEqual(run(files), [err("d", "missing required field 'status'")])


class StatusAndDate(unittest.TestCase):
    def test_missing_status(self):
        self.assertEqual(run(wiki({"d": decision()})),
                         [err("d", "missing required field 'status'")])

    def test_empty_status(self):
        self.assertEqual(run(wiki({"d": decision(status="")})),
                         [err("d", "missing required field 'status'")])

    def test_status_outside_the_set(self):
        self.assertEqual(
            run(wiki({"d": decision(status="Decided")})),
            [err("d", "status 'Decided' is not one of: proposed, decided, superseded")])

    def test_every_status_in_the_set_passes(self):
        for status in ("proposed", "decided"):
            with self.subTest(status=status):
                self.assertEqual(run(wiki({"d": decision(status=status)})), [])

    def test_decided_is_optional(self):
        self.assertEqual(run(wiki({"d": decision(status="decided")})), [])

    def test_decided_date_passes(self):
        files = wiki({"d": decision(status="decided", decided="2024-03-01")})
        self.assertEqual(run(files), [])

    def test_decided_not_a_date(self):
        files = wiki({"d": decision(status="decided", decided="01-03-2024")})
        self.assertEqual(run(files),
                         [err("d", "decided '01-03-2024' is not a YYYY-MM-DD date")])


class Sections(unittest.TestCase):
    def test_missing_sections_one_finding_each(self):
        files = wiki({"d": decision("## Context\nWhy.\n", status="decided")})
        self.assertEqual(run(files), [
            err("d", "missing required section '## Consequences'"),
            err("d", "missing required section '## Decision'"),
            err("d", "missing required section '## Rejected options'"),
        ])

    def test_heading_spelling_variants_match(self):
        body = ("## context\n\n##  Rejected Options  \n\n## Decision ##\n\n"
                "## CONSEQUENCES\n")
        self.assertEqual(run(wiki({"d": decision(body, status="decided")})), [])

    def test_extra_sections_are_allowed(self):
        body = SECTIONS + "\n## Timeline\nThen.\n\n## Open questions\nNone.\n"
        self.assertEqual(run(wiki({"d": decision(body, status="decided")})), [])

    def test_level_three_and_plural_headings_do_not_count(self):
        body = ("### Context\n\n## Decisions\n\n## Rejected options\n\n"
                "## Consequences\n")
        self.assertEqual(run(wiki({"d": decision(body, status="decided")})), [
            err("d", "missing required section '## Context'"),
            err("d", "missing required section '## Decision'"),
        ])

    def test_heading_inside_a_fence_does_not_count(self):
        body = ("```markdown\n## Context\n```\n\n## Decision\n\n"
                "## Rejected options\n\n## Consequences\n")
        self.assertEqual(run(wiki({"d": decision(body, status="decided")})),
                         [err("d", "missing required section '## Context'")])

    def test_crlf_page(self):
        text = decision(status="decided").replace("\n", "\r\n")
        self.assertEqual(run(wiki({"d": text})), [])


class LinkValues(unittest.TestCase):
    """A `proposed` page's `supersedes` is an intent: only its shape and
    its target are checked, so these fixtures use one and leave the old
    page `decided`."""

    def test_page_name_shapes_that_pass(self):
        for value in ("old", "[old]", "[old, other]", "[old, old]"):
            with self.subTest(value=value):
                files = wiki({
                    "new": decision(status="proposed", supersedes=value),
                    "old": decision(status="decided"),
                    "other": decision(status="decided"),
                })
                self.assertEqual(run(files), [])

    def test_page_name_shapes_that_are_refused(self):
        for value in ("old.md", "./old.md", "wiki/old.md", "../wiki/old.md"):
            with self.subTest(value=value):
                files = wiki({
                    "new": decision(status="proposed", supersedes=value),
                    "old": decision(status="decided"),
                })
                self.assertEqual(run(files), [err(
                    "new", f"supersedes value '{value}' is not a page name; "
                           "write 'old'")])

    def test_superseded_by_shape_is_refused_with_its_own_key_name(self):
        files = wiki({
            "old": decision(status="superseded", superseded_by="./new.md"),
            "new": decision(status="proposed"),
        })
        self.assertEqual(run(files), [err(
            "old", "superseded_by value './new.md' is not a page name; write 'new'")])

    def test_empty_supersedes_replaces_nothing(self):
        for value in ("", "[]"):
            with self.subTest(value=repr(value)):
                files = wiki({"d": decision(status="decided", supersedes=value)})
                self.assertEqual(run(files), [])

    def test_supersedes_a_missing_page(self):
        files = wiki({"new": decision(status="proposed", supersedes="ghost")})
        self.assertEqual(run(files), [err(
            "new", "supersedes names 'ghost', but wiki/ghost.md does not exist")])

    def test_supersedes_a_page_that_is_not_a_decision_page(self):
        files = wiki({"new": decision(status="proposed", supersedes="plain"),
                      "plain": page()})
        self.assertEqual(run(files), [err(
            "new", "supersedes names 'plain', but wiki/plain.md is not a decision page")])

    def test_superseded_by_a_missing_page(self):
        files = wiki({"old": decision(status="superseded", superseded_by="ghost")})
        self.assertEqual(run(files), [err(
            "old", "superseded_by names 'ghost', but wiki/ghost.md does not exist")])

    def test_superseded_by_a_page_that_is_not_a_decision_page(self):
        files = wiki({"old": decision(status="superseded", superseded_by="plain"),
                      "plain": page()})
        self.assertEqual(run(files), [err(
            "old", "superseded_by names 'plain', but wiki/plain.md is not a decision page")])


class Replacement(unittest.TestCase):
    """`new` replaces `old`. Each test asserts the complete finding list,
    so a second finding for the same mistake fails it."""

    def test_consistent_pair_no_findings(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "old": decision(status="superseded", superseded_by="new"),
        })
        self.assertEqual(run(files), [])

    def test_superseded_page_still_counts_as_a_replacement(self):
        files = wiki({
            "newest": decision(status="decided", supersedes="mid"),
            "mid": decision(status="superseded", superseded_by="newest",
                            supersedes="old"),
            "old": decision(status="superseded", superseded_by="mid"),
        })
        self.assertEqual(run(files), [])

    def test_r1_superseded_without_superseded_by(self):
        files = wiki({"old": decision(status="superseded")})
        self.assertEqual(run(files), [err(
            "old", "status is 'superseded', but superseded_by is missing")])

    def test_r1_alone_when_a_replacement_exists(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "old": decision(status="superseded"),
        })
        self.assertEqual(run(files), [err(
            "old", "status is 'superseded', but superseded_by is missing")])

    def test_r2_superseded_by_on_a_decided_page(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "old": decision(status="decided", superseded_by="new"),
        })
        self.assertEqual(run(files), [err(
            "old", "superseded_by is set, but status is 'decided', not 'superseded'")])

    def test_r3_superseded_by_a_proposal(self):
        files = wiki({
            "new": decision(status="proposed", supersedes="old"),
            "old": decision(status="superseded", superseded_by="new"),
        })
        self.assertEqual(run(files), [err(
            "old", "superseded_by names 'new', but wiki/new.md is still 'proposed'")])

    def test_p1_replaced_page_not_marked(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "old": decision(status="decided"),
        })
        self.assertEqual(run(files), [err(
            "old", "wiki/new.md supersedes this page, but status is 'decided' "
                   "and superseded_by is missing")])

    def test_p2_superseded_by_does_not_name_a_replacement(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "other": decision(status="decided", supersedes="old"),
            "old": decision(status="superseded", superseded_by="other"),
        })
        self.assertEqual(run(files), [err(
            "old", "wiki/new.md supersedes this page, but superseded_by "
                   "does not name 'new'")])

    def test_p3_named_replacement_does_not_name_back(self):
        files = wiki({
            "new": decision(status="decided"),
            "old": decision(status="superseded", superseded_by="new"),
        })
        self.assertEqual(run(files), [err(
            "new", "wiki/old.md is superseded_by 'new', but supersedes here "
                   "does not name 'old'")])

    def test_wrong_name_reported_on_both_pages(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "other": decision(status="decided"),
            "old": decision(status="superseded", superseded_by="other"),
        })
        self.assertEqual(run(files), sorted([
            err("old", "wiki/new.md supersedes this page, but superseded_by "
                       "does not name 'new'"),
            err("other", "wiki/old.md is superseded_by 'other', but supersedes "
                         "here does not name 'old'"),
        ]))

    def test_proposed_supersedes_leaves_old_page_untouched(self):
        files = wiki({
            "new": decision(status="proposed", supersedes="old"),
            "old": decision(status="decided"),
        })
        self.assertEqual(run(files), [])

    def test_invalid_status_gives_only_its_status_finding(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "old": decision(status="done"),
        })
        self.assertEqual(run(files), [err(
            "old", "status 'done' is not one of: proposed, decided, superseded")])

    def test_refused_value_takes_no_part(self):
        files = wiki({
            "new": decision(status="decided", supersedes="old"),
            "old": decision(status="superseded", superseded_by="./new.md"),
        })
        self.assertEqual(run(files), [err(
            "old", "superseded_by value './new.md' is not a page name; write 'new'")])

    def test_duplicate_values_give_one_finding(self):
        files = wiki({
            "new": decision(status="decided", supersedes="[old, old]"),
            "old": decision(status="decided"),
        })
        self.assertEqual(run(files), [err(
            "old", "wiki/new.md supersedes this page, but status is 'decided' "
                   "and superseded_by is missing")])

    def test_c1_two_page_loop(self):
        files = wiki({
            "a": decision(status="superseded", superseded_by="b", supersedes="b"),
            "b": decision(status="superseded", superseded_by="a", supersedes="a"),
        })
        self.assertEqual(run(files), [
            err("a", "supersedes chain loops back to this page: a -> b -> a"),
            err("b", "supersedes chain loops back to this page: b -> a -> b"),
        ])

    def test_c1_self_loop(self):
        files = wiki({"a": decision(status="superseded", superseded_by="a",
                                    supersedes="a")})
        self.assertEqual(run(files), [err(
            "a", "supersedes chain loops back to this page: a -> a")])


def index(*decision_lines, extra=""):
    return ("# Index\n\n## widgets\n\n- [d](./wiki/d.md) — a page\n\n"
            "## Decisions\n\n" + "\n".join(decision_lines) + "\n" + extra)


class IndexSection(unittest.TestCase):
    def test_no_decision_pages_no_section_needed(self):
        files = wiki({"plain": page()}, index="# Index\n\n- [p](./wiki/plain.md)\n")
        self.assertEqual(run(files), [])

    def test_missing_section(self):
        files = wiki({"d": decision(status="decided")},
                     index="# Index\n\n## widgets\n\n- [d](./wiki/d.md) — decided\n")
        self.assertEqual(run(files), [err(
            "index.md", "no '## Decisions' section, but decision pages exist")])

    def test_page_not_listed(self):
        files = wiki({"d": decision(status="decided"), "e": decision(status="decided")},
                     index=index("- [d](./wiki/d.md) — decided"))
        self.assertEqual(run(files), [err(
            "index.md", "decision page not listed under '## Decisions': wiki/e.md")])

    def test_line_without_the_status(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("- [d](./wiki/d.md) — batch size and why"))
        self.assertEqual(run(files), [err(
            "index.md", "'## Decisions' lists wiki/d.md without its status 'decided'")])

    def test_entry_that_is_not_a_decision_page(self):
        files = wiki({"d": decision(status="decided"), "plain": page()},
                     index=index("- [d](./wiki/d.md) — decided",
                                 "- [p](./wiki/plain.md) — decided"))
        self.assertEqual(run(files), [err(
            "index.md", "'## Decisions' lists wiki/plain.md, which is not a decision page")])

    def test_entry_for_a_missing_page_is_left_to_index_check(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("- [d](./wiki/d.md) — decided",
                                 "- [g](./wiki/ghost.md) — decided"))
        self.assertEqual(run(files), [])

    def test_status_word_is_case_insensitive(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("- [d](./wiki/d.md) — Decided 2024-03-01"))
        self.assertEqual(run(files), [])

    def test_status_in_code_span_counts(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("- [d](./wiki/d.md) — `decided`"))
        self.assertEqual(run(files), [])

    def test_status_inside_link_text_does_not_count(self):
        files = wiki({"d": decision(status="proposed")},
                     index=index("- [What we proposed](./wiki/d.md) — soon"))
        self.assertEqual(run(files), [err(
            "index.md", "'## Decisions' lists wiki/d.md without its status 'proposed'")])

    def test_status_inside_link_target_does_not_count(self):
        files = wiki({"decided-widgets": decision(status="decided")},
                     index=index("- [Widgets](./wiki/decided-widgets.md) — size"))
        self.assertEqual(run(files), [err(
            "index.md", "'## Decisions' lists wiki/decided-widgets.md without "
                        "its status 'decided'")])

    def test_second_link_on_a_line_is_a_reference(self):
        pages = {"new": decision(status="decided", supersedes="old"),
                 "old": decision(status="superseded", superseded_by="new")}
        line = "- [old](./wiki/old.md) — superseded by [new](./wiki/new.md)"
        self.assertEqual(run(wiki(pages, index=index(line))), [err(
            "index.md", "decision page not listed under '## Decisions': wiki/new.md")])
        both = index(line, "- [new](./wiki/new.md) — decided")
        self.assertEqual(run(wiki(pages, index=both)), [])

    def test_section_ends_at_the_next_level_two_heading(self):
        files = wiki({"d": decision(status="decided")},
                     index=index(extra="\n## later\n\n- [d](./wiki/d.md) — decided\n"))
        self.assertEqual(run(files), [err(
            "index.md", "decision page not listed under '## Decisions': wiki/d.md")])

    def test_entry_inside_a_fence_does_not_count(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("```", "- [d](./wiki/d.md) — decided", "```"))
        self.assertEqual(run(files), [err(
            "index.md", "decision page not listed under '## Decisions': wiki/d.md")])

    def test_heading_case_and_closing_hashes(self):
        text = "# Index\n\n## decisions ##\n\n- [d](./wiki/d.md) — decided\n"
        self.assertEqual(run(wiki({"d": decision(status="decided")}, index=text)), [])

    def test_two_decisions_sections_are_one_list(self):
        text = ("# Index\n\n## Decisions\n\n- [d](./wiki/d.md) — decided\n\n"
                "## widgets\n\n## Decisions\n\n- [e](./wiki/e.md) — proposed\n")
        files = wiki({"d": decision(status="decided"), "e": decision(status="proposed")},
                     index=text)
        self.assertEqual(run(files), [])

    def test_indented_list_line(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("  - [d](./wiki/d.md) — decided"))
        self.assertEqual(run(files), [])

    def test_crlf_index(self):
        text = index("- [d](./wiki/d.md) — decided").replace("\n", "\r\n")
        self.assertEqual(run(wiki({"d": decision(status="decided")}, index=text)), [])

    def test_invalid_status_skips_the_status_word_check(self):
        files = wiki({"d": decision(status="done")},
                     index=index("- [d](./wiki/d.md) — finished"))
        self.assertEqual(run(files), [err(
            "d", "status 'done' is not one of: proposed, decided, superseded")])

    def _replaced_pair(self):
        return {"new": decision(status="decided", supersedes="old"),
                "old": decision(status="superseded", superseded_by="new")}

    def test_wrapped_item_line_is_a_continuation(self):
        text = index("- [old](./wiki/old.md) — superseded by",
                     "  [new](./wiki/new.md)",
                     "- [new](./wiki/new.md) — decided")
        self.assertEqual(run(wiki(self._replaced_pair(), index=text)), [])

    def test_status_word_on_a_wrapped_line_counts(self):
        text = index("- [old](./wiki/old.md) — replaced by [new](./wiki/new.md),",
                     "  superseded on 2024-03-01",
                     "- [new](./wiki/new.md) — decided")
        self.assertEqual(run(wiki(self._replaced_pair(), index=text)), [])

    def test_nested_item_is_a_continuation(self):
        text = index("- [new](./wiki/new.md) — decided",
                     "  - replaces [old](./wiki/old.md)",
                     "- [old](./wiki/old.md) — superseded")
        self.assertEqual(run(wiki(self._replaced_pair(), index=text)), [])

    def test_prose_line_is_not_an_entry(self):
        files = wiki({"d": decision(status="decided"), "plain": page()},
                     index=index("Read [how to write one](./wiki/plain.md) first.",
                                 "",
                                 "- [d](./wiki/d.md) — decided"))
        self.assertEqual(run(files), [])

    def test_numbered_item_is_an_entry(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("1. [d](./wiki/d.md) — decided"))
        self.assertEqual(run(files), [])

    def test_unindented_prose_after_a_blank_line_ends_the_item(self):
        files = wiki({"d": decision(status="decided")},
                     index=index("- [d](./wiki/d.md) — soon", "",
                                 "The word decided here is prose."))
        self.assertEqual(run(files), [err(
            "index.md", "'## Decisions' lists wiki/d.md without its status 'decided'")])

    def test_crlf_page_heading_inside_a_fence_does_not_count(self):
        body = ("```markdown\n## Context\n```\n\n## Decision\n\n"
                "## Rejected options\n\n## Consequences\n")
        text = decision(body, status="decided").replace("\n", "\r\n")
        self.assertEqual(run(wiki({"d": text})),
                         [err("d", "missing required section '## Context'")])

    def test_crlf_index_entry_inside_a_fence_does_not_count(self):
        text = index("```", "- [d](./wiki/d.md) — decided", "```").replace("\n", "\r\n")
        self.assertEqual(run(wiki({"d": decision(status="decided")}, index=text)), [err(
            "index.md", "decision page not listed under '## Decisions': wiki/d.md")])

    def test_missing_index_is_left_to_index_check(self):
        files = {"wiki/d.md": decision(status="decided")}
        self.assertEqual(run(files), [])


if __name__ == "__main__":
    unittest.main()
