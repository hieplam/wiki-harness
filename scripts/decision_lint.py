#!/usr/bin/env python3
"""Decision page lint: the checks for wiki pages that opt in with
`kind: decision` -- their status and date, their four required sections,
and the `supersedes` / `superseded_by` links between them.

A page without `kind: decision` is never judged here, whatever other keys
it carries: a wiki that uses `kind`, `status` or `supersedes` for its own
purpose keeps exactly the findings it had before this module existed.

lint.py's run() calls check_decisions() and hands it lint.py's own page
list, code stripper and link extractor. This module cannot import them,
because lint.py imports this module; receiving them also keeps one fence
parser in the harness instead of two.

Pure, every function: check_decisions(), decision_pages(), opts_in(),
link_values(), shown(), section_names(), page_findings(),
link_findings(). There are no impure edges.

Python 3 stdlib only.
"""
from __future__ import annotations

import re
from collections import namedtuple
from pathlib import PurePosixPath

from card_frontmatter_lint import Finding, parse_frontmatter

CODE = "DECISION"
DECISION_STATUSES = ("proposed", "decided", "superseded")
REQUIRED_SECTIONS = ("Context", "Decision", "Rejected options", "Consequences")
LINK_KEYS = ("supersedes", "superseded_by")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A level-2 ATX heading: exactly two '#', then its text, then optional
# closing '#'s. '### x' is level 3 and does not match.
H2_RE = re.compile(r"^##(?!#)[ \t]+(.*?)[ \t]*#*[ \t]*$")

DecisionPage = namedtuple("DecisionPage", "path name meta text")


def opts_in(meta):
    """Pure. True when the frontmatter says `kind: decision` (any case),
    or `kind` is a list with that item."""
    kind = meta.get("kind", "")
    kinds = kind if isinstance(kind, list) else [kind]
    return any(k.strip().casefold() == "decision" for k in kinds)


def decision_pages(files, pages):
    """Pure. The pages among `pages` that opt in, keyed by page name (the
    file name without '.md'). A page whose frontmatter does not parse at
    all is left to lint.py's FM check."""
    found = {}
    for path in pages:
        meta, _ = parse_frontmatter(files[path])
        if meta is not None and opts_in(meta):
            name = PurePosixPath(path).stem
            found[name] = DecisionPage(path, name, meta, files[path])
    return found


def link_values(meta, key):
    """Pure. `supersedes` / `superseded_by` as a list of distinct values in
    written order. An absent key, an empty value and `[]` all mean
    "none"."""
    raw = meta.get(key, "")
    values = raw if isinstance(raw, list) else [raw]
    out = []
    for value in values:
        value = value.strip()
        if value and value not in out:
            out.append(value)
    return out


def shown(value):
    """Pure. A frontmatter value as a finding message quotes it."""
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]"
    return value


def section_names(text, strip_code):
    """Pure. The casefolded text of every level-2 heading outside fenced
    code, with runs of spaces collapsed. Lines are split on '\\n' and a
    trailing '\\r' is dropped, so a CRLF page reads the same as an LF one."""
    names = set()
    for line in strip_code(text).split("\n"):
        m = H2_RE.match(line.rstrip("\r"))
        if m:
            names.add(" ".join(m.group(1).split()).casefold())
    return names


def page_findings(page, strip_code):
    """Pure. Status, date and section findings for one decision page."""
    findings = []

    def report(message):
        findings.append(Finding("ERROR", CODE, page.path, message))

    status = page.meta.get("status", "")
    if status in ("", []):
        report("missing required field 'status'")
    elif status not in DECISION_STATUSES:
        report(f"status '{shown(status)}' is not one of: "
               + ", ".join(DECISION_STATUSES))
    decided = page.meta.get("decided")
    if decided is not None and (isinstance(decided, list)
                                or not DATE_RE.match(decided)):
        report(f"decided '{shown(decided)}' is not a YYYY-MM-DD date")
    present = section_names(page.text, strip_code)
    for section in REQUIRED_SECTIONS:
        if section.casefold() not in present:
            report(f"missing required section '## {section}'")
    return findings


def link_findings(page, key, files, decisions):
    """Pure. Shape and target findings for one link key of one page, and
    the values that passed both -- only those take part in the
    replacement checks. A page name is a file name without '.md'; a value
    with a folder or the suffix is refused with the name it should be."""
    findings = []
    valid = []
    for value in link_values(page.meta, key):
        if "/" in value or value.endswith(".md"):
            stem = PurePosixPath(value).name
            if stem.endswith(".md"):
                stem = stem[:-len(".md")]
            message = f"{key} value '{value}' is not a page name; write '{stem}'"
        elif f"wiki/{value}.md" not in files:
            message = f"{key} names '{value}', but wiki/{value}.md does not exist"
        elif value not in decisions:
            message = (f"{key} names '{value}', but wiki/{value}.md "
                       "is not a decision page")
        else:
            valid.append(value)
            continue
        findings.append(Finding("ERROR", CODE, page.path, message))
    return findings, valid


def check_decisions(files, pages, strip_code, extract_links):
    """Pure. Every DECISION finding for the wiki in `files`.

    `pages` is lint.py's list of wiki pages (_wiki_pages); `strip_code`
    blanks fenced code and inline code spans and keeps the line count;
    `extract_links` returns the link targets of a text."""
    decisions = decision_pages(files, pages)
    findings = []
    for name in sorted(decisions):
        page = decisions[name]
        findings += page_findings(page, strip_code)
        for key in LINK_KEYS:
            findings += link_findings(page, key, files, decisions)[0]
    return findings
