---
id: adr-20260826-amend-verbatim-port-scope
c3-seal: 25990df9e35597109ac31697a4e47b1ca8d9e4b424c0ac82d435c4f78e788cf9
title: amend-verbatim-port-scope
type: adr
goal: |-
    Amend the frozen fact `ref-verbatim-port`'s Choice section so it keeps naming, byte-for-byte,
    the actual set of itemized fixes plan-v3 authorizes for the verbatim port of `scripts/*.py`,
    `.githooks/*`, and `tests/*.py`, and so it explicitly bounds what an audit pass during this
    phase may fix — after the Warchief's P1 whole-branch audit found and reverted two fix commits
    (root-relative link handling, list-item rule enforcement) that went beyond the ref's authorized
    scope, and added task T08b to fix a real defect T04 itself introduced (RULES_FILES parity is
    missing from the card-lint CLI's `main()` discovery, even though T08 already generalized
    `RULES_FILES` in `lint.py`).
status: accepted
date: "2026-08-26"
---

## Goal

Amend the frozen fact `ref-verbatim-port`'s Choice section so it keeps naming, byte-for-byte,
the actual set of itemized fixes plan-v3 authorizes for the verbatim port of `scripts/*.py`,
`.githooks/*`, and `tests/*.py`, and so it explicitly bounds what an audit pass during this
phase may fix — after the Warchief's P1 whole-branch audit found and reverted two fix commits
(root-relative link handling, list-item rule enforcement) that went beyond the ref's authorized
scope, and added task T08b to fix a real defect T04 itself introduced (RULES_FILES parity is
missing from the card-lint CLI's `main()` discovery, even though T08 already generalized
`RULES_FILES` in `lint.py`).

## Context

`ref-verbatim-port`'s Choice section currently reads: "applying only the specific, itemized
additive/prose fixes plan-v3 names by number — T03 ..., T04 ..., T08 ... — never a freehand
rewrite of the checks themselves." `docs/PLAN.md` now also tracks a new task, T08b (RULES_FILES
parity in the card-lint CLI discovery, `card_frontmatter_lint.py` `main()`), which the ref's
Choice text does not name — so the ref is stale the moment T08b lands, and any future reader
cannot tell from the fact alone that T08b was in-scope.

Separately, the whole-branch audit (commits `37302cb` fix(card-lint) and `8789f23`
fix(card-lint)) applied two fixes — resolving root-relative link targets and anchoring the
citation scan on both sides, plus list-item rule enforcement — that were not itemized by
plan-v3 and were not defects introduced by T03/T04/T08. Those two fixes touched behaviour
ogp-wiki's own current tree already exhibits byte-identically (an *inherited* defect, not a
port-introduced one), so landing them during the port would have violated the byte-identical
oracle this ref exists to protect. The Warchief reverted both (commit `723fbf8`
revert(card-lint)). The ref's Choice text authorizes only the *itemized* T03/T04/T08 fixes and
says nothing about the general *class* of audit-driven fix it does or does not permit, which is
exactly the gap that let an out-of-scope fix land in the first place.

The `scripts` container (`c3-1`) is the only topology this ref governs; no code file changes
with this ADR — this is a doc-only change-unit amending one frozen `ref` fact's Choice section.

## Decision

Amend `ref-verbatim-port`'s Choice section (single `block` patch, base
`ref-verbatim-port#n53@v1:sha256:a0a393912248d93783cf5a794b21fc2380f93c82a384123e8099e03da6304af9`)
to:

1. add T08b to the itemized list of authorized fixes, alongside T03/T04/T08, naming it as the
RULES_FILES-parity fix that T04 itself made necessary in the card-lint CLI's `main()`
discovery; and
2. state explicitly that audit-driven fixes in this phase are bounded to defects *introduced by
those itemized tasks* — a defect inherited byte-identical from ogp-wiki (e.g. the unanchored
citation scan's prefix-matching, list-item rule non-enforcement, `git diff HEAD` vs
`--cached` in `git_changes()`) is out of scope for the port and is tracked as a
post-migration hardening candidate, never fixed "freehand" during the port.

This is the smallest change that keeps the fact true: it does not relax the byte-identical
mandate, it only names the one task the Warchief already added (T08b) and writes down, as an
explicit rule rather than an implicit inference, the scope boundary the revert already enforced
in practice. The alternative — leaving the Choice text silent on the boundary — is rejected
because it is exactly the ambiguity that let the two out-of-scope audit fixes land before being
reverted; a silent ref cannot be checked against by the next audit pass.

## Affected Topology

| Entity | Type | Why affected | Evidence | Governance review |
| --- | --- | --- | --- | --- |
| ref-verbatim-port | N.A - ref (not system/container/component; the only fact this ADR mutates) | Its Choice section is the frozen text amended to name T08b and bound audit-driven fixes | ref-verbatim-port#n53@v1:sha256:a0a393912248d93783cf5a794b21fc2380f93c82a384123e8099e03da6304af9 "Fork scripts/lint.py, scripts/card_frontmatter_lint.py, scripts/check_commit_msg.py," | Amend via one block patch on the cited Choice node; landed 2026-08-26, verified below |

## Verification

| Check | Result |
| --- | --- |
| c3x read ref-verbatim-port --full, filtered through grep -c "T08b" | Must print a count ≥ 1 |
| c3x check | Must exit 0, no drift/canvas/orphan findings |
| python3 -m unittest discover -s tests -q | Must stay green (doc-only change; no code touched) |
