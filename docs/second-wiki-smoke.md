# Second-wiki smoke — T31

Evidence record for card T31 (`wiki-harness-migration`). Amendment A12: this card's product
is a throwaway `/tmp` fixture and creates no tracked file on its own, so this record states
each command that was run verbatim, what was observed, and the verdict. It is a record, not
a new requirement — the brief's acceptance commands remain the only gate.

Both fixtures (`/tmp/ai-wiki-smoke`, `/tmp/ai-wiki-custom`) are throwaway: created fresh under
`/tmp`, never committed anywhere permanent, never pushed to a real remote, and removed after
this smoke ran.

## Version under test

```
$ cat /Users/hip/repo/wiki-harness/VERSION
1.0.1
$ git -C /Users/hip/repo/wiki-harness log --oneline -1
2e43199 Merge pull request #20 from hieplam/task/T31A-init-relative-target
```

Library HEAD sha (full): `2e43199c9b52d9180be417833a591944e2b1b6ef`.

v1.0.1 carries the T31A fix (`init.py`'s `dry_run_hooks` now resolves git-hook program paths
to absolute), so the acceptance command's **relative** target (`ai-wiki-smoke`, not an
absolute path) is expected to succeed here, per ruling R4.

## Half A — default schema (`/tmp/ai-wiki-smoke`)

### 1. Init from a relative target (the T31A fix)

```
$ rm -rf /tmp/ai-wiki-smoke
$ cd /tmp && python3 /Users/hip/repo/wiki-harness/init.py ai-wiki-smoke --wiki-title 'AI Wiki' --org-name 'AI tribe' --content-language English --repo-name ai-wiki --non-interactive
```
Observed:
```
lint: 0 error(s), 0 warning(s)

Scaffolded ai-wiki-smoke -- lint clean, .githooks wired, first commit d14c3c72245b.
Next: start ingesting -- see AGENTS.md's Workflow: Ingest.
Note: commits authored via the GitHub API or a cloud coding agent structurally bypass every local hook this scaffold just wired up; wiki-harness v1.0.0 ships no mitigation for that class of commit at all.
```
Exit code: `0`.

**Verdict:** PASS — a relative init target no longer crashes; the T31A fix holds.

### 2. Lint the fresh fixture

```
$ cd /tmp/ai-wiki-smoke && python3 scripts/lint.py
```
Observed:
```
lint: 0 error(s), 0 warning(s)
```
Exit code: `0`.

**Verdict:** PASS — lint clean, 0 errors, 0 warnings on the freshly scaffolded fixture.

### 3. No `tests/` directory (A6)

```
$ test ! -d /tmp/ai-wiki-smoke/tests && echo "A6-OK: no tests/ dir"
```
Observed:
```
A6-OK: no tests/ dir
```

**Verdict:** PASS — A6 holds: no `tests/` directory in the wiki instance.

### 4. Synthetic ingest, committed through the real hooks

Added `sources/cards/src-2026-09-02-001.md` (id `src-2026-09-02-001`, date `2026-09-02`,
`origin: session`, `trust: stated`, `topics: [smoke-test]`, a `## Claims` bullet),
`wiki/smoke-test.md` (frontmatter `title` + `topics`, citing the card as the relative link
`../sources/cards/src-2026-09-02-001.md`), and an `index.md` entry under a new `## smoke-test`
topic heading linking to `./wiki/smoke-test.md`.

```
$ cd /tmp/ai-wiki-smoke && python3 scripts/lint.py
```
Observed:
```
WARN ORPHAN wiki/smoke-test.md: no inbound links from other wiki pages
lint: 0 error(s), 1 warning(s)
```
Exit code: `0` (0 errors; ORPHAN is a WARN-only finding, which is fine — lint exits 0 on
warnings).

```
$ cd /tmp/ai-wiki-smoke && git add -A && git commit -m "ingest(src-2026-09-02-001): synthetic smoke card"
```
Observed:
```
WARN ORPHAN wiki/smoke-test.md: no inbound links from other wiki pages
lint: 0 error(s), 1 warning(s)
[main 7f7fcc5] ingest(src-2026-09-02-001): synthetic smoke card
 3 files changed, 22 insertions(+)
 create mode 100644 sources/cards/src-2026-09-02-001.md
 create mode 100644 wiki/smoke-test.md
```
Exit code: `0`.

