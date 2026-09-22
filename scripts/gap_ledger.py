#!/usr/bin/env python3
"""Pure core for the knowledge-gap ledger.

Owns the whole answer to "is this ledger valid, and what does it say?" - the
JSONL parser, the schema loader, record validation, the status fold, the
rendered view and the append-only comparator. Every function here takes
already-fetched data and returns a result: no filesystem, no subprocess, no
clock, no environment. scripts/gap.py and scripts/gap_lint.py are the impure
edges that supply that data.

Gap record rules are DATA, not code: gaps/gap-schema.json is the single
source of truth, read both by this module and by the agent writing records.

Python 3 stdlib only.
"""
from __future__ import annotations

import json
import re

LEDGER_PATH = "gaps/knowledge-gaps.jsonl"
VIEW_PATH = "gaps/KNOWLEDGE_GAP.md"
GAP_SCHEMA_PATH = "gaps/gap-schema.json"

# Fallback only -- used when the schema is missing or malformed (that case
# already produces its own finding) or when a schema simply does not declare
# an id_pattern. The schema's own id_pattern, when present, is the single,
# sole declaration of gap-id shape.
DEFAULT_GAP_ID_PATTERN = r"^gap-\d{4}-\d{2}-\d{2}-\d{3}$"

GAP_TYPE = "gap"


def load_gap_schema(text):
    """Pure. Schema text in -> (schema dict, error message) out.
    Exactly one of the two is None."""
    if text is None:
        return None, "gap schema is missing"
    try:
        schema = json.loads(text)
    except ValueError as exc:
        return None, "gap schema could not be parsed: {}".format(exc)
    if not isinstance(schema, dict):
        return None, "gap schema must be a JSON object"
    if not isinstance(schema.get("types"), dict) or not schema["types"]:
        return None, "gap schema must declare a non-empty 'types' object"
    return schema, None


def gap_id_pattern_from_schema(schema):
    """Pure. The schema's declared id shape, or the module default."""
    if isinstance(schema, dict):
        pattern = schema.get("id_pattern")
        if isinstance(pattern, str) and pattern:
            return pattern
    return DEFAULT_GAP_ID_PATTERN


def parse_ledger(text):
    """Pure. Ledger text in -> ([(lineno, record)], [(lineno, message)]) out.

    An absent ledger is represented by an empty string and is clean: a wiki
    that has recorded no gaps has no file, and that is not an error.
    """
    records = []
    errors = []
    if not text:
        return records, errors
    if not text.endswith("\n"):
        errors.append((len(text.splitlines()),
                       "last line does not end with a newline"))
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            errors.append((lineno, "blank lines are not allowed"))
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            errors.append((lineno, "line is not valid JSON: {}".format(exc)))
            continue
        if not isinstance(record, dict):
            errors.append((lineno, "line must be a JSON object"))
            continue
        records.append((lineno, record))
    return records, errors


def validate_records(records, schema, id_pattern):
    """Pure. [(lineno, record)] + schema in -> [(lineno, message)] out.

    Enforces the closed key set per record type, id shape and uniqueness,
    declared enums, non-empty list keys, and that every reference points at
    a gap declared EARLIER in the file (which is what makes a single
    forward pass sufficient, here and in the fold).
    """
    errors = []
    types = schema.get("types", {}) if isinstance(schema, dict) else {}
    enums = schema.get("enums", {}) if isinstance(schema, dict) else {}
    list_keys = set(schema.get("list_keys", []) if isinstance(schema, dict) else [])
    try:
        id_re = re.compile(id_pattern)
    except re.error:
        id_re = re.compile(DEFAULT_GAP_ID_PATTERN)

    # Every gap id declared anywhere in the ledger, regardless of line order.
    # Needed to tell "this gap simply does not exist" apart from "this gap
    # exists but appears later than its reference" -- the forward pass below
    # still enforces ordering via seen_ids, this set only classifies misses.
    all_gap_ids = {
        record.get("id")
        for _, record in records
        if record.get("type") == GAP_TYPE and isinstance(record.get("id"), str)
    }

    seen_ids = set()
    for lineno, record in records:
        rtype = record.get("type")
        if rtype not in types:
            errors.append((lineno, "unknown record type {!r}".format(rtype)))
            continue
        spec = types[rtype]
        allowed = set(spec.get("required", [])) | set(spec.get("optional", []))
        for key in sorted(set(record) - allowed):
            errors.append((lineno, "key {!r} is not declared for type {!r} "
                                   "in the gap schema".format(key, rtype)))
        for key in sorted(k for k in spec.get("required", []) if k not in record):
            errors.append((lineno, "required key {!r} is missing for type "
                                   "{!r}".format(key, rtype)))
        for key in sorted(set(record) & list_keys):
            value = record[key]
            if not isinstance(value, list) or not value:
                errors.append((lineno, "key {!r} must be a non-empty "
                                       "list".format(key)))
        for key in sorted(set(record) & allowed):
            enum_values = enums.get("{}.{}".format(rtype, key))
            if enum_values and record[key] not in enum_values:
                errors.append((lineno, "key {!r} must be one of {}".format(
                    key, ", ".join(enum_values))))

        if rtype == GAP_TYPE:
            gid = record.get("id")
            if isinstance(gid, str):
                if not id_re.match(gid):
                    errors.append((lineno, "id {!r} does not match the schema's "
                                           "id_pattern".format(gid)))
                elif gid in seen_ids:
                    errors.append((lineno, "duplicate gap id {!r}".format(gid)))
                else:
                    seen_ids.add(gid)
        else:
            ref = record.get("gap")
            if isinstance(ref, str) and ref not in seen_ids:
                if ref in all_gap_ids:
                    errors.append((lineno, "references gap {!r}, which must be "
                                           "declared on an earlier line".format(ref)))
                else:
                    errors.append((lineno, "references unknown gap "
                                           "{!r}".format(ref)))
    return errors


