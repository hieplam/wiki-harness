---
allowsSchemaChange: true
---

# Plan — card `P2-close`

Thin plan. The buildable detail for each task lives in that task's brief, named in the task
section below; this file exists so the campaign runner and `validate-plan.sh` have a
mechanically well-formed plan, and so the acceptance commands are in one place. Do not restate
a brief here and do not treat this file as a substitute for reading one.

## Global Constraints

The implementer is the `hunter` subagent. Dispatch one hunter subagent per task and never
write the feature source in the orchestrating session itself. Every deliverable is then
audited by two independent `skinner` subagents that run the proof, and the diff is reviewed by
a `tracker` subagent before the card's final commit.

Purity: core logic stays deterministic and free of side effects; every outside-world
dependency — the filesystem, a subprocess, the network, the clock, randomness, global state —
enters through a named edge the caller supplies, and is never constructed inside a decision
function. See `~/.claude/rules/pure-core.md`.

All nine standing rules, the commit trailers, the branching and pull-request convention, the
audit roster and the settled decisions are in `docs/plans/CAMPAIGN-CONSTRAINTS.md`. That file governs this plan
and every task in it.

### Task 1: T15 — close amendment A11 on `upgrade --check`

Requirement contract: `/Users/hip/repo/wiki-harness-analysis/plan/briefs/T15.md` — read it in full, including any trailing section headed
"Warchief amendment". Work on branch `task/T15-upgrade-check`, following the branching convention in the
campaign constraints file.

The branch `task/T15-upgrade-check` already carries four audited commits (`bde7e48`, `d318a07`, `837e630`, `4ef962a`). Keep them. Add exactly one new commit that closes the brief's trailing amendment section, then merge that branch into `phase/p2` with a `merge(T15):` subject and push both branches. The `docs/PLAN.md` box for T15 is already ticked; leave it alone.

Adjudication rule for this task's audits: a finding that `--check` exits 1 for a missing, unparseable, or non-object manifest is REFUTED by clarification A11. A finding that it does so WITH a traceback, WITHOUT a clear message, or AFTER contacting the remote is CONFIRMED.

Acceptance commands, run verbatim in a fresh shell:

```sh
cd /Users/hip/repo/wiki-harness && python3 -m unittest discover -s tests -q
cd /Users/hip/repo/wiki-harness && python3 -m unittest tests.test_upgrade.TestCheck -v
```

Expected: every command above exits 0, and the full suite
(`python3 -m unittest discover -s tests -q` from the repository root) stays green. Re-run all
of them yourself before claiming the task is done.

- [ ] **Step 1: Commit** — one or more conventional commits, each ending with the three
      trailers from the campaign constraints file, using `Tribe-Task: 21/40`, and
      never a Co-Authored-By trailer. Tick only this task's own `docs/PLAN.md` box, in the
      same commit as the code.

### Task 2: C3-2 — reconcile the frozen C3 facts with what P1 and P2 actually shipped

Requirement contract: `/Users/hip/repo/wiki-harness-analysis/plan/briefs/C3-2.md` — read it in full, including any trailing section headed
"Warchief amendment". Work on branch `task/C3-2-reconcile-facts`, following the branching convention in the
campaign constraints file.

This task is governance work driven entirely through the C3 wrapper. The brief's own header names a general-purpose agent; that is superseded by a Shaman ruling: dispatch a `hunter` subagent instead, and equip it in its brief with the C3 procedure. The hunter drives `C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh` and may READ the C3 skill's own reference docs from disk (in particular `references/change.md` next to that binary). It must never hand-edit a `.c3/` fact file, never run `c3x repair`, and must stop and report the CLI's refusal verbatim if the CLI refuses at any step.

Branch off `phase/p2` only after task 1 has merged into it. Merge back with a `merge(C3-2):` subject and push. This task adds its own new line to `docs/PLAN.md`, ticked, in the same commit, as the LAST line of the `## P2 — Templates / init` section.

Acceptance commands, run verbatim in a fresh shell:

```sh
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read c3-101 --full | grep -q 'check_harness'
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read c3-101 --full | grep -q 'c3-201'
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read c3-201 --full | grep -q 'scripts/manifest.py'
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read ref-ownership-classes --full | grep -q 'scripts/manifest.py'
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read ref-verbatim-port --full | grep -q 'T11'
cd /Users/hip/repo/wiki-harness && test "$(C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read c3-102 --full | grep -c 'raises on malformed JSON')" = 0
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read c3-102 --full | grep -q 'fails closed'
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read c3-103 --full | grep -q 'card_id_pattern: str'
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh read c3-103 --full | grep -q 'main(argv: list\[str\]) -> int'
cd /Users/hip/repo/wiki-harness && C3X_MODE=agent bash /Users/hip/.claude/plugins/cache/c3-skill-marketplace/c3-skill/11.6.3/skills/c3/bin/c3x.sh check
cd /Users/hip/repo/wiki-harness && python3 -m unittest discover -s tests -q
```

Expected: every command above exits 0, and the full suite
(`python3 -m unittest discover -s tests -q` from the repository root) stays green. Re-run all
of them yourself before claiming the task is done.

- [ ] **Step 2: Commit** — one or more conventional commits, each ending with the three
      trailers from the campaign constraints file, using `Tribe-Task: 22/40`, and
      never a Co-Authored-By trailer. Tick only this task's own `docs/PLAN.md` box, in the
      same commit as the code.
