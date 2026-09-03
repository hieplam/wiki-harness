# Migration record — ogp-wiki clone

Evidence record for the ogp-wiki migration (`wiki-harness-migration` campaign). Amendment A12:
cards T28 and T29 land their product OUTSIDE this repository — T28 in the disposable
`ogp-wiki-clone`, T29 in the analysis directory's `baseline/after/` — so this record captures
the migration as it happens, with the verbatim commands and the observed result. It is a
record, not a new requirement — no card's scope, acceptance commands, or definition of done
changes because of it; the brief's acceptance commands remain the only gate.

## Clone under migration

- Path: `/Users/hip/repo/wiki-harness-analysis/ogp-wiki-clone`
- Branch: `master`
- This is a SEPARATE, disposable git repository. The live wiki at `/Users/hip/repo/ogp-wiki`
  is never touched by this migration — not one byte.

### T27 — `--adopt` result

T27 ran wiki-harness's `--adopt` migration against the clone (explicit `--wiki-title`,
`--org-name`, `--content-language`, `--repo-name` flags, no back-parser), producing the commit
`d4ae5f3 chore: adopt wiki-harness v1.0.0`.

```
$ git -C /Users/hip/repo/wiki-harness-analysis/ogp-wiki-clone show --stat --format="%H %s" d4ae5f3
```
Observed:
```
d4ae5f32b42bd34d0bbe5a53eb90bb31cee6a8c7 chore: adopt wiki-harness v1.0.0

 .gitignore                       |   1 -
 .wiki-harness-manifest.json      |  76 +++++++++
 AGENTS.md                        |  29 +++-
 CLAUDE.md                        |   1 +
 README.md                        |   7 +-
 scripts/card_frontmatter_lint.py | 142 ++++++++++++++++-
 scripts/check_commit_msg.py      |  46 +++++-
 scripts/lint.py                  | 329 +++++++++++++++++++++++++++++++++++++--
 scripts/manifest.py              | 164 +++++++++++++++++++
 sources/AGENTS.md                |   2 +-
 sources/CLAUDE.md                |   1 +
 sources/cards/AGENTS.md          |  35 ++---
 sources/cards/CLAUDE.md          |   1 +
 sources/cards/recipes.md         |  22 +++
 wiki/AGENTS.md                   |   8 +-
 wiki/CLAUDE.md                   |   1 +
 16 files changed, 803 insertions(+), 62 deletions(-)
```

The commit created `.wiki-harness-manifest.json` (self-consistent, records
`harness_version: 1.0.0`, `source_ref: v1.0.0`, the adoption `vars`, and a per-file
role/sha256 table), vendored `scripts/manifest.py` (new, MANAGED) and rewrote the existing
`scripts/lint.py`, `scripts/card_frontmatter_lint.py`, `scripts/check_commit_msg.py` in place,
added a `CLAUDE.md` (`@AGENTS.md`) alongside every tracked `AGENTS.md`, added
`sources/cards/recipes.md`, and wired `core.hooksPath=.githooks` so the vendored hooks run on
every commit from that point on.

```
$ git -C /Users/hip/repo/wiki-harness-analysis/ogp-wiki-clone config core.hooksPath
```
Observed:
```
.githooks
```

## T28 — `tests/` deleted (A6)

No wiki instance ever carries a `tests/` directory — the library owns every test, permanently
(A6). This step deletes `tests/` from the clone outright.

### Precondition

```
$ cd /Users/hip/repo/wiki-harness-analysis/ogp-wiki-clone && ls tests/
```
Observed:
```
test_card_frontmatter_lint.py
test_commit_msg.py
test_lint_checks.py
test_lint_cli.py
test_lint_parsing.py
```

### Deletion

```
$ git rm -r tests/
```
Observed:
```
rm 'tests/test_card_frontmatter_lint.py'
rm 'tests/test_commit_msg.py'
rm 'tests/test_lint_checks.py'
rm 'tests/test_lint_cli.py'
rm 'tests/test_lint_parsing.py'
```

### Commit

Per the clone's `AGENTS.md` commit table, `chore` is the correct op for "Scripts, repo infra".

```
$ git commit -m "chore: delete tests/ -- library owns all tests (A6)"
```
Observed:
```
lint: 0 error(s), 0 warning(s)
[master 9933904] chore: delete tests/ -- library owns all tests (A6)
 5 files changed, 698 deletions(-)
 delete mode 100644 tests/test_card_frontmatter_lint.py
 delete mode 100644 tests/test_commit_msg.py
 delete mode 100644 tests/test_lint_checks.py
 delete mode 100644 tests/test_lint_cli.py
 delete mode 100644 tests/test_lint_parsing.py
```

