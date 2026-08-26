# Campaign constraints — wiki-harness-extraction

Every card in this campaign obeys this file in full. Read it before the spec and the plan.
It is referenced by every card's Global Constraints section rather than copied into each one.

## Where the real contract lives

The authoritative contract is NOT in this repository. It is:

- `/Users/hip/repo/wiki-harness-analysis/plan/plan-v3.md` — the plan of record, including
  appendix A8 through A11 at the end of the file.
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
   deltas: no new lint or card-lint findings on that migrated tree, the same output ordering,
   the same exit codes, the same commit-message verdicts. The vendored linters must find
   exactly what ogp-wiki's originals found on the same content. A HARNESS `manifest missing`
   ERROR from the new `lint.py` on a tree that has NOT adopted the harness is plan section 4.4's
   intended adoption signal, NOT a violation of this rule.
5. NEVER modify `/Users/hip/repo/ogp-wiki`, the live repository. Not one byte, in any card of
   this campaign. Reading it is allowed; writing to it is not.
6. Not in scope, do not build even if older notes mention them: an upgrade-in-progress marker
   file, a resume flag, a ci flag, any CI workflow, `ci_verify.py`, a LICENSE, a `tests/`
   directory in any wiki instance, per-enum descriptions in `card-schema.json`, an AGENTS.md
   back-parser. `CLAUDE.md` files are TRACKED and MANAGED, with the content `@AGENTS.md`.
7. Message strings quoted in a brief are verbatim contracts. Reproduce them byte for byte.
8. Commits: a conventional subject line; the trailers below as the final paragraph; NEVER a
   Co-Authored-By trailer of any kind.
9. Build nothing beyond the brief. Ambiguity is escalated, never guessed.

## Commit trailers

Every commit ends with this paragraph, with the task number the card's plan gives for that
task, out of the campaign's forty tasks:

```
Tribe-Card: wiki-harness-extraction
Tribe-Task: 21/40
Campaign: wiki-harness-extraction
```

## Branching and pull requests

- Card `P2-close` ships the existing `phase/p2` branch, which already carries seven merged
  tasks. Do not rebase it and do not rewrite its commits.
- Every card after `P2-close` cuts its branch from `main` and opens one pull request into
  `main`. The phase-branch convention ended with P2 — this is a Shaman ruling of 2026-08-26,
  taken because the campaign runner resolves the repository's default branch and would not
  otherwise be able to verify a card as shipped.
- Merge with a merge commit. Never squash and never rebase-merge.
- Push the branch as soon as the first commit exists, then keep pushing after every commit.
  Do not batch pushes to the end of a card.

## Audit roster — mandatory on every card

The owner ruled on 2026-08-26 that this campaign keeps the phase P1 and P2 bar:

- The implementation is written by a `hunter` subagent under strict test-driven development.
  The session orchestrating a card never writes the feature source itself.
- Every deliverable is audited by TWO INDEPENDENT `skinner` subagents that RUN the proof —
  the test suite, the acceptance commands — rather than reading claims. Do not collapse them
  into one. Give a skinner the diff and nothing else: a cold lens treats a note from the
  caller as contamination.
- A `tracker` subagent reviews the diff against every written rule source before the final
  commit of the card.
- A `scout` subagent surveys the touched code on the last card of each phase — `P2-close`,
  `C3-3`, and `T26` — and its rule candidates are reported, never silently adopted.

A finding is adjudicated before it is fixed. Where a card's plan or a brief states an
adjudication rule, that rule wins over a skinner's severity.

## Settled decisions — never reopened, never re-litigated

A1 through A7 and D1 through D8 of plan-v3, plus appendix A8 through A11, plus:

- A8: `manifest.py` lives at `scripts/manifest.py`, vendored MANAGED into every wiki next to
  the three linters. Never a second copy, never back at the repository root.
- A9: the scratch copy receives the new manifest BEFORE the step-10 lint; promote excludes the
  manifest; the real manifest is written last.
- A10: `extract_links` ignores fenced code blocks and inline code spans. The contract is the
  round-4 specification inside `T12b.md`: a fence only at three or fewer spaces of indent, no
  blockquote or list handling, an unclosed fence is not a fence, a span is single-line only.
  An under-check is CONFIRMED, an over-check is REFUTED. CommonMark is NOT the oracle.
- A11: `upgrade --check` honours the manifest precondition of plan-v3 section 3.2. A missing,
  unparseable, or non-object manifest exits 1 with ONE clear line on standard error, no
  traceback, and no remote round trip.
- The T11 fixture ruling: `main()` calls `check_harness` unconditionally, so a root with no
  manifest yields the `manifest missing` HARNESS error. The two phase-1 tests
  `test_cli_exit_zero_on_clean_tree` and `test_error_before_warn_in_printed_output` write an
  empty manifest in fixture setup; their assertions are unchanged. In scope, not a violation.
- Many commits per task is fine, as long as every commit carries the trailers above.
- A stale C3 row caused by a task's own code is REFUTED-as-scheduled when a C3 task is already
  scheduled in the same phase to reconcile it. C3-2 is that task for P2 and C3-3 for P3.
- "A single finding is CONFIRMED by default" applies ONLY where the brief contains no refuting
  sentence.

## Escalate, do not guess

Return the question upward rather than deciding it yourself when the answer would touch
`/Users/hip/repo/ogp-wiki`, change a sentence of the plan-v3 contract, add a dependency or a
permission, rewrite commits that were already audited, or delete or force-push a shared branch.
Anything else that the brief and this file do not settle is still a question, not a guess.
