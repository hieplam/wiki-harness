# Spec — decision pages: a checked home for decision records

| Field | Value |
| --- | --- |
| Source issue | hieplam/wiki-harness#51 |
| Base | `main` @ 1ec59fd (v1.4.1) |
| Branch | `feat/decision-records` |
| Target release | 1.5.0 (MINOR), before the 2.0.0 in-host work of #46 |
| Plan | `docs/plans/decision-records.plan.md` |

## 1. Intent

A consumer wiki needs one place for **decision records**: why something is the way it is, what
was decided, which options lost, and whether the decision still holds. Today a decision is free
prose inside an ordinary page. A reader cannot list the decisions, cannot see which decision
replaced another, and cannot tell a decided fact from an open one.

The real case behind #51 (generic, as in the issue): a fix and its reason lived only in one agent
session's chat. A later commit undid the fix, the failure came back, and a second session had to
find the cause again. The owner of that wiki decided that the wiki is the single home for
decision records. The wiki needs a page type for them, and the harness has to ship it, because
`wiki/AGENTS.md` is MANAGED.

## 2. Goals, non-goals, anti-goals

Goals:

1. A consumer writes a **decision page**: an ordinary `wiki/` page with `kind: decision`. Lint
   checks its keys, its four required sections, and its replacement links.
2. A reader lists every decision and its status from one `## Decisions` section of `index.md`.
3. A replaced decision names the decision that replaced it, and lint checks both directions.
4. The recipes say where a decision, a lesson learnt, or an incident's fix is filed.
5. An existing ADR enters the wiki through the normal ingest: raw file, card, decision page.

Non-goals:

- No `incident` or `lesson` page kind. An incident or a lesson is the `## Context` of the
  decision it produced (owner decision).
- No `decisions/` folder. `wiki/` stays flat (owner decision).
- No ADR converter script. The agent maps an ADR with a table in `wiki/AGENTS.md` (owner
  decision).
- No generated decisions view file (owner decision: the view is a section of `index.md`).
- No migration of any consumer wiki's pages. That is the consumer's own `ingest`/`lint` work.

Anti-goals (a failure even if every test passes):

- **A wiki with no decision pages sees a different lint result.** Every new check runs only on
  pages that opt in with `kind: decision`. This is stricter than compatibility-policy §2
  requires for a MINOR release, on purpose.
- **A page that uses `kind`, `status` or `supersedes` for its own purpose gets a new
  finding.** Only `kind: decision` opts in.
- **Any consumer-specific name** in `scripts/`, `githooks/` or `templates/`
  (`tests/test_genericity.py`, `docs/neutrality-rubric.md`).

## 3. Constraints (quoted, not restated)

- `AGENTS.md` hard rules 1–6 bind every file. Rule 1: "Python 3.9, standard library only".
  Rule 2: "Every calculation, decision, and flow-control step is a pure function over
  already-collected data." Rule 3: "Edges fail closed."
- `AGENTS.md` hard rule 4: "`scripts/` and `githooks/` are a verbatim port. ... Change them only
  for a defect this library itself introduced." The precedent for a new feature is the gap
  ledger (commit `cada8d8`): a **new module** plus a short wiring in `scripts/lint.py`. Follow
  that precedent and keep the `lint.py` diff to the wiring.
- `docs/compatibility-policy.md` §2, MINOR column: "May add new finding codes and new checks ...
  May not change the meaning or wording of an existing code's message for content that already
  triggered it." And "May add new MANAGED/TEMPLATE paths".
- `AGENTS.md` "Changing a template": a MANAGED file "is overwritten byte-for-byte" on upgrade,
  and a TEMPLATE file "is re-rendered". SEEDED files are never written by `upgrade` (commit
  `cada8d8`: "upgrade never writes seeded paths"). So every rule that must reach an existing
  wiki goes into `templates/wiki.AGENTS.md` (MANAGED) or `templates/AGENTS.root.md.tmpl`
  (TEMPLATE). `templates/recipes.md` and `templates/index.md.header.tmpl` changes reach new
  wikis only.

## 4. The design (as decided)

### 4.1 Frontmatter keys

A page opts in with `kind: decision`. Without it, none of the keys below is checked, and
unknown keys keep parsing and being ignored.

| key | on a decision page | value |
| --- | --- | --- |
| `kind` | required to opt in | `decision`, compared case-insensitively. A list opts in when one item is `decision`. Any other value: not a decision page, no check. |
| `status` | **required** | exactly one of `proposed`, `decided`, `superseded` (case-sensitive, like the card `trust` enum) |
| `decided` | optional | `YYYY-MM-DD` when present. Omitted when the date is not known (a decision that holds today but was never written down). |
| `supersedes` | optional | one page name, or a list `[a, b]` |
| `superseded_by` | **required** when `status: superseded` | one page name, or a list |