The vendored `.githooks/commit-msg` hook (wired via `core.hooksPath`) ran and accepted the
subject; the vendored `pre-commit` hook ran `lint.py` and reported it clean.

### Postcondition

```
$ test ! -d tests && echo "PASS: tests/ absent"
```
Observed:
```
PASS: tests/ absent
```

```
$ ls tests/
```
Observed:
```
ls: tests/: No such file or directory
```
Exit code: `1` (non-zero, as expected for a missing directory).

### Resulting commit

```
$ git rev-parse HEAD
```
Observed:
```
9933904621a3d5da64eb1e9ccb6772aa28fd7373
```

```
$ git log -1 --format=%s
```
Observed:
```
chore: delete tests/ -- library owns all tests (A6)
```

## T29 — Baseline oracle verdict (R5 gate)

This verdict supersedes the old R1 "3 deltas" framing. Per Shaman ruling R5 (owner-ratified
2026-09-03, restated in plan-v3 appendix A13), the migrated clone PASSES if and only if BOTH
hold: (A) every differing file between `before/` and `after/` is attributable to exactly one of
five pre-ratified causes C1–C5, and (B) `card-lint/*` and `commit-msg/*` (the corpora that
measure ogp-wiki's own real content) are byte-identical.

### Acceptance command 1 — capture `after/`

```
$ TEST_CMD='echo "tests/ removed by migration - all wiki-harness tests now live in the wiki-harness library repo"; exit 0' bash /Users/hip/repo/wiki-harness-analysis/baseline/run.sh /Users/hip/repo/wiki-harness-analysis/ogp-wiki-clone /Users/hip/repo/wiki-harness-analysis/baseline/after
```
Observed:
```
baseline: repo=/Users/hip/repo/wiki-harness-analysis/ogp-wiki-clone lint_exit=0 tests_exit=0 corpus_lines=54 scenarios=37 matched_expectation=36/37 out=/Users/hip/repo/wiki-harness-analysis/baseline/after
```
`matched_expectation=36/37` is expected: scenario 32 flips `allowed`→`blocked` under C4 below (the
`before/` capture was 37/37). `tests_exit=0` and `lint_exit=0` both hold on the `after/` side.

### Acceptance command 2 — inspection diff (non-zero exit is EXPECTED)

```
$ diff -r --exclude=env.txt /Users/hip/repo/wiki-harness-analysis/baseline/before /Users/hip/repo/wiki-harness-analysis/baseline/after
```
Exit code: `1` — expected and correct. This is an inspection, not an exit-code gate: two of the
five causes (C4, C5) are real content differences by design (the manifest drift check firing, and
the canonical `AGENTS.md` link set differing from the hand-written original).

Enumeration of every differing file:
```
$ diff -rq --exclude=env.txt /Users/hip/repo/wiki-harness-analysis/baseline/before /Users/hip/repo/wiki-harness-analysis/baseline/after
```
Observed (36 lines, one per differing file):
```
Files .../before/lint/exit.txt and .../after/lint/exit.txt differ
Files .../before/lint/stdout.txt and .../after/lint/stdout.txt differ
Files .../before/scenarios/01-lint-broken-link.result.txt and .../after/scenarios/01-lint-broken-link.result.txt differ
Files .../before/scenarios/02-lint-citation-missing-card.result.txt and .../after/scenarios/02-lint-citation-missing-card.result.txt differ
Files .../before/scenarios/03-lint-card-unfiled.result.txt and .../after/scenarios/03-lint-card-unfiled.result.txt differ
Files .../before/scenarios/04-lint-fm-missing-title.result.txt and .../after/scenarios/04-lint-fm-missing-title.result.txt differ
Files .../before/scenarios/05-lint-fm-missing-topics.result.txt and .../after/scenarios/05-lint-fm-missing-topics.result.txt differ
Files .../before/scenarios/06-lint-fm-unclosed-block.result.txt and .../after/scenarios/06-lint-fm-unclosed-block.result.txt differ
Files .../before/scenarios/07-lint-index-missing-entry.result.txt and .../after/scenarios/07-lint-index-missing-entry.result.txt differ
Files .../before/scenarios/08-lint-index-ghost-entry.result.txt and .../after/scenarios/08-lint-index-ghost-entry.result.txt differ
Files .../before/scenarios/09-lint-index-file-missing.result.txt and .../after/scenarios/09-lint-index-file-missing.result.txt differ
Files .../before/scenarios/10-lint-raw-modify.result.txt and .../after/scenarios/10-lint-raw-modify.result.txt differ
Files .../before/scenarios/11-lint-raw-rename.result.txt and .../after/scenarios/11-lint-raw-rename.result.txt differ
Files .../before/scenarios/12-lint-encoding-invalid-utf8.result.txt and .../after/scenarios/12-lint-encoding-invalid-utf8.result.txt differ
Files .../before/scenarios/13-lint-card-schema-invalid-json.result.txt and .../after/scenarios/13-lint-card-schema-invalid-json.result.txt differ
Files .../before/scenarios/14-lint-card-schema-missing-file.result.txt and .../after/scenarios/14-lint-card-schema-missing-file.result.txt differ
Files .../before/scenarios/15-lint-card-fm-parse-error.result.txt and .../after/scenarios/15-lint-card-fm-parse-error.result.txt differ
Files .../before/scenarios/16-lint-card-key-unknown.result.txt and .../after/scenarios/16-lint-card-key-unknown.result.txt differ
Files .../before/scenarios/17-lint-card-key-missing-required.result.txt and .../after/scenarios/17-lint-card-key-missing-required.result.txt differ
Files .../before/scenarios/18-lint-card-value-bad-enum.result.txt and .../after/scenarios/18-lint-card-value-bad-enum.result.txt differ
Files .../before/scenarios/19-lint-card-value-bad-pattern.result.txt and .../after/scenarios/19-lint-card-value-bad-pattern.result.txt differ
Files .../before/scenarios/20-lint-card-value-list-required.result.txt and .../after/scenarios/20-lint-card-value-list-required.result.txt differ
Files .../before/scenarios/21-lint-card-value-list-not-allowed.result.txt and .../after/scenarios/21-lint-card-value-list-not-allowed.result.txt differ
Files .../before/scenarios/22-lint-card-ref-matches-filename.result.txt and .../after/scenarios/22-lint-card-ref-matches-filename.result.txt differ
Files .../before/scenarios/23-lint-card-ref-missing-raw-path.result.txt and .../after/scenarios/23-lint-card-ref-missing-raw-path.result.txt differ
Files .../before/scenarios/24-lint-card-ref-missing-parent-card.result.txt and .../after/scenarios/24-lint-card-ref-missing-parent-card.result.txt differ
Files .../before/scenarios/26-commitmsg-bad-op.result.txt and .../after/scenarios/26-commitmsg-bad-op.result.txt differ
Files .../before/scenarios/27-commitmsg-ingest-missing-ref.result.txt and .../after/scenarios/27-commitmsg-ingest-missing-ref.result.txt differ
Files .../before/scenarios/28-commitmsg-ingest-bad-ref-format.result.txt and .../after/scenarios/28-commitmsg-ingest-bad-ref-format.result.txt differ
Files .../before/scenarios/29-commitmsg-two-card-ids.result.txt and .../after/scenarios/29-commitmsg-two-card-ids.result.txt differ
Files .../before/scenarios/30-commitmsg-empty-message.result.txt and .../after/scenarios/30-commitmsg-empty-message.result.txt differ
Files .../before/scenarios/31-commitmsg-comment-only-message.result.txt and .../after/scenarios/31-commitmsg-comment-only-message.result.txt differ
Files .../before/scenarios/32-commitmsg-comment-lines-ignored.result.txt and .../after/scenarios/32-commitmsg-comment-lines-ignored.result.txt differ
Files .../before/scenarios/SUMMARY.tsv and .../after/scenarios/SUMMARY.tsv differ
Files .../before/tests/stderr.txt and .../after/tests/stderr.txt differ
Files .../before/tests/stdout.txt and .../after/tests/stdout.txt differ
```

**Count: 36 differing files, 5 causes, 0 unclassified.** No file was unattributable.

### Attribution by cause

**C1 — capture's own HEAD moved** (`f8b43fb`→`9933904`, the migration commits). Only the
`POST_LOG:` line in each scenario result differs; no finding/verdict/exit-code changes. 22 files:
`scenarios/01-lint-broken-link.result.txt`, `02-lint-citation-missing-card.result.txt`,
`03-lint-card-unfiled.result.txt`, `04-lint-fm-missing-title.result.txt`,
`05-lint-fm-missing-topics.result.txt`, `06-lint-fm-unclosed-block.result.txt`,
`07-lint-index-missing-entry.result.txt`, `08-lint-index-ghost-entry.result.txt`,
`09-lint-index-file-missing.result.txt`, `10-lint-raw-modify.result.txt`,
`11-lint-raw-rename.result.txt`, `13-lint-card-schema-invalid-json.result.txt`,
`15-lint-card-fm-parse-error.result.txt`, `16-lint-card-key-unknown.result.txt`,
`17-lint-card-key-missing-required.result.txt`, `18-lint-card-value-bad-enum.result.txt`,
`19-lint-card-value-bad-pattern.result.txt`, `20-lint-card-value-list-required.result.txt`,
`21-lint-card-value-list-not-allowed.result.txt`, `22-lint-card-ref-matches-filename.result.txt`,
`23-lint-card-ref-missing-raw-path.result.txt`, `24-lint-card-ref-missing-parent-card.result.txt`
(all under `scenarios/`).

**C2 — `--adopt` set `core.hooksPath`**, so the HOOKS error no longer fires (an error is REMOVED,
never added). 2 files: `lint/exit.txt` (`1`→`0`), `lint/stdout.txt` (the
`ERROR HOOKS .githooks: commit hook not active` line and the error count both drop to
`lint: 0 error(s), 0 warning(s)`).

**C3 — `tests/` deleted (A6)**, so the fixed `TEST_CMD` override line replaces unittest's own
output; `tests/exit.txt` stays `0` on both sides (confirmed byte-identical). 2 files:
`tests/stdout.txt` (unittest's `Ran 82 tests … OK` output → the override echo line),
`tests/stderr.txt` (before held 93 lines of unittest progress on stderr → now empty).

**C4 — scenario edits `README.md` as fixture; migration made `README.md` harness-MANAGED**, so
the manifest drift check correctly fires (`ERROR HARNESS README.md: local edit conflicts with
library-managed content …`); in scenario 32 it blocks the commit before the commit-msg rule is
reached, flipping that row `allowed`→`blocked` (`ACTUAL`, `MATCH`, `COMMIT_EXIT_CODE`,
`COMMITTED` all change accordingly). 8 files: `scenarios/26-commitmsg-bad-op.result.txt`,
`27-commitmsg-ingest-missing-ref.result.txt`, `28-commitmsg-ingest-bad-ref-format.result.txt`,
`29-commitmsg-two-card-ids.result.txt`, `30-commitmsg-empty-message.result.txt`,
`31-commitmsg-comment-only-message.result.txt`, `32-commitmsg-comment-lines-ignored.result.txt`,
`scenarios/SUMMARY.tsv`.

**C5 — `--adopt` installed canonical `AGENTS.md`/`sources/cards/AGENTS.md`** whose link
set/multiplicity differ from ogp-wiki's hand-written pages: scenario 14 gains a SECOND copy of an
already-firing error (canonical `sources/cards/AGENTS.md` names `./card-schema.json` twice,
`5 error(s)`→`6 error(s)`); scenario 12 LOSES an error (canonical `AGENTS.md` has no
`./wiki/pay-run.md` example link, `5 error(s)`→`4 error(s)`). 2 files:
`scenarios/12-lint-encoding-invalid-utf8.result.txt`,
`scenarios/14-lint-card-schema-missing-file.result.txt`.

Tally: C1 22 + C2 2 + C3 2 + C4 8 + C5 2 = **36**, matching the enumerated diff exactly. Zero
files remained unclassified.

### Gate (B) — `card-lint/*` and `commit-msg/*` are byte-identical

```
$ diff -rq /Users/hip/repo/wiki-harness-analysis/baseline/before/card-lint /Users/hip/repo/wiki-harness-analysis/baseline/after/card-lint
```
Observed: (no output, exit code `0`)

```
$ diff -rq /Users/hip/repo/wiki-harness-analysis/baseline/before/commit-msg /Users/hip/repo/wiki-harness-analysis/baseline/after/commit-msg
```
Observed: (no output, exit code `0`)

Both corpora — which measure ogp-wiki's own real, unmutated content — are byte-identical between
`before/` and `after/`. No new finding appears on ogp-wiki's real content anywhere in the capture.

### Verdict

**PASS.** Both R5 gate conditions hold: (A) all 36 differing files are attributable to exactly one
of C1–C5, 0 unclassified; (B) `card-lint/*` and `commit-msg/*` are byte-identical. The migrated
clone at `9933904` matches the pre-migration behavior of ogp-wiki at `f8b43fb` up to the five
ratified, expected causes.

## Next

Card T30 will take this migration to PR review and merge it into the real `ogp-wiki` repository.
