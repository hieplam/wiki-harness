# Campaign constraints — wiki-harness-migration

Every card in this campaign obeys this file in full. Read it before the spec and the plan.
It is referenced by every card's Global Constraints section rather than copied into each one.

This is the SECOND campaign on this repository. The first, `wiki-harness-extraction`, built
the library and ended at T26 (ruling R5) with v1.0.0 tagged. This campaign migrates the live
wiki onto that release and proves a second wiki can be created from it.

## Where the real contract lives

The authoritative contract is NOT in this repository. It is:

- `/Users/hip/repo/wiki-harness-analysis/plan/plan-v3.md` — the plan of record, including
  appendix A8 through **A12** at the end of the file. A12 is this campaign's own amendment
  and is owner-ratified; read it.
- `/Users/hip/repo/wiki-harness-analysis/plan/briefs/` — one self-contained brief per task.
  Several briefs carry trailing sections headed "Warchief amendment". Those sections are
  binding. Read every brief to its last line.
- `docs/PLAN.md` in this repository — the checklist. Each task's hunter ticks its OWN box in
  the SAME commit as the code, and nobody else's box.

The `docs/specs/` and `docs/plans/` files in this repository are thin pointers generated for
the campaign runner. They never override a brief. Where a pointer and a brief disagree, the
brief wins, except where this file or a card's own plan explicitly records a Shaman ruling.

## Standing rules (all nine apply to every card)

1. C3: the repo's architecture model lives in `.c3/` — read facts via the wrapper; never
   hand-edit `.c3/` facts (only `.c3/eval/*.yaml` bindings); an architectural fact change
   requires a change-unit — if your task needs one, STOP and report it upward.
2. Pure core, impure edges (`~/.claude/rules/pure-core.md`): decisions never do input or
   output directly; input and output enter through a named edge the caller supplies.
3. Python 3.9 floor, standard library only, no pyproject and no setup.py,
   `from __future__ import annotations` in every Python module.
4. Byte-identical behaviour for ogp-wiki's CONTENT (plan-v3 section 6(e)): the baseline oracle
   at `/Users/hip/repo/wiki-harness-analysis/baseline` compares before (ogp-wiki at `f8b43fb`,
   its ORIGINAL scripts) with after (the MIGRATED clone: vendored scripts, a self-consistent
   `.wiki-harness-manifest.json`, and `core.hooksPath`) — an empty diff modulo the three named
   deltas. Card T29 is where this rule is actually adjudicated; its plan carries ruling R1,
   which states exactly what the diff may contain.
5. NEVER modify `/Users/hip/repo/ogp-wiki`, the live repository. Not one byte, in any card of
   this campaign. Reading it is allowed; writing to it is not. **T30, the one task that does
   write to it, is deliberately NOT in this campaign** — it is manual and owner-gated, because
   a runner session self-merges its own pull request (ruling R6 of the previous campaign) and
   would bypass the owner-reads-the-diff rule on the single most irreversible task in the plan.
6. Not in scope, do not build even if older notes mention them: an upgrade-in-progress marker
   file, a resume flag, a ci flag, any CI workflow, `ci_verify.py`, a LICENSE, a `tests/`
   directory in any wiki instance, per-enum descriptions in `card-schema.json`, an AGENTS.md
   back-parser. `CLAUDE.md` files are TRACKED and MANAGED, with the content `@AGENTS.md`.
7. Message strings quoted in a brief are verbatim contracts. Reproduce them byte for byte.
8. Commits: a conventional subject line; the trailers below as the final paragraph; NEVER a
   Co-Authored-By trailer of any kind.
9. Build nothing beyond the brief. Ambiguity is escalated, never guessed.

## Amendment A12 — the evidence record

Three of this campaign's four cards do work whose product lands OUTSIDE this repository: T28
in a disposable ogp-wiki clone, T29 in the analysis directory's `baseline/after/`, T31 in a
throwaway `/tmp` fixture. The campaign runner only marks a card shipped on a merged pull
request in this repository, so each of those three additionally commits a short evidence
record:

| Card | Evidence record | What it does |
|---|---|---|
| T31 | `docs/second-wiki-smoke.md` | creates it |
| T28 | `docs/migration-record.md` | creates it |
| T29 | `docs/migration-record.md` | appends the oracle verdict |

An evidence record states what was run (verbatim commands), what was observed, and the
verdict. It is a RECORD, not a new requirement — no card's scope, acceptance commands, or
definition of done changes because of it, and a card is never "done" because its record reads
well. T27 needs no record: it writes library code, which is already a pull request.

## Commit trailers

Every commit ends with this paragraph, with the task number the card's plan gives for that
task, out of this campaign's four tasks:

```
Tribe-Card: wiki-harness-migration
Tribe-Task: 1/4
Campaign: wiki-harness-migration
```

## Branching and pull requests

- Every card cuts its branch from `main` and opens one pull request into `main`.
- Merge with a merge commit. Never squash and never rebase-merge.
- Push the branch as soon as the first commit exists, then keep pushing after every commit.
  Do not batch pushes to the end of a card.

## Audit roster — mandatory on every card

This campaign keeps the bar the previous one held:

- The implementation is written by a `hunter` subagent under strict test-driven development.
  The session orchestrating a card never writes the feature source itself.
- Every deliverable is audited by TWO INDEPENDENT `skinner` subagents that RUN the proof —
  the test suite, the acceptance commands — rather than reading claims. Do not collapse them
  into one. Give a skinner the diff and nothing else: a cold lens treats a note from the
  caller as contamination.
- A `tracker` subagent reviews the diff against every written rule source before the final
  commit of the card.
- A `scout` subagent surveys the touched code on the last card of each phase — `T31` for P5,
  `T29` for P4 — and its rule candidates are reported, never silently adopted.

A finding is adjudicated before it is fixed. Where a card's plan or a brief states an
adjudication rule, that rule wins over a skinner's severity.

## Adjudication rules carried over from the previous campaign

- A stale C3 row caused by a task's own code is REFUTED-as-scheduled only when a C3 task is
  already scheduled to reconcile it. **This campaign schedules no C3 card**, so a C3 fact this
  campaign's code genuinely falsifies is a real finding: STOP and report it upward as needing
  a change-unit, rather than fixing the fact by hand or waving it through.
- "A single finding is CONFIRMED by default" applies ONLY where the brief contains no refuting
  sentence.
- Inherited defects — behaviour ported verbatim from ogp-wiki that this campaign did not
  introduce — are REFUTED as out-of-scope and recorded as hardening candidates, never fixed
  mid-card. The standing list is in the previous campaign's record.
- Many commits per task is fine, as long as every commit carries the trailers above.

## Settled decisions — never reopened, never re-litigated

A1 through A7 and D1 through D8 of plan-v3, plus appendix A8 through A12. In particular:

- A2: the trust table's per-value meanings are NOT folded into `card-schema.json`. The table
  moves into `recipes.md` verbatim and `card-schema.json`'s `trust` key keeps exactly the one
  key-level description string it has today.
- A5: `--adopt` takes the four template variables as explicit flags. There is no back-parser.
- A6: no wiki instance ever carries a `tests/` directory.
- A8: `manifest.py` lives at `scripts/manifest.py`, vendored MANAGED into every wiki.
- A12: the evidence record, above.

## Escalate, do not guess

Return the question upward rather than deciding it yourself when the answer would touch
`/Users/hip/repo/ogp-wiki`, change a sentence of the plan-v3 contract, add a dependency or a
permission, rewrite commits that were already audited, or delete or force-push a shared branch.
Anything else that the brief and this file do not settle is still a question, not a guess.