A **page name** is the page's file name without `.md`: `widgets-ship-singly` for
`wiki/widgets-ship-singly.md`. A value that contains `/` or ends in `.md` is refused with a
message that names the correct value.

### 4.2 Required sections

Four level-2 headings, counted outside fenced code blocks, in any order. Extra sections are
allowed. A heading matches when its text, with surrounding space and closing `#`s removed,
internal space collapsed, and case folded, equals one of:

| heading | holds |
| --- | --- |
| `## Context` | what led to the record: an incident (a timeline is welcome), a lesson learnt, or a decision that holds today but was never written down |
| `## Decision` | what was decided, who decided, and why |
| `## Rejected options` | each option that lost, and why; `None considered.` is a valid body |
| `## Consequences` | what is true now because of the decision |

`### Context` (level 3) does not match. `## Decisions` does not match `## Decision`.

### 4.3 The `## Decisions` section of `index.md`

When at least one decision page exists, `index.md` has a level-2 heading whose text is
`Decisions` (case-insensitive). The section runs to the next level-1 or level-2 heading. Each
decision page has a list item there (`-`, `*`, `+`, `1.` or `1)`). An **entry** is a list item
at the section's outermost item indentation; its **first** link is the page it lists. A wrapped
line, a deeper (nested) item, and an indented line after a blank line continue the item: their
text counts toward the status word and their links are references. A line that belongs to no
item is prose and is ignored. The item states the page's `status` as a whole word,
case-insensitive (`Decided` counts), outside the text and target of every link. CRLF line ends
are read as LF before fences are found.

```markdown
## Decisions

- [Widgets ship in batches of ten](./wiki/widgets-ship-in-batches.md) — decided 2024-03-01 — batch size and why
- [Widgets ship singly](./wiki/widgets-ship-singly.md) — superseded by [batches of ten](./wiki/widgets-ship-in-batches.md)
```

The page also keeps its ordinary line under its topic heading (existing rule, not lint-checked
for topic grouping; `INDEX` keeps checking presence).

### 4.4 The `DECISION` finding code

One new code, severity `ERROR` for every message. `<p>`, `<a>`, `<x>` are page names; `<s>` is a
raw value as written. The messages are a contract from 1.5.0 on (policy §2), so use this
wording.

On the decision page itself:

| condition | message |
| --- | --- |
| `status` missing or empty | `missing required field 'status'` |
| `status` not in the set | `status '<s>' is not one of: proposed, decided, superseded` |
| `decided` present, not `^\d{4}-\d{2}-\d{2}$` | `decided '<s>' is not a YYYY-MM-DD date` |
| a section missing (one finding each, in table order of 4.2) | `missing required section '## Rejected options'` |
| a `supersedes` value with `/` or `.md` | `supersedes value '<s>' is not a page name; write '<stem>'` (`<stem>`: last path segment, `.md` removed) |
| the named page does not exist | `supersedes names '<x>', but wiki/<x>.md does not exist` |
| the named page exists but has no `kind: decision` | `supersedes names '<x>', but wiki/<x>.md is not a decision page` |

The three rows above apply to `superseded_by` with the key name changed in the message
(`superseded_by value '<s>' is not a page name; write '<stem>'`, `superseded_by names '<x>', …`).
A value that fails one of them takes no part in the rows below. "`superseded_by` empty" and
"not empty" in R1, R2 and P1 judge the key as written, so a refused value is not also reported
as a missing one. R3, P2, P3 and C1 use only the values that passed, and P2 needs at least one.

**Replacement rows.** Only a page whose own status is `decided` or `superseded` replaces
another page. A `proposed` page's `supersedes` is an intent: it is checked for shape and
existence (rows above) and nothing else, and the old page stays as it is. On one page, R1, R2
and P1 exclude each other, R2 and R3 exclude each other, and R1 and P2 exclude each other, so
one mistake on a page gives one finding on that page:

| # | condition (on page `<p>`) | message |
| --- | --- | --- |
| R1 | `status: superseded`, `superseded_by` empty | `status is 'superseded', but superseded_by is missing` |
| R2 | `status` is `proposed` or `decided`, `superseded_by` not empty | `superseded_by is set, but status is '<s>', not 'superseded'` |
| R3 | `status: superseded`, `superseded_by` names `<a>`, and `<a>`'s status is `proposed` | `superseded_by names '<a>', but wiki/<a>.md is still 'proposed'` |
| P1 | a replacing page `<a>` lists `<p>` in `supersedes`; `<p>` is `proposed` or `decided` with `superseded_by` empty | `wiki/<a>.md supersedes this page, but status is '<s>' and superseded_by is missing` |
| P2 | a replacing page `<a>` lists `<p>` in `supersedes`; `<p>` is `superseded` and its non-empty `superseded_by` does not name `<a>` | `wiki/<a>.md supersedes this page, but superseded_by does not name '<a>'` |
| P3 | (reported on `<x>`) `<p>` is `superseded`, its `superseded_by` names `<x>`, `<x>` is `decided` or `superseded`, and `<x>`'s `supersedes` does not name `<p>` | `wiki/<p>.md is superseded_by '<x>', but supersedes here does not name '<p>'` |
| C1 | following `superseded_by` from `<p>` returns to `<p>` | `supersedes chain loops back to this page: <p> -> <x> -> <p>` |

