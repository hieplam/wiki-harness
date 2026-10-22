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


if __name__ == "__main__":
    unittest.main()