**Verdict:** PASS — the pre-commit lint hook ran and passed (0 errors), the commit-msg hook
accepted the `ingest(src-2026-09-02-001)` subject as a valid card-id ref, and the commit was
created.

### 5. Deliberately broken commit, blocked as expected

```
$ cd /tmp/ai-wiki-smoke && git commit --allow-empty -m "ingest(not-a-valid-id): should be blocked"
```
Observed:
```
WARN ORPHAN wiki/smoke-test.md: no inbound links from other wiki pages
lint: 0 error(s), 1 warning(s)
commit-msg: ingest commits require ref = card id, e.g. 'ingest(src-2026-08-06-001): summary'
```
Exit code: `1`.

```
$ git log --oneline -1
7f7fcc5 ingest(src-2026-09-02-001): synthetic smoke card
```
(unchanged from before the blocked attempt — no commit was created.)

**Verdict:** PASS — the commit-msg hook blocked the malformed `ingest` ref with the verbatim
message, non-zero exit, and no commit was created.

## Half B — customized `id.pattern` (`/tmp/ai-wiki-custom`)

A separate, fresh fixture, so the schema switch is clean (switching the pattern in a fixture
that already holds `src-` cards would retroactively break their own citations/id-validation —
expected library behaviour, not a bug — so a fresh fixture is the faithful
"configured-for-ai-from-the-start" proof).

### 1. Init the second fixture

```
$ rm -rf /tmp/ai-wiki-custom
$ cd /tmp && python3 /Users/hip/repo/wiki-harness/init.py ai-wiki-custom --wiki-title 'AI Wiki Custom' --org-name 'AI tribe' --content-language English --repo-name ai-wiki-custom --non-interactive
```
Observed:
```
lint: 0 error(s), 0 warning(s)

Scaffolded ai-wiki-custom -- lint clean, .githooks wired, first commit ce7902f5b33a.
Next: start ingesting -- see AGENTS.md's Workflow: Ingest.
Note: commits authored via the GitHub API or a cloud coding agent structurally bypass every local hook this scaffold just wired up; wiki-harness v1.0.0 ships no mitigation for that class of commit at all.
```
Exit code: `0`.

**Verdict:** PASS.

### 2. Customize `card-schema.json`'s `id.pattern`, commit as a `schema:` op

Edited ONLY `sources/cards/card-schema.json` — the `id` key's `pattern` changed from
`^src-\d{4}-\d{2}-\d{2}-\d{3}$` to `^ai-\d{4}-\d{2}-\d{2}-\d{3}$`. No `scripts/*.py`
(library code) touched.

```
$ cd /tmp/ai-wiki-custom && python3 scripts/lint.py
```
Observed:
```
lint: 0 error(s), 0 warning(s)
```
Exit code: `0` (lint clean — no cards exist yet).

```
$ cd /tmp/ai-wiki-custom && git add sources/cards/card-schema.json && git commit -m "schema: switch card id.pattern to ai- shape"
```
Observed:
```
lint: 0 error(s), 0 warning(s)
[main 773e9b4] schema: switch card id.pattern to ai- shape
 1 file changed, 1 insertion(+), 1 deletion(-)
```
Exit code: `0`.

**Verdict:** PASS.

### 3. Synthetic ingest with an `ai-`-shaped id

Added `sources/cards/ai-2026-09-02-001.md` (id `ai-2026-09-02-001`, date `2026-09-02`,
`origin: session`, `trust: stated`, `topics: [smoke-test]`, a `## Claims` bullet),
`wiki/smoke-test.md` citing it as `../sources/cards/ai-2026-09-02-001.md`, and an `index.md`
entry under `## smoke-test`.

```
$ cd /tmp/ai-wiki-custom && python3 scripts/lint.py
```
Observed:
```
WARN ORPHAN wiki/smoke-test.md: no inbound links from other wiki pages
lint: 0 error(s), 1 warning(s)
```
Exit code: `0`.

```
$ cd /tmp/ai-wiki-custom && git add -A && git commit -m "ingest(ai-2026-09-02-001): custom-id-shape smoke card"
```
Observed:
```
WARN ORPHAN wiki/smoke-test.md: no inbound links from other wiki pages
lint: 0 error(s), 1 warning(s)
[main 6f32d97] ingest(ai-2026-09-02-001): custom-id-shape smoke card
 3 files changed, 22 insertions(+)
 create mode 100644 sources/cards/ai-2026-09-02-001.md
 create mode 100644 wiki/smoke-test.md
```
Exit code: `0`.

