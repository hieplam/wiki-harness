---
id: adr-20260826-complete-verbatim-port-precedence-cell
c3-seal: dde8b4d6b04b2e81a52f439d512db0493f0a5dc4108362d31ffe22ba880da982
title: complete-verbatim-port-precedence-cell
type: adr
goal: |-
    Fix the self-contradiction in c3-101's Governance table row for `ref-verbatim-port`: the
    Precedence cell still reads "T03/T04/T08 are the only sanctioned deltas" while the same row's
    Governs cell already lists T08b, the plan-sanctioned §4.4 HARNESS eighth edge (T11), and
    amendment A10 as additional sanctioned deltas. Correct ONLY the Precedence cell so it names the
    same expanded sanctioned-delta set as the Governs cell. No code changes.
status: accepted
date: "2026-08-26"
---

## Goal

Fix the self-contradiction in c3-101's Governance table row for `ref-verbatim-port`: the
Precedence cell still reads "T03/T04/T08 are the only sanctioned deltas" while the same row's
Governs cell already lists T08b, the plan-sanctioned §4.4 HARNESS eighth edge (T11), and
amendment A10 as additional sanctioned deltas. Correct ONLY the Precedence cell so it names the
same expanded sanctioned-delta set as the Governs cell. No code changes.

## Context

The C3-2 reconciliation commit (`a9f2c68`, "docs(c3): reconcile c3-101/c3-201/c3-102/c3-103 and
both refs with T04/T09/T11 + A8") expanded c3-101's `ref-verbatim-port` Governance row's Governs
cell to correctly name T08b, the §4.4 HARNESS edge (T11), and amendment A10 (T12b) as sanctioned
deltas on top of T03/T04/T08 — but left the same row's Precedence cell unchanged, still asserting
"T03/T04/T08 are the only sanctioned deltas". This makes the single Governance row internally
contradictory: one cell says the sanctioned-delta set is T03/T04/T08/T08b/T11/A10, the adjacent
cell in the same row says it is only T03/T04/T08. `ref-verbatim-port` itself (the underlying ref
fact) already documents the wider T11/A10 deltas, so the Precedence cell is the only place still
out of sync. This unit touches only that one table cell in one fact; it does not open code, ADRs
about code, or any other row/section.

## Decision

Author a single `block`-scope patch against c3-101's Governance table row for `ref-verbatim-port`
(anchor `c3-101#n115`) that replaces only the Precedence cell's text so it names the SAME
expanded sanctioned-delta set the Governs cell already names — T03/T04/T08/T08b plus the §4.4
HARNESS edge (T11) and A10 — while leaving the Reference, Type, Governs, and Notes cells of that
row byte-identical to their current content. This is the minimal fix: it removes the
contradiction without altering the correct (already-expanded) Governs cell, the entity cell, or
the Rationale/Notes cell, and without touching any other fact, row, or the underlying
`ref-verbatim-port` ref fact.

## Affected Topology

| Entity | Type | Why affected | Evidence | Governance review |
| --- | --- | --- | --- | --- |
| c3-101 | component | Its Governance table's ref-verbatim-port row has a Precedence cell that contradicts the same row's Governs cell; this unit corrects the Precedence cell only | c3-101#n115@v1:sha256:16e367c41aad3963a4a96be25adce839adb3acba338b0cb88cca940dfa83cce1 "ref-verbatim-port" | Confirm the patched Precedence cell matches the Governs cell's sanctioned-delta set and no other cell/row/section changed |

## Verification

| Check | Result |
| --- | --- |
| c3x read c3-101 --full | grep -c 'are the only sanctioned deltas' |
| c3x read c3-101 --full | grep -q 'A10' |
| c3x check (unscoped) | Must report ok: true |
