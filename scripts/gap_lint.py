#!/usr/bin/env python3
"""Knowledge-gap ledger lint.

One pure decision function, check_gaps(), takes an already-gathered
GapInputs and returns Findings; one impure edge, gather(), reads the
filesystem and git to build that GapInputs. scripts/lint.py calls gather()
then check_gaps(), exactly as it already does for its other checks.

Python 3 stdlib only.
"""
from __future__ import annotations

import subprocess
from collections import namedtuple
from pathlib import Path

from card_frontmatter_lint import Finding

import gap_ledger

# Matches scripts/lint.py's SUBPROCESS_TIMEOUT: every subprocess.run call
# must bound its wait, so a hung git process cannot hang the lint.
_SUBPROCESS_TIMEOUT = 30

GapInputs = namedtuple(
    "GapInputs",
    "ledger_text view_text schema_text head_bytes work_bytes "
    "deleted_lines git_error card_ids page_paths")


def check_gaps(inputs):
    """Pure. A GapInputs in -> a Finding list out. No I/O of any kind."""
    findings = []

    # V3: a git failure means "unknown", and unknown must never read as
    # "clean". Fail closed before anything else is judged.
    if inputs.git_error:
        findings.append(Finding(
            "ERROR", "GAP_APPEND", gap_ledger.LEDGER_PATH,
            "could not verify the append-only history: {}".format(inputs.git_error)))

    schema, schema_error = gap_ledger.load_gap_schema(inputs.schema_text)
    if schema_error:
        findings.append(Finding("ERROR", "GAP_SCHEMA",
                                gap_ledger.GAP_SCHEMA_PATH, schema_error))

    records, parse_errors = gap_ledger.parse_ledger(inputs.ledger_text)
    for lineno, message in parse_errors:
        findings.append(Finding("ERROR", "GAP", gap_ledger.LEDGER_PATH,
                                "line {}: {}".format(lineno, message)))

    if schema is not None:
        pattern = gap_ledger.gap_id_pattern_from_schema(schema)
        for lineno, message in gap_ledger.validate_records(records, schema, pattern):
            findings.append(Finding("ERROR", "GAP", gap_ledger.LEDGER_PATH,
                                    "line {}: {}".format(lineno, message)))

    for lineno, record in records:
        if record.get("type") != "resolution":
            continue
        card = record.get("card")
        if isinstance(card, str) and card not in inputs.card_ids:
            findings.append(Finding(
                "ERROR", "GAP", gap_ledger.LEDGER_PATH,
                "line {}: resolution names card {!r}, which does not "
                "exist".format(lineno, card)))
        page = record.get("wiki_page")
        if isinstance(page, str) and page not in inputs.page_paths:
            findings.append(Finding(
                "ERROR", "GAP", gap_ledger.LEDGER_PATH,
                "line {}: resolution names page {!r}, which does not "
                "exist".format(lineno, page)))

    violation = gap_ledger.append_only_violation(inputs.head_bytes, inputs.work_bytes)
    if violation:
        findings.append(Finding("ERROR", "GAP_APPEND",
                                gap_ledger.LEDGER_PATH, violation))

    # Second, independent mechanism: a staged diff that removes lines is a
    # violation on its own evidence, through a different code path.
    if inputs.deleted_lines:
        findings.append(Finding(
            "ERROR", "GAP_APPEND", gap_ledger.LEDGER_PATH,
            "the staged change removes {} line(s); the ledger is "
            "append-only".format(inputs.deleted_lines)))

    if inputs.ledger_text or inputs.view_text:
        expected = gap_ledger.render_view(records)
        if inputs.view_text != expected:
            findings.append(Finding(
                "ERROR", "GAP_VIEW", gap_ledger.VIEW_PATH,
                "the generated view is out of date; regenerate it with "
                "'python3 scripts/gap.py render'"))
    return findings


def _git_bytes(root, rev_path):
    """Impure edge. (bytes or None, error or None). None bytes with no
    error means the path is simply not in HEAD yet -- the legitimate
    first-commit case."""
    try:
        result = subprocess.run(["git", "show", rev_path], cwd=str(root),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=_SUBPROCESS_TIMEOUT)
    except OSError as exc:
        return None, "git could not be run: {}".format(exc)
    except subprocess.TimeoutExpired:
        return None, "git show timed out"
    if result.returncode == 0:
        return result.stdout, None
    stderr = result.stderr.decode("utf-8", "replace")
    if "does not exist" in stderr or "exists on disk, but not in" in stderr:
        return b"", None
    if "unknown revision" in stderr or "bad revision" in stderr:
        return b"", None
    return None, stderr.strip() or "git show failed"


def _staged_deletions(root, path):
    """Impure edge. Counts removal lines in the staged diff for one path."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--numstat", "--", path],
            cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=_SUBPROCESS_TIMEOUT)
    except OSError as exc:
        return 0, "git could not be run: {}".format(exc)
    except subprocess.TimeoutExpired:
        return 0, "git diff timed out"
    if result.returncode != 0:
        return 0, result.stderr.decode("utf-8", "replace").strip() or "git diff failed"
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1]), None
    return 0, None


def _read_text(path):
    """Impure edge. Missing file reads as empty -- a wiki that has recorded
    no gaps has no ledger, and that is not an error."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def gather(root):
    """Impure edge. Builds the GapInputs check_gaps() judges."""
    root = Path(root)
    ledger = root / gap_ledger.LEDGER_PATH
    head_bytes, git_error = _git_bytes(root, "HEAD:{}".format(gap_ledger.LEDGER_PATH))
    deleted, diff_error = _staged_deletions(root, gap_ledger.LEDGER_PATH)
    try:
        work_bytes = ledger.read_bytes()
    except OSError:
        work_bytes = b""
    schema_path = root / gap_ledger.GAP_SCHEMA_PATH
    schema_text = _read_text(schema_path) if schema_path.is_file() else None
    card_ids = frozenset(p.stem for p in (root / "sources" / "cards").glob("src-*.md"))
    page_paths = frozenset(
        p.relative_to(root).as_posix() for p in (root / "wiki").glob("*.md"))
    return GapInputs(
        ledger_text=_read_text(ledger),
        view_text=_read_text(root / gap_ledger.VIEW_PATH),
        schema_text=schema_text,
        head_bytes=head_bytes,
        work_bytes=work_bytes,
        deleted_lines=deleted,
        git_error=git_error or diff_error,
        card_ids=card_ids,
        page_paths=page_paths,
    )


def run(root):
    """Impure edge. The one entry point scripts/lint.py calls.

    A wiki with neither a ledger nor a gap schema has not adopted the
    feature and is clean -- that is the pre-upgrade state, and it must not
    produce findings."""
    inputs = gather(root)
    if not inputs.ledger_text and inputs.schema_text is None:
        return []
    return check_gaps(inputs)