A page whose `status` is missing or not in the set gets only its status finding: R1–R3, P1, P2
and C1 skip it, and P3 skips a pair where `<p>` has such a status. Every other combination
(for example `superseded` with a `superseded_by` that names `<a>`, while `<a>` supersedes it)
is consistent and gives nothing. When one wrong name leaves it unclear which of two pages is
wrong (P2 on one page, P3 on the other), both pages get a finding.

On `index.md`:

| condition | message |
| --- | --- |
| decision pages exist, no `## Decisions` section | `no '## Decisions' section, but decision pages exist` |
| a decision page has no entry in the section | `decision page not listed under '## Decisions': wiki/<p>.md` |
| an entry's line does not state the page's valid status | `'## Decisions' lists wiki/<p>.md without its status '<s>'` |
| an entry points at an existing page that is not a decision page | `'## Decisions' lists wiki/<p>.md, which is not a decision page` |

An entry that points at a page that does not exist is left to the existing `INDEX` check.

### 4.5 Where the code goes

- New MANAGED module `scripts/decision_lint.py`, pure only: `check_decisions(files, ...)` takes
  the same `files` dict as every `check_*` in `lint.py` and returns `Finding`s. It needs
  `lint.py`'s fence stripping and link extraction, and `lint.py` imports it, so it receives
  those functions as arguments instead of importing them (no circular import, no second fence
  parser). Its docstring lists the pure functions (hard rule 2).
- `scripts/lint.py`: import the module and add the call to `run()`. Nothing else changes.
- `init.py`'s `copy_scripts()` and `upgrade.py` discover `scripts/*.py` from disk, and
  `tools/build_release.py` ships `scripts/`, so no list changes there. A test proves the module
  reaches a fresh wiki.

### 4.6 Template text

`templates/wiki.AGENTS.md` (MANAGED, reaches every wiki):

- The frontmatter table gains the keys of 4.1. The sentence "No optional keys are defined for
  wiki pages yet." is replaced by: the optional keys apply when `kind: decision`; unknown keys
  still parse and are ignored.
- A new section "Decision pages": when to write one (an incident and its fix, a lesson learnt
  written as the rule the team now follows, a decision that holds today but was never written
  down); one decision per page; the four sections; a generic example; how to replace a decision
  (new page with `supersedes`, old page gets `status: superseded` and `superseded_by` and keeps
  its text as history, index line changes to `superseded`). A `proposed` page may name the page
  it intends to replace; the old page changes only when the new one is `decided`. A decision
  that stops holding with no successor is replaced by a decision to stop: write that page and
  supersede the old one. The status set has no fourth value for this.
- A subsection "Importing an ADR": store the file in `sources/raw/`, write a card with
  `origin: adr` (if `sources/cards/card-schema.json` does not list `adr` in its `origin` enum,
  add it first, in a `schema:` commit), file one decision page per decision. Mapping:

  | ADR part | decision page |
  | --- | --- |
  | context, problem, decision drivers | `## Context` |
  | decision, chosen option | `## Decision` |
  | alternatives considered, considered options | `## Rejected options` |
  | consequences, risks, costs | `## Consequences` |
  | status accepted, implemented, done | `status: decided` |
  | status proposed, open, in progress | `status: proposed` |
  | status superseded | `status: superseded` with `superseded_by` |

  An ADR whose proposal was rejected, withdrawn or abandoned records a decision not to do it:
  file it as `status: decided`, with the rejection as its `## Decision`. A deprecated ADR with
  no successor: import it, then write the decision to stop and supersede it. Import a superseded
  ADR only together with the ADR that replaced it. Leave out parts that only serve the ADR's
  own tool (content seals, tool commands); the raw file keeps them. `init`'s default origins
  and `templates/card-schema.default.json` do not change.
- The "Index" section gains the `## Decisions` rule of 4.3.

`templates/AGENTS.root.md.tmpl` (TEMPLATE, re-rendered on upgrade):

- Ingest step 3: a decision, a lesson learnt, or the fix an incident produced goes to a
  decision page.
