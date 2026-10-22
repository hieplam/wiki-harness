#!/usr/bin/env python3
"""Decision page lint: the checks for wiki pages that opt in with
`kind: decision` -- their status and date, their four required sections,
and the `supersedes` / `superseded_by` links between them, which must name
each other and must not loop -- and the `## Decisions` section of index.md,
which lists every decision page with its status.

A page without `kind: decision` is never judged here, whatever other keys
it carries: a wiki that uses `kind`, `status` or `supersedes` for its own
purpose keeps exactly the findings it had before this module existed.

lint.py's run() calls check_decisions() and hands it lint.py's own page
list, code stripper and link extractor. This module cannot import them,
because lint.py imports this module; receiving them also keeps one fence
parser in the harness instead of two.

Pure, every function: check_decisions(), decision_pages(), opts_in(),
link_values(), shown(), section_names(), page_findings(),
link_findings(), valid_status(), loop_path(), replacement_findings(),
lf(), decisions_entries(), states_status(), index_findings().
There are no impure edges.

Python 3 stdlib only.
"""
from __future__ import annotations

import re
from collections import namedtuple
from pathlib import PurePosixPath

from card_frontmatter_lint import Finding, parse_frontmatter, resolve

CODE = "DECISION"
DECISION_STATUSES = ("proposed", "decided", "superseded")
REQUIRED_SECTIONS = ("Context", "Decision", "Rejected options", "Consequences")
LINK_KEYS = ("supersedes", "superseded_by")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A level-2 ATX heading: exactly two '#', then its text, then optional
# closing '#'s. '### x' is level 3 and does not match.
H2_RE = re.compile(r"^##(?!#)[ \t]+(.*?)[ \t]*#*[ \t]*$")
# A level-1 or level-2 heading: where a `## Decisions` section ends.
SECTION_END_RE = re.compile(r"^#{1,2}(?!#)(?:[ \t]|$)")
# The start of a markdown list item ('-', '*', '+', '1.' or '1)'), with its
# indentation captured.
LIST_ITEM_RE = re.compile(r"^([ \t]*)(?:[-*+]|\d+[.)])[ \t]+")
# A whole inline link, text and target, removed before the status word is
# searched -- a title or a file name that contains "decided" says nothing.
INLINE_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")

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


def lf(text):
    """Pure. `text` with CRLF line ends turned into LF, before strip_code()
    sees it: its fence closer does not match a line that ends in '\\r', so
    on a CRLF page no fence would close and a fenced heading would count."""
    return text.replace("\r\n", "\n")


def section_names(text, strip_code):
    """Pure. The casefolded text of every level-2 heading outside fenced
    code, with runs of spaces collapsed."""
    names = set()
    for line in strip_code(lf(text)).split("\n"):
        m = H2_RE.match(line)
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


def valid_status(meta):
    """Pure. The page's status when it is one of DECISION_STATUSES, else
    None. A page with no valid status gets only its status finding; the
    replacement checks skip it."""
    status = meta.get("status", "")
    return status if status in DECISION_STATUSES else None


def loop_path(start, links):
    """Pure. The first path that follows `superseded_by` from `start` back
    to `start` (['a', 'b', 'a'], or ['a', 'a'] for a page that names
    itself), or None. Neighbours are walked in sorted order, so the same
    wiki always reports the same path. Iterative, so a long chain cannot
    exhaust Python's recursion limit inside a commit hook."""
    stack = [(start, [start])]
    seen = {start}
    while stack:
        name, path = stack.pop()
        for nxt in sorted(links.get(name, {}).get("superseded_by", []), reverse=True):
            if nxt == start:
                return path + [start]
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, path + [nxt]))
    return None


def replacement_findings(decisions, links):
    """Pure. Rows R1-R3, P1-P3 and C1 of the spec. `links[name][key]` holds
    only the values that passed link_findings().

    Only a `decided` or `superseded` page replaces another: a `proposed`
    page's `supersedes` is an intent, and the old page stays as it is.
    "superseded_by is empty" (R1, R2, P1) judges the key as written, so a
    refused value is not reported a second time as a missing one."""
    statuses = {name: valid_status(page.meta) for name, page in decisions.items()}
    replacers = {}
    for name in sorted(decisions):
        if statuses[name] in ("decided", "superseded"):
            for old in links[name]["supersedes"]:
                replacers.setdefault(old, []).append(name)
    findings = []
    for name in sorted(decisions):
        status = statuses[name]
        if status is None:
            continue
        path = decisions[name].path
        is_superseded = status == "superseded"
        has_written_successor = bool(link_values(decisions[name].meta, "superseded_by"))
        successors = links[name]["superseded_by"]

        def report(on_path, message):
            findings.append(Finding("ERROR", CODE, on_path, message))

        if is_superseded and not has_written_successor:
            report(path, "status is 'superseded', but superseded_by is missing")
        if not is_superseded and has_written_successor:
            report(path, f"superseded_by is set, but status is '{status}', "
                         "not 'superseded'")
        if is_superseded:
            for successor in successors:
                if statuses[successor] == "proposed":
                    report(path, f"superseded_by names '{successor}', but "
                                 f"wiki/{successor}.md is still 'proposed'")
                elif (statuses[successor] is not None
                      and name not in links[successor]["supersedes"]):
                    report(decisions[successor].path,
                           f"wiki/{name}.md is superseded_by '{successor}', "
                           f"but supersedes here does not name '{name}'")
        for replacer in replacers.get(name, []):
            if not is_superseded and not has_written_successor:
                report(path, f"wiki/{replacer}.md supersedes this page, but "
                             f"status is '{status}' and superseded_by is missing")
            elif is_superseded and successors and replacer not in successors:
                report(path, f"wiki/{replacer}.md supersedes this page, but "
                             f"superseded_by does not name '{replacer}'")
        loop = loop_path(name, links)
        if loop:
            report(path, "supersedes chain loops back to this page: "
                         + " -> ".join(loop))
    return findings