**Verdict:** PASS — lint's citation scan (CITE/UNFILED) and the commit-msg hook both honored
the customized `^ai-\d{4}-\d{2}-\d{2}-\d{3}$` id.pattern with an `ai-`-shaped card and citation,
proving the schema-driven card-id mechanism honors a differently-configured second wiki with
ZERO library-code change. This is the direct proof that agent-bypass #1's original finding — a
hardcoded `src-` prefix would permanently block a differently-configured second wiki — is fixed.

### 4. Old `src-` shape is rejected under the customized pattern

```
$ cd /tmp/ai-wiki-custom && git commit --allow-empty -m "ingest(src-2026-09-02-001): should now be blocked"
```
Observed:
```
WARN ORPHAN wiki/smoke-test.md: no inbound links from other wiki pages
lint: 0 error(s), 1 warning(s)
commit-msg: ingest commits require ref = card id, e.g. 'ingest(src-2026-08-06-001): summary'
```
Exit code: `1`.

```
$ git log --oneline -1
6f32d97 ingest(ai-2026-09-02-001): custom-id-shape smoke card
```
(unchanged — no commit was created.)

**Verdict:** PASS — the `src-` shaped ref, which was valid under the default schema, is
correctly rejected once the fixture's own schema declares the `ai-` shape as the id.pattern.

### 5. No `tests/` directory (A6)

```
$ test ! -d /tmp/ai-wiki-custom/tests && echo "A6-OK: no tests/ dir"
```
Observed:
```
A6-OK: no tests/ dir
```

**Verdict:** PASS.

### 6. Zero library-code change

```
$ git -C /Users/hip/repo/wiki-harness status --short
```
Observed: (empty output) — exit `0`.

```
$ diff -r /Users/hip/repo/wiki-harness/scripts /tmp/ai-wiki-custom/scripts
```
Observed: (empty output, no differences) — exit `0`.

**Verdict:** PASS — the library's own working tree is untouched, and the fixture's vendored
`scripts/` are byte-identical to the library's. The customized-`id.pattern` half of this smoke
required editing only `sources/cards/card-schema.json` inside the fixture; no `scripts/*.py`
change of any kind.

## Full library test suite (from the library root)

```
$ cd /Users/hip/repo/wiki-harness && python3 -m unittest discover -s tests -q ; echo "EXIT=$?"
```
Observed (tail; the lines before `EXIT=0` are stdout from subprocess-driving tests that exercise
`upgrade.py`/`init.py` end-to-end against their own scratch fixtures, not test failures):
```
upgrade --check: remote 'https://example.invalid/repo.git' is unreachable
----------------------------------------------------------------------
Ran 251 tests in 82.673s

OK
lint: 0 error(s), 0 warning(s)

Scaffolded relative-wiki -- lint clean, .githooks wired, first commit 2e8d13456c61.
Next: start ingesting -- see AGENTS.md's Workflow: Ingest.
Note: commits authored via the GitHub API or a cloud coding agent structurally bypass every local hook this scaffold just wired up; wiki-harness v1.0.0 ships no mitigation for that class of commit at all.
upgrade: dry run against v1.1.0 -- no files written.
The following managed/template path(s) would change:
  wiki/AGENTS.md
Pass --apply to write these changes.
upgrade: suggested commit message: chore: upgrade wiki-harness v1.0.0 -> v1.1.0
already at v1.0.0
EXIT=0
```

**Verdict:** PASS — the full suite stays green.

## Closing verdict

The second-wiki E2E smoke PASSED on both halves: `init.py` scaffolds a lint-clean,
hook-enforced, `tests/`-free (A6) wiki from a relative target (v1.0.1, T31A fix confirmed);
a synthetic ingest commits cleanly through the real pre-commit and commit-msg hooks; a
malformed `ingest` ref is blocked as expected; and the schema-driven card-id mechanism
honors a fully customized `^ai-\d{4}-\d{2}-\d{2}-\d{3}$` id.pattern end-to-end (citation scan,
UNFILED/CITE checks, and the commit-msg hook) with zero library-code change, while the
previously-valid `src-` shape is correctly rejected once the fixture's own schema no longer
declares it. Both fixtures were created under `/tmp`, never committed anywhere permanent, and
removed after this smoke ran.