- Ingest step 4: a decision page also gets a line under `## Decisions`, with its status.
- Query step 1: for "why is it like this?", start at `## Decisions`.
- The Lint workflow's list of mechanical checks names decision pages.

`templates/recipes.md` (SEEDED, new wikis only):

- `session` row: `Verified findings, decisions made, lessons learnt, gotchas discovered`.
- New row `adr`: context, decision, rejected options, consequences, status, supersedes; filed
  as described in `wiki/AGENTS.md` "Importing an ADR" (plain text, not a link).
- Lines 21-22 become: "All recipes emit the SAME contract: a card with claims, filed into wiki
  pages. A recipe never invents its own page shape: it files into a page kind that
  `wiki/AGENTS.md` defines. A decision, a lesson learnt, or the fix an incident produced goes
  to a decision page."

`templates/index.md.header.tmpl` (SEEDED): one sentence saying decision pages are also listed
under `## Decisions` with their status.

`README.md` (library, not shipped): the `wiki/` line of the layout tree mentions decision pages.

## 5. Tests

Write each test first and watch it fail.

1. **Unit, `tests/test_decision_lint.py`**: every message row of 4.4, each from a minimal
   `files` dict, asserting the **complete** finding list (so a second finding for the same
   mistake fails the test). Plus: a `proposed` page with `supersedes` leaves a `decided` old page
   without finding; a consistent pair gives nothing; a page with an invalid status gives only
   its status finding. Plus: no decision page → no finding and no `## Decisions` required; a page
   with `kind: runbook`, `status: draft`, `supersedes: x` and no `kind: decision` → no finding;
   `kind: Decision` opts in; a heading inside a fenced block does not count; heading spelling
   variants of 4.2 match (`## Rejected Options`, `##  Rejected options  `, `## Rejected options ##`);
   `### Context` does not.
2. **Value shapes (fixtures mirror reality)**: `supersedes` written as `old`, `[old]`,
   `[old, other]`, `old.md`, `./old.md`, `wiki/old.md`, `../wiki/old.md`. The first three pass;
   the rest give the "is not a page name; write 'old'" message.
3. **Fresh wiki, end to end**: `init.py` into an empty temp directory (subprocess, isolated git),
   then add a card, a decision page, a page that supersedes it, both index lines, and run the
   **vendored** `scripts/lint.py` there: exit 0, no `DECISION`. Then remove a required section:
   the finding appears. Then point `supersedes` at a missing page: the finding appears.
4. **Existing wiki unchanged**: `check_decisions` on `tests/fixtures/sample-wiki` returns
   nothing, and the full `lint.run()` output on that fixture contains no `DECISION`. During
   implementation, also run v1.4.1's `scripts/lint.py` (from `git show v1.4.1:…` into a temp
   folder) and this branch's against the same no-decision wiki trees and diff the outputs;
   record the empty diff in the PR. This one-time check is evidence, not a test, because the
   suite must not depend on tags being fetched.
5. **Upgrade**: an existing upgrade test path (or a new one beside it) shows that `upgrade` to
   this version writes `scripts/decision_lint.py` and the new `wiki/AGENTS.md`, and that
   post-upgrade lint on a wiki without decision pages passes.
6. **Templates and genericity**: `tests/test_genericity.py` passes unchanged. The existing
   `tests/test_templates.py` constant that pins the per-origin recipes table changes with the
   table, because this plan changes that table on purpose. Add a template test that
   `wiki.AGENTS.md` names `kind: decision`, the four sections and `## Decisions`.

`./run_tests.sh` passes before the PR opens.

## 6. Release and records

- PR title (the squash subject, which decides the release): `feat(wiki): add decision pages
  with status and supersedes checks` → MINOR. No `BREAKING CHANGE` footer: nothing is removed
  or repurposed.
- PR body states the policy reason: new finding code and new checks (§2 MINOR), new MANAGED
  path `scripts/decision_lint.py`, MANAGED `wiki/AGENTS.md` and TEMPLATE `AGENTS.md` change on
  upgrade, SEEDED `recipes.md` and `index.md` change for new wikis only.
- `CHANGELOG.md` is generated by release-please (policy §8). It is not edited by hand.
- `.c3/` is not changed in this PR: the model fails `c3x check` (#49). The PR says which facts
  are now stale, for #49 to pick up.

## 7. Left to the builder

- Function names and the split of `decision_lint.py` into helpers.
- The exact prose of the template sections, inside the content listed in 4.6. Keep the
  existing voice of `wiki.AGENTS.md`: short, imperative, with a generic `widget` example.
- The order in which findings are emitted (lint sorts them before printing).
- How cycle paths are walked, provided the result is deterministic for the same input.