def decisions_entries(index, strip_code, extract_links):
    """Pure. (has_section, entries) for index.md's `## Decisions` sections.

    A section opens at a level-2 heading whose text is "Decisions" (any
    case) and runs to the next level-1 or level-2 heading; two such
    sections read as one list. An entry is a list item at the section's
    outermost item indentation, and its FIRST link, resolved from index.md,
    is the page it lists. Everything else that belongs to the item -- a
    wrapped line, a deeper (nested) item, an indented line after a blank
    line -- continues it: its text counts toward the status word, and its
    links are references, such as the page a superseded decision points
    to. A line that belongs to no item is prose and is ignored.

    `entries` pairs each listed page with the item's original text, because
    strip_code() also blanks inline code spans and a status may be written
    as `decided`. Headings, items and links are read from the stripped
    text, so nothing inside a fence counts: a fenced line is blank there."""
    text = lf(index)
    stripped = strip_code(text).split("\n")
    original = text.split("\n")
    has_section = False
    in_section = False
    entries = []
    current = None          # [page, [original lines]] of the item being read
    outer_indent = None     # indentation of the section's first list item
    after_blank = False
    for plain, line in zip(stripped, original):
        heading = H2_RE.match(plain)
        if heading and " ".join(heading.group(1).split()).casefold() == "decisions":
            has_section = in_section = True
            current, outer_indent, after_blank = None, None, False
            continue
        if SECTION_END_RE.match(plain):
            in_section = False
            continue
        if not in_section:
            continue
        if not plain.strip():
            after_blank = True
            continue
        item = LIST_ITEM_RE.match(plain)
        indent = len(item.group(1).expandtabs(4)) if item else None
        if item and (outer_indent is None or indent <= outer_indent):
            if outer_indent is None:
                outer_indent = indent
            targets = extract_links(plain)
            current = [resolve("index.md", targets[0]), [line]] if targets else None
            if current:
                entries.append(current)
        elif current is not None and (item or not after_blank or plain[0] in " \t"):
            current[1].append(line)
        else:
            current = None
        after_blank = False
    return has_section, [(page, " ".join(lines)) for page, lines in entries]


def states_status(item, status):
    """Pure. True when `status` appears in the index item's text as a whole
    word, in any case, outside the text and target of every link."""
    rest = INLINE_LINK_RE.sub(" ", item)
    return re.search(rf"\b{status}\b", rest, re.IGNORECASE) is not None


def index_findings(files, decisions, strip_code, extract_links):
    """Pure. The index.md rows of the spec. A missing index.md, and an
    entry that points at a file that does not exist, are lint.py's INDEX
    findings already, so they are not repeated here."""
    index = files.get("index.md")
    if index is None or not decisions:
        return []

    def finding(message):
        return Finding("ERROR", CODE, "index.md", message)

    has_section, entries = decisions_entries(index, strip_code, extract_links)
    if not has_section:
        return [finding("no '## Decisions' section, but decision pages exist")]
    by_path = {page.path: page for page in decisions.values()}
    findings = []
    listed = set()
    for target, item in entries:
        if target not in files:
            continue
        page = by_path.get(target)
        if page is None:
            findings.append(finding(
                f"'## Decisions' lists {target}, which is not a decision page"))
            continue
        listed.add(target)
        status = valid_status(page.meta)
        if status is not None and not states_status(item, status):
            findings.append(finding(
                f"'## Decisions' lists {target} without its status '{status}'"))
    for path in sorted(set(by_path) - listed):
        findings.append(finding(
            f"decision page not listed under '## Decisions': {path}"))
    return findings


def check_decisions(files, pages, strip_code, extract_links):
    """Pure. Every DECISION finding for the wiki in `files`.

    `pages` is lint.py's list of wiki pages (_wiki_pages); `strip_code`
    blanks fenced code and inline code spans and keeps the line count;
    `extract_links` returns the link targets of a text."""
    decisions = decision_pages(files, pages)
    findings = []
    links = {}
    for name in sorted(decisions):
        page = decisions[name]
        findings += page_findings(page, strip_code)
        links[name] = {}
        for key in LINK_KEYS:
            key_findings, valid = link_findings(page, key, files, decisions)
            findings += key_findings
            links[name][key] = valid
    findings += replacement_findings(decisions, links)
    findings += index_findings(files, decisions, strip_code, extract_links)
    return findings
