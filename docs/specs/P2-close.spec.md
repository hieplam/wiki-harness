# Spec — card `P2-close`

**Campaign:** wiki-harness-extraction | **Phase:** P2 — Templates / init | **Depends on:** none

## What this card delivers

Close phase P2: T15's A11 amendment, the C3-2 fact reconcile, and the P2 pull request.

This spec is a thin pointer, not a restatement. The requirement contract for every task below
is its brief, listed with the task. Read the brief in full, including any trailing section
headed "Warchief amendment", before writing a line of code.

## Tasks in this card

1. **T15** — T15 — close amendment A11 on `upgrade --check`
   - Brief (the real contract): `/Users/hip/repo/wiki-harness-analysis/plan/briefs/T15.md`
   - Task branch: `task/T15-upgrade-check`
   - Campaign task number: 21 of 40
2. **C3-2** — C3-2 — reconcile the frozen C3 facts with what P1 and P2 actually shipped
   - Brief (the real contract): `/Users/hip/repo/wiki-harness-analysis/plan/briefs/C3-2.md`
   - Task branch: `task/C3-2-reconcile-facts`
   - Campaign task number: 22 of 40

## Scope fence

- Only the tasks listed above may produce a change. Nothing else in the repository is touched.
- `/Users/hip/repo/ogp-wiki`, the live wiki, is never written to. Not one byte.
- No CI workflow file is created, in this card or any other.
- Build nothing beyond the brief; escalate an ambiguity instead of guessing at it.
- This card ships the WHOLE of phase P2 to `main` in one pull request, exactly as phases P0 and P1 shipped (pull requests 1 and 2). Its branch already exists and already carries seven merged tasks (T09, T10, T11, T12, T12b, T13, T14) — never rebase it, never rewrite those commits, never open a second branch for this card.

## Governing constraints

`docs/plans/CAMPAIGN-CONSTRAINTS.md` applies in full: the nine standing rules, the commit trailers, the
branching and pull-request convention, the mandatory audit roster of one hunter, two
independent skinners and one tracker, and the settled decisions that are never reopened.

## Definition of done

Every acceptance command in this card's plan exits 0 when re-run in a fresh shell, both
skinners report no confirmed gating finding, the tracker approves the diff, the pull request
into `main` is merged, and `docs/PLAN.md` carries this card's tasks ticked.
