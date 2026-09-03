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

## Next

Card T29 will run the baseline oracle against this migrated clone (before: ogp-wiki at
`f8b43fb`, its original scripts; after: this clone, now at `9933904`) and APPEND its verdict to
this same file.
