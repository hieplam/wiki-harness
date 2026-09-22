#!/usr/bin/env python3
"""Write to the knowledge-gap ledger.

The only supported way to add a record. It owns the id, the timestamp, the
key order and the JSON encoding, so a record's shape never depends on
whoever -- or whatever -- is writing it. Validation runs BEFORE anything is
written: a rejected call leaves the ledger byte-identical.

The ledger is append-only. This tool only ever appends.

Python 3 stdlib only.
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

import gap_ledger

# Matches gap_lint.py's own _SUBPROCESS_TIMEOUT: every subprocess.run call
# must bound its wait, so a hung git process cannot hang forever (A5,
# fail-closed-edges.md obligation 3, enforced repo-wide by
# tests/test_hardening_backlog.py).
_SUBPROCESS_TIMEOUT = 30

RECORD_KEY_ORDER = (
    "type", "id", "gap", "at", "service", "session", "topics", "context",
    "prompt_verbatim", "question", "wiki_answer", "answer_given",
    "card", "wiki_page", "verdict", "reason",
)

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_COMMIT_FAILED = 3


def read_value(raw):
    """Impure edge. '@path' reads a file, '-' reads stdin, anything else is
    the literal value. Prose fields carry paragraphs, so a shell argument
    is not always the right container.

    A value that genuinely starts with a literal '@' (say, an answer
    quoting an @-mention) cannot be entered this way -- write it to a file
    and pass '@that-file' instead. This mirrors the same convention curl
    and other stdlib-adjacent tools already use for '@file' arguments, so
    it is a known, accepted trade-off rather than an oversight."""
    if raw is None:
        return None
    if raw == "-":
        return sys.stdin.read().strip()
    if raw.startswith("@"):
        return Path(raw[1:]).read_text(encoding="utf-8").strip()
    return raw


def ordered(record):
    """Pure. A record dict in -> the same dict in canonical key order out,
    so two runs of the same input produce byte-identical JSON."""
    return {k: record[k] for k in RECORD_KEY_ORDER if k in record}


def encode(record):
    """Pure. A record in -> exactly one newline-terminated JSON line out."""
    return json.dumps(ordered(record), ensure_ascii=False) + "\n"


def load_ledger(root):
    """Impure edge. Returns the ledger text, or '' when there is none."""
    path = Path(root) / gap_ledger.LEDGER_PATH
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def load_schema(root):
    """Impure edge."""
    path = Path(root) / gap_ledger.GAP_SCHEMA_PATH
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    return gap_ledger.load_gap_schema(text)


def append_record(root, record):
    """Impure edge. Creates gaps/ and the ledger on demand -- an upgrade
    never writes seeded paths, so first write is where they appear -- then
    appends one line and regenerates the view."""
    root = Path(root)
    (root / "gaps").mkdir(parents=True, exist_ok=True)
    ledger_path = root / gap_ledger.LEDGER_PATH
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(encode(record))
    render(root)


def render(root):
    """Impure edge. Regenerates the markdown view from the ledger."""
    root = Path(root)
    records, _errors = gap_ledger.parse_ledger(load_ledger(root))
    (root / "gaps").mkdir(parents=True, exist_ok=True)
    (root / gap_ledger.VIEW_PATH).write_text(
        gap_ledger.render_view(records), encoding="utf-8")


def commit(root, gap_id, summary):
    """Impure edge. One path-scoped commit per ledger operation, so an
    unrelated in-flight edit elsewhere in the wiki is never swept in.

    A hung git process must not hang this call forever, so both
    subprocess.run calls below are bounded (see _SUBPROCESS_TIMEOUT); a
    timeout is reported the same way a non-zero exit is -- the append has
    already happened on disk either way, so this never loses the record."""
    root = Path(root)
    paths = [gap_ledger.LEDGER_PATH, gap_ledger.VIEW_PATH]
    try:
        add = subprocess.run(["git", "add", "--"] + paths, cwd=str(root),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=_SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "git add failed: {}".format(exc)
    if add.returncode != 0:
        return add.returncode, add.stderr.decode("utf-8", "replace")
    message = "gap({}): {}".format(gap_id, summary)
    try:
        done = subprocess.run(["git", "commit", "-m", message, "--"] + paths,
                              cwd=str(root), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=_SUBPROCESS_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "git commit failed: {}".format(exc)
    return done.returncode, (done.stdout + done.stderr).decode("utf-8", "replace")


def validate_or_fail(root, record):
    """Impure edge wrapping the pure validator. Validates the record IN
    CONTEXT -- against the whole ledger it is about to join -- so a bad
    reference or a duplicate id is caught before a byte is written."""
    schema, error = load_schema(root)
    if error:
        return "gap schema is unusable: {}".format(error)
    text = load_ledger(root)
    records, parse_errors = gap_ledger.parse_ledger(text)
    if parse_errors:
        lineno, message = parse_errors[0]
        return ("the existing ledger is invalid at line {}: {} -- fix it "
                "before appending".format(lineno, message))
    pattern = gap_ledger.gap_id_pattern_from_schema(schema)
    candidate = records + [(len(records) + 1, ordered(record))]
    errors = gap_ledger.validate_records(candidate, schema, pattern)
    if errors:
        return "; ".join(m for _ln, m in errors)
    return None


def existing_gap_ids(root):
    """Impure edge."""
    records, _ = gap_ledger.parse_ledger(load_ledger(root))
    return [r.get("id") for _ln, r in records if r.get("type") == "gap"]


def build_add(args, root, now):
    topics = [t.strip() for t in (args.topics or "").split(",") if t.strip()]
    if not topics:
        return None, "--topics must name at least one topic"
    gap_id = gap_ledger.next_gap_id(existing_gap_ids(root), now.date().isoformat())
    return {
        "type": "gap", "id": gap_id, "at": now.isoformat(),
        "service": args.service, "session": args.session,
        "topics": topics, "context": read_value(args.context),
        "prompt_verbatim": read_value(args.prompt),
        "question": read_value(args.question),
        "wiki_answer": read_value(args.wiki_answer),
        "answer_given": read_value(args.answer_given),
    }, None


def _list_cell(value):
    """Pure. Keeps 'list' output tab-separated and one line per gap: a
    prose field is free-form and may itself contain a tab or a newline, and
    either would corrupt the column layout for a caller parsing this
    output."""
    return " ".join(str(value).split())


def main(argv=None, root=None, now=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = Path(root) if root is not None else Path.cwd()
    now = now or datetime.datetime.now(datetime.timezone.utc).astimezone()

    parser = argparse.ArgumentParser(
        prog="gap.py",
        description="Record and track questions this wiki could not answer.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Shared by every subcommand that writes: --no-commit is a per-call
    # choice, not a global mode, so it must parse whether it comes before
    # or after the subcommand name -- argparse only honours an option after
    # the chosen subparser's own arguments if that subparser declares it.
    write_common = argparse.ArgumentParser(add_help=False)
    write_common.add_argument("--no-commit", action="store_true",
                              help="append without making a commit")

    add = subparsers.add_parser(
        "add", parents=[write_common],
        help="record a question the wiki could not answer")
    add.add_argument("--service", required=True, help="repository the question came from")
    add.add_argument("--session", required=True, help="caller session id")
    add.add_argument("--context", required=True, help="what the caller was doing")
    add.add_argument("--prompt", required=True, help="the user's exact words")
    add.add_argument("--question", required=True,
                     help="the exact question asked of the wiki; this is the replayable one")
    add.add_argument("--wiki-answer", required=True,
                     help="what the wiki returned, verbatim; accepts @file or -")
    add.add_argument("--answer-given", required=True,
                     help="what the caller finally told the user; accepts @file or -")
    add.add_argument("--topics", required=True, help="comma-separated topics")

    resolve = subparsers.add_parser(
        "resolve", parents=[write_common],
        help="name the card meant to answer a gap")
    resolve.add_argument("gap_id")
    resolve.add_argument("--card", required=True)
    resolve.add_argument("--page", required=True)

    measure = subparsers.add_parser(
        "measure", parents=[write_common],
        help="record a re-run against the wiki")
    measure.add_argument("gap_id")
    measure.add_argument("--verdict", required=True,
                         choices=["answered", "partial", "still-missing"])
    measure.add_argument("--wiki-answer", required=True, help="accepts @file or -")

    ratify = subparsers.add_parser(
        "ratify", parents=[write_common],
        help="judge a gap out of scope")
    ratify.add_argument("gap_id")
    ratify.add_argument("--verdict", required=True, choices=["unrelated"])
    ratify.add_argument("--reason", required=True)

    subparsers.add_parser("render", help="regenerate the markdown view")

    listing = subparsers.add_parser("list", help="list gaps by folded status")
    listing.add_argument("--status", choices=["opened", "answered", "unrelated"])

    args = parser.parse_args(argv)

    if args.command == "render":
        render(root)
        return EXIT_OK

    if args.command == "list":
        records, _ = gap_ledger.parse_ledger(load_ledger(root))
        statuses = gap_ledger.fold_status(records)
        for _ln, record in records:
            if record.get("type") != "gap":
                continue
            status = statuses.get(record.get("id"), gap_ledger.STATUS_OPENED)
            if args.status and status != args.status:
                continue
            print("{}\t{}\t{}".format(
                _list_cell(record.get("id")), _list_cell(status),
                _list_cell(record.get("question", ""))))
        return EXIT_OK

    now_iso = now.isoformat()
    if args.command == "add":
        record, error = build_add(args, root, now)
        if error:
            print("gap: {}".format(error), file=sys.stderr)
            return EXIT_INVALID
        summary = "record unanswered question"
        gap_id = record["id"]
    elif args.command == "resolve":
        gap_id = args.gap_id
        record = {"type": "resolution", "gap": gap_id, "at": now_iso,
                  "card": args.card, "wiki_page": args.page}
        summary = "name the answering card"
    elif args.command == "measure":
        gap_id = args.gap_id
        record = {"type": "measurement", "gap": gap_id, "at": now_iso,
                  "verdict": args.verdict,
                  "wiki_answer": read_value(args.wiki_answer)}
        summary = "measure the wiki ({})".format(args.verdict)
    else:
        gap_id = args.gap_id
        record = {"type": "ratification", "gap": gap_id, "at": now_iso,
                  "verdict": args.verdict, "reason": args.reason}
        summary = "ratify as unrelated"

    error = validate_or_fail(root, record)
    if error:
        print("gap: refusing to write an invalid record: {}".format(error),
              file=sys.stderr)
        return EXIT_INVALID

    append_record(root, record)

    if args.no_commit:
        return EXIT_OK
    code, output = commit(root, gap_id, summary)
    if code != 0:
        print("gap: the record was appended but the commit failed; the line "
              "is on disk and uncommitted.\n{}".format(output), file=sys.stderr)
        return EXIT_COMMIT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
