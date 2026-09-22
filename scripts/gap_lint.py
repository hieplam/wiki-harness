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


def _run_git(root, args, timeout_label):
    """Impure edge. One subprocess.run wrapper shared by every git call
    below, so every caller gets the same OSError/timeout handling and the
    same bounded wait. Returns (CompletedProcess or None, error or None)."""
    try:
        return subprocess.run(args, cwd=str(root), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              timeout=_SUBPROCESS_TIMEOUT), None
    except OSError as exc:
        return None, "git could not be run: {}".format(exc)
    except subprocess.TimeoutExpired:
        return None, "{} timed out".format(timeout_label)


_RepoState = namedtuple("_RepoState", "unborn head_resolves error")


def _resolve_repo_state(root):
    """Impure edge. Resolves, ONCE, the two structural git facts that both
    `_git_bytes` and `_staged_deletions` independently need to decide
    whether HEAD is safe to trust: "is this repository truly unborn" and,
    if not, "does HEAD actually resolve to a commit". Both callers used to
    ask git these same two questions themselves, doubling the only
    call here (`git rev-list --all --count`) that scales with total
    history size, for two answers guaranteed identical within one
    `gather()` invocation. Resolving it once here and threading the
    result through as an explicit parameter removes that duplication
    without any module-level cache or other mutable global state.

    Returns a `_RepoState`:
    - `.error` set: git itself could not answer (missing, timed out, or
      failed) -- `.unborn`/`.head_resolves` are meaningless in that case.
      Fail closed: callers must surface `.error`, never read this as
      "clean".
    - `.error` is None and `.unborn` is True: `_commit_count` found zero
      commits reachable from any ref -- genuinely unborn.
    - `.error` is None and `.unborn` is False: history exists somewhere;
      `.head_resolves` says whether HEAD itself names a real commit
      (`_head_resolves`, decided purely by exit code -- see its docstring
      for why that must never be stderr text).
    """
    count, error = _commit_count(root)
    if error is not None:
        return _RepoState(unborn=False, head_resolves=False, error=error)
    if count == 0:
        return _RepoState(unborn=True, head_resolves=False, error=None)
    resolves, error = _head_resolves(root)
    if error is not None:
        return _RepoState(unborn=False, head_resolves=False, error=error)
    return _RepoState(unborn=False, head_resolves=resolves, error=None)


def _commit_count(root):
    """Impure edge. The number of commits reachable from ANY ref, or an
    error. This is the structural test for "truly unborn": a repository
    with zero commits anywhere has nothing committed for any path, full
    stop. It is deliberately `--all`, not just HEAD, so a HEAD that has
    been pointed at a nonexistent ref (the demonstrated attack) is not
    confused with a genuinely fresh repository -- the attack repo still
    has a real commit reachable from refs/heads/main, so this returns a
    positive count and routes into the HEAD-resolution check below instead
    of the unborn short-circuit."""
    result, error = _run_git(root, ["git", "rev-list", "--all", "--count"],
                             "git rev-list")
    if error is not None:
        return None, error
    if result.returncode != 0:
        return None, (result.stderr.decode("utf-8", "replace").strip()
                      or "git rev-list failed")
    text = result.stdout.decode("utf-8", "replace").strip()
    try:
        return int(text), None
    except ValueError:
        return None, "git rev-list returned unparseable output: {!r}".format(text)


def _head_resolves(root):
    """Impure edge. Whether HEAD names a real, existing commit -- decided
    purely by exit code, never by reading stderr. `git rev-parse --verify`
    exits 0 only when the ref chain actually resolves to an object; a HEAD
    that names a branch that was never created (the attack: `ref:
    refs/heads/ghost`) or a bogus SHA both exit non-zero here regardless of
    what stderr says."""
    result, error = _run_git(root, ["git", "rev-parse", "--verify", "-q", "HEAD"],
                             "git rev-parse")
    if error is not None:
        return None, error
    return result.returncode == 0, None


def _path_in_head(root, path):
    """Impure edge. Whether <path> exists in the tree at HEAD -- decided
    by exit code. Only ever called after `_head_resolves` has confirmed
    HEAD itself is good, so a non-zero exit here can only mean "this path
    was never committed", the legitimate case."""
    result, error = _run_git(root, ["git", "cat-file", "-e", "HEAD:{}".format(path)],
                             "git cat-file")
    if error is not None:
        return None, error
    return result.returncode == 0, None


