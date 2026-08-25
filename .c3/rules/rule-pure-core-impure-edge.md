---
id: rule-pure-core-impure-edge
c3-seal: 6e35517905dc9000407161f9b4d11f2cd9a371a8435dd0d3edac519844e75bd6
title: Pure core, impure edges
type: rule
goal: |-
    Keep every non-trivial computation across the library — the lint checks, the manifest diff, the
    upgrade drift/promote decision — callable with plain in-memory data, so it stays deterministic
    (same input, same output, run 1 and run 100), unit-testable without a live filesystem/git
    process, and reviewable from its inputs alone.
---

## Goal

Keep every non-trivial computation across the library — the lint checks, the manifest diff, the
upgrade drift/promote decision — callable with plain in-memory data, so it stays deterministic
(same input, same output, run 1 and run 100), unit-testable without a live filesystem/git
process, and reviewable from its inputs alone.

## Rule

Every `check_*`/`compute_*`/decision function takes already-fetched data as arguments and
returns a result; it never itself touches the filesystem, runs a subprocess, reads the clock, or
reads env/global state — that access happens only inside a small, separately named edge
function that the caller supplies the result of.

## Golden Example

Literal code from `/Users/hip/repo/ogp-wiki/scripts/lint.py` (HEAD `f8b43fb`) — the exact
pattern `scripts/lint.py` is forked byte-identical from (`ref-verbatim-port`) and the pattern
`init.py`/`upgrade.py`/`manifest.py` must extend into the `lifecycle` container:

```python
"""Mechanical lint for the OGP wiki (spec §7.1).

Pure core: parse/extract/resolve helpers and check_* functions (data in ->
Findings out). Impure edges: scan()/git_changes()/main() at the bottom.
Python 3 stdlib only.
"""
from __future__ import annotations

# REQUIRED: every check_* function receives pre-fetched data, returns Findings —
# no I/O inside the function body.
def check_raw_immutability(changes):          # `changes` arrives as a parameter
    ...

def run(files, changes):                      # REQUIRED: the pure orchestrator —
    findings = []                              # `files`/`changes` are plain dicts/lists,
    for check in (check_broken_links, check_orphans, check_card_citations,
                  check_cards, check_frontmatter, check_index_sync):
        findings += check(files)               # every check_* call is pure
    findings += check_raw_immutability(changes)
    return findings

# ---- impure edges below this line ----          # REQUIRED: a clear, commented boundary

def scan(root):                                # OPTIONAL naming, REQUIRED shape: reads disk,
    ...                                         # returns plain data — never calls a check_*

def git_changes(root):                         # REQUIRED: the only place subprocess.run is
    result = subprocess.run(                   # called for git-diff data
        ["git", "-C", str(root), "diff", "HEAD", "--name-status"],
        capture_output=True, text=True)
    ...

def hooks_finding(root):                       # REQUIRED: the only place git-config is read
    ...
```

## Not This

| Anti-Pattern | Correct | Why Wrong Here |
| --- | --- | --- |
| A check_* function calls subprocess.run(["git", ...]) itself to look up changes | Pass the already-computed changes list in as a parameter, as check_raw_immutability(changes) does | A check that shells out cannot be unit-tested without a real git repo, and can silently observe stale state mid-run |
| upgrade.py's drift decision opens and hashes candidate files itself while deciding | Scratch-copy and hash the candidate tree with a thin edge function first, then hand the resulting {path: hash} dict to a pure diff/decision function | Mixing decision with I/O means the atomic-promote/rollback story (try/except -> git checkout -- .) cannot reason about "did the decision run" separately from "did the write happen" |
| manifest.py's compute_manifest reads time.time() directly to stamp initialised_at | Pass the timestamp in as a parameter from the one impure edge that calls the clock | A pure function reading the clock directly can no longer be given a fixed timestamp in a test, so its output is no longer reproducible from its arguments |

## Scope

Applies to every module under `scripts/` and every module in the `lifecycle` container
(`init.py`, `upgrade.py`, `manifest.py`). Does not apply to `templates/*` (static content, no
logic to be pure or impure) or to `tests/*` test code itself (a test may set up fixtures with
real I/O; it is the code *under test* that must stay pure, not the test harness around it).

## Override

None. This is the owner's global pure-core rule (`~/.claude/rules/tribe/pure-core.md`), carried
into this library's own architecture without exception.