STATUS_OPENED = "opened"
STATUS_ANSWERED = "answered"
STATUS_UNRELATED = "unrelated"

# How each record type moves a gap's status. A 'resolution' is intent, not
# evidence, so it is deliberately absent: recording which card is MEANT to
# answer a gap does not make the wiki able to answer it. Only a measurement
# -- an actual re-run against the wiki -- is evidence.
_VERDICT_STATUS = {
    ("measurement", "answered"): STATUS_ANSWERED,
    ("measurement", "partial"): STATUS_OPENED,
    ("measurement", "still-missing"): STATUS_OPENED,
    ("ratification", "unrelated"): STATUS_UNRELATED,
}

_ID_DATE_SEQ_RE = re.compile(r"^gap-(\d{4}-\d{2}-\d{2})-(\d{3})$")


def fold_status(records):
    """Pure. [(lineno, record)] in -> {gap id: status} out.

    Walks the records in FILE ORDER -- the order they appear in the file --
    and NOT in 'at' order. In an append-only log the append order is the
    truth; 'at' is descriptive metadata and may legitimately be out of
    order (a backfilled measurement, clock skew, a timezone mistake).
    Every gap starts at 'opened'; the last record that carries a verdict
    wins.
    """
    statuses = {}
    for _lineno, record in records:
        rtype = record.get("type")
        if rtype == GAP_TYPE:
            gid = record.get("id")
            if isinstance(gid, str):
                statuses.setdefault(gid, STATUS_OPENED)
            continue
        gid = record.get("gap")
        if gid not in statuses:
            continue
        new_status = _VERDICT_STATUS.get((rtype, record.get("verdict")))
        if new_status is not None:
            statuses[gid] = new_status
    return statuses


def next_gap_id(existing_ids, today):
    """Pure. Existing gap ids + a 'YYYY-MM-DD' string in -> the next id out.

    Counts from the HIGHEST sequence already used today, never from how
    many ids exist: a hand-deleted middle id must not cause a collision.
    """
    highest = 0
    for gid in existing_ids:
        match = _ID_DATE_SEQ_RE.match(gid or "")
        if match and match.group(1) == today:
            highest = max(highest, int(match.group(2)))
    return "gap-{}-{:03d}".format(today, highest + 1)


VIEW_HEADER = (
    "# Knowledge gaps\n"
    "\n"
    "Questions this wiki could not answer, and what happened to them.\n"
    "\n"
    "**This file is generated.** It is rendered from `knowledge-gaps.jsonl` by\n"
    "`scripts/gap.py render`; edit the ledger, never this view. Status is folded\n"
    "from the ledger records in file order -- see `AGENTS.md` in this folder.\n"
    "\n"
)

_VIEW_COLUMNS = ("Gap", "Status", "Service", "Topics", "Question", "Answering card", "Note")


def _cell(value):
    """Pure. One prose value in -> one table-safe cell out. A pipe would end
    the cell and a newline would end the row, so both are neutralised."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value)
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(text.split("\n"))
    return text.replace("|", r"\|").strip()


def render_view(records):
    """Pure. [(lineno, record)] in -> the full markdown view out.

    Deterministic: the same records always render byte-identically, which is
    what lets lint compare this against the committed file.
    """
    statuses = fold_status(records)
    gaps = [r for _ln, r in records if r.get("type") == GAP_TYPE]
    if not gaps:
        return VIEW_HEADER + "No gaps recorded yet.\n"

    cards = {}
    notes = {}
    for _ln, record in records:
        rtype = record.get("type")
        if rtype == "resolution":
            cards[record.get("gap")] = record.get("card")
        elif rtype == "ratification":
            notes[record.get("gap")] = record.get("reason")

    lines = [VIEW_HEADER.rstrip("\n"), ""]
    lines.append("| " + " | ".join(_VIEW_COLUMNS) + " |")
    lines.append("|" + "|".join(["---"] * len(_VIEW_COLUMNS)) + "|")
    for record in gaps:
        gid = record.get("id")
        lines.append("| " + " | ".join((
            _cell(gid),
            _cell(statuses.get(gid, STATUS_OPENED)),
            _cell(record.get("service")),
            _cell(record.get("topics")),
            _cell(record.get("question")),
            _cell(cards.get(gid)),
            _cell(notes.get(gid)),
        )) + " |")
    return "\n".join(lines) + "\n"