def _git_bytes(root, path, state):
    """Impure edge. (bytes or None, error or None) for the committed
    content of <path> at HEAD.

    `state` is a `_RepoState` already resolved once by
    `_resolve_repo_state` for this `gather()` call -- see its docstring.
    This function makes no `_commit_count`/`_head_resolves` calls of its
    own; it only judges the state it was given.

    Three states are possible, and each is decided by an exit code or an
    explicit count -- never by matching git's human-readable stderr text.
    Stderr matching is what the demonstrated bypass exploited: writing
    `ref: refs/heads/ghost` (a ref that was never created) into `.git/HEAD`
    makes `git show HEAD:<path>` fail with "fatal: invalid object name
    'HEAD'." -- the *exact same string* a genuinely unborn repository
    produces -- even though a real commit with a real ledger still exists
    at refs/heads/main. Matching that string can never tell those two
    cases apart; only asking git structurally can.

    1. `state.error` is set: some git invocation behind the state failed
       or timed out. Fail closed: (None, error).
    2. `state.unborn` is True: the repository has no commits at all,
       anywhere. Nothing is committed for any path yet; (b"", None) is
       the truthful answer.
    3. `state.head_resolves` is True, but the path is not present in that
       commit's tree (`_path_in_head` is False): the path has simply
       never been committed. Legitimate; (b"", None).
    4. Anything else -- commits exist somewhere but HEAD does not resolve
       (a dangling or forged ref, or any other corruption). Fail closed:
       (None, error).
    """
    if state.error is not None:
        return None, state.error
    if state.unborn:
        return b"", None
    if not state.head_resolves:
        return None, ("HEAD does not resolve to a commit even though the "
                      "repository has history -- refusing to treat a "
                      "dangling or forged HEAD as clean")

    present, error = _path_in_head(root, path)
    if error is not None:
        return None, error
    if not present:
        return b"", None

    result, error = _run_git(root, ["git", "show", "HEAD:{}".format(path)],
                             "git show")
    if error is not None:
        return None, error
    if result.returncode != 0:
        return None, (result.stderr.decode("utf-8", "replace").strip()
                      or "git show failed")
    return result.stdout, None


def _staged_deletions(root, path, state):
    """Impure edge. Counts removal lines in the staged diff for one path.

    `state` is the same `_RepoState` `_git_bytes` was given for this
    `gather()` call -- resolved once by `_resolve_repo_state`, not
    re-derived here.

    `git diff --cached` silently diffs against git's empty tree when HEAD
    does not resolve -- it never fails, it just reports every staged line
    as a pure insertion with zero deletions, which is precisely how the
    second "independent" mechanism was shown to share the same blind spot
    as `_git_bytes`. So this must not trust the numstat output at all
    unless `state` has already confirmed HEAD is in a state where "diff
    against HEAD" is a meaningful question: either the repository is truly
    unborn (nothing to diff against, so 0 is correct), or HEAD actually
    resolves. Anything else -- history exists but HEAD does not resolve,
    or `state.error` is set -- is an error, not a silent 0."""
    if state.error is not None:
        return 0, state.error
    if not state.unborn and not state.head_resolves:
        return 0, ("HEAD does not resolve to a commit even though the "
                   "repository has history -- refusing to treat the "
                   "staged diff as clean")

    result, error = _run_git(
        root, ["git", "diff", "--cached", "--numstat", "--", path], "git diff")
    if error is not None:
        return 0, error
    if result.returncode != 0:
        return 0, (result.stderr.decode("utf-8", "replace").strip()
                   or "git diff failed")
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
    state = _resolve_repo_state(root)
    head_bytes, git_error = _git_bytes(root, gap_ledger.LEDGER_PATH, state)
    deleted, diff_error = _staged_deletions(root, gap_ledger.LEDGER_PATH, state)
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

    Whether a wiki adopted the ledger feature is a question about HISTORY,
    not about the working tree: the working tree is exactly what an
    attacker controls. A wiki that never adopted the feature has no ledger
    or schema in the working tree AND nothing recorded for the ledger in
    HEAD, and git could actually be asked -- that combination is the only
    safe "clean, nothing to check" state.

    Checking only the working tree (the old guard: no ledger text and no
    schema text) cannot distinguish "never adopted" from "adopted, then
    deleted": an agent that deletes the whole gaps/ folder -- ledger and
    schema together, not just the ledger -- makes both working-tree checks
    true even though HEAD still holds a committed ledger, so the old guard
    returned [] and silently discarded the tampering. Requiring head_bytes
    to also be empty closes that: a ledger present in HEAD means the wiki
    adopted it, so its disappearance from the working tree is tampering,
    not non-adoption. Requiring git_error to be absent keeps this fail
    closed per V3: an "unknown" git state must never read as "never
    adopted", i.e. as clean."""
    inputs = gather(root)
    never_adopted = (not inputs.ledger_text
                     and inputs.schema_text is None
                     and not inputs.head_bytes
                     and not inputs.git_error)
    if never_adopted:
        return []
    return check_gaps(inputs)
