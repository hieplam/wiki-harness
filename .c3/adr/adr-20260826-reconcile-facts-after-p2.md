---
id: adr-20260826-reconcile-facts-after-p2
c3-seal: 1c53d00778001b9c82528e3265e57a45dc87c3c062e3403257fccdb9992c5efa
title: reconcile-facts-after-p2
type: adr
goal: |-
    Reconcile six frozen facts — `c3-101` (lint-core), `c3-201` (manifest), `ref-ownership-classes`,
    `ref-verbatim-port`, `c3-102` (card-lint), `c3-103` (commit-msg-lint) — with the code phase P1/P2
    actually shipped: T04's schema-driven card-id mechanism, T09's `manifest.py`, T11's HARNESS
    eighth edge in `lint.py`, T12b/amendment A10's fenced-code/inline-code link stripping, T08b's
    RULES_FILES CLI-discovery parity, and Warchief amendment A8 (`manifest.py` vendored at
    `scripts/manifest.py`, not the repository root). No code, template, or test changes; this is a
    doc-only change-unit that makes each row's wording match the shipped surfaces.
status: accepted
date: "2026-08-26"
---

## Goal

Reconcile six frozen facts — `c3-101` (lint-core), `c3-201` (manifest), `ref-ownership-classes`,
`ref-verbatim-port`, `c3-102` (card-lint), `c3-103` (commit-msg-lint) — with the code phase P1/P2
actually shipped: T04's schema-driven card-id mechanism, T09's `manifest.py`, T11's HARNESS
eighth edge in `lint.py`, T12b/amendment A10's fenced-code/inline-code link stripping, T08b's
RULES_FILES CLI-discovery parity, and Warchief amendment A8 (`manifest.py` vendored at
`scripts/manifest.py`, not the repository root). No code, template, or test changes; this is a
doc-only change-unit that makes each row's wording match the shipped surfaces.

## Context

Facts were frozen at C3 onboarding (P0.2) against a pre-T04/pre-T09/pre-T11 mental model of the
`scripts` and `lifecycle` containers. Since then:

- T04 made the card-id shape schema-driven (`card_id_pattern_from_schema`,
`card_id_scan_pattern`, `DEFAULT_CARD_ID_PATTERN`), which `c3-101`, `c3-102`, and `c3-103` now
import/export, but `c3-101`'s Parent Fit still says "Nothing inside c3-1" for Depends on, and
`c3-102`'s Contract still describes a `load_schema(text) -> dict` that "raises on malformed
JSON" — the real surface (verified by reading `scripts/card_frontmatter_lint.py`) is
`load_schema(text) -> tuple[dict | None, list[Finding]]`, fails closed, never raises.
- T09 shipped `manifest.py`'s pure `compute_manifest`/`diff_manifest` plus a thin I/O edge, and
Warchief amendment A8 settled that it vendors at `scripts/manifest.py` in every wiki instance,
next to the three linters — not at the repository root. `c3-201`'s Purpose and Derived
Materials rows, and `ref-ownership-classes`'s prose, still say bare `manifest.py`.
- T11 added `lint.py`'s eighth impure edge — `check_harness(manifest_state) -> list[Finding]`
(pure) and `read_harness_manifest(root) -> ManifestState | ManifestMalformed | None` (impure),
reading `scripts/manifest.py`'s `read_manifest`/`hash_tree`/`is_valid_role` — but `c3-101`'s
Parent Fit, Governance, Derived Materials, and Contract sections say nothing about it, and
`c3-201` is not named as a dependency at all.
- T12b (amendment A10) made `extract_links` ignore fenced code blocks and inline code spans, a
plan-sanctioned delta proven byte-identical on ogp-wiki, not yet named in `c3-101`'s Governance
row or `ref-verbatim-port`'s Choice section (which C3-1 already amended for T08b but predates
T11/A10).
- T08's `RULES_FILES` and T08b's CLI-discovery parity fix are sanctioned per `ref-verbatim-port`
(amended by C3-1) but `c3-101`'s own Governance and Derived Materials rows still read "T03/T04/
T08 fixes only" / "T03/T04/T08", one task behind that ref.

Every row named above was read live through the C3 wrapper (`read <id> --full`, `--section
--cite`) and cross-checked against the actual on-disk surfaces in this worktree
(`scripts/lint.py`, `scripts/card_frontmatter_lint.py`, `scripts/check_commit_msg.py`,
`scripts/manifest.py`) before drafting any patch, per the campaign's standing rule 10: a stale C3
row caused by a task's own code is REFUTED-as-scheduled when a C3 task is already scheduled in
the same phase to reconcile it — C3-2 is that task for P2.

## Decision

Land one change-unit with a `block` or `insert` patch per stale row (twelve patches total across
the six facts), each carrying the corrected wording verified against the live code:

1. `c3-101` Parent Fit "Depends on" → name both `c3-102` (nine imported names) and `c3-201` (the
HARNESS edge's manifest data path).
2. `c3-101` Governance row for `ref-verbatim-port` → add T08b/T11/A10 to the sanctioned-delta
list.
3. `c3-101` Derived Materials row for `scripts/lint.py` → add T08b/T11/A10 to the allowed
variance.
4. `c3-101` Contract → add two rows: `check_harness` and `read_harness_manifest`.
5. `c3-201` Purpose → name `scripts/manifest.py` and A8's vendoring rationale.
6. `c3-201` Derived Materials → `wiki-harness/manifest.py` becomes `wiki-harness/scripts/
manifest.py`.
7. `ref-ownership-classes` → its two bare `manifest.py` mentions (Why, How) become
`scripts/manifest.py`, matching A8 and the identical rename already applied in item 6 —
confirmed by `read --full` that no table row enumerating "the three linters + hooks +
AGENTS/CLAUDE" exists in this ref to add a path to; the only path-bearing content here is
these two `manifest.py` mentions.
8. `ref-verbatim-port` Choice → append one sentence distinguishing plan-sanctioned additions
(T08's `RULES_FILES`, T11's §4.4 edge, A10) from audit-driven fixes.
9. `c3-102` Contract `load_schema` row → the real `tuple[dict | None, list[Finding]]`,
fails-closed surface, replacing "raises on malformed JSON".
10. `c3-102` Parent Fit "Depended on by" → the accurate nine-name `c3-101` import list plus
`c3-103`'s four-name import list.
11. `c3-103` Contract `validate` row → the real `card_id_pattern` parameter.
12. `c3-103` Contract `main` row → the real `argv: list[str]` signature and its two reads
(schema, then message file).

This is the smallest change that makes every named row true again: no code changes, no row not
named above is touched, and every corrected row is verified by re-reading the live source before
being written into the patch. The alternative — deferring reconciliation to a later phase —
already failed once (P0.2's own acknowledged, expected drift note) and would let the facts keep
describing surfaces that no longer exist, which defeats their purpose as an architecture ground
truth.

## Affected Topology

| Entity | Type | Why affected | Evidence | Governance review |
| --- | --- | --- | --- | --- |
| c3-101 | component | Parent Fit/Governance/Derived Materials/Contract rows describe pre-T09/T11/A10 surfaces | c3-101#n106@v1:sha256:e9f19aa97b4d42dffebe103bc3619ad397e6f950865a108bccb86c8e47347d91 | Reconcile via block/insert patches; no ref/rule text changes |
| c3-201 | component | Purpose/Derived Materials name bare manifest.py instead of A8's scripts/manifest.py | c3-201#n226@v1:sha256:00b5f776dc925cc74401f48093fab286cc0cd23522142dfcc19c64e6dabd88c2 | Reconcile via block patches; A8 already settled, no new decision |
| ref-ownership-classes | N.A - ref (not system/container/component) | Two prose mentions of bare manifest.py predate A8's vendoring location | ref-ownership-classes@v1:sha256:669cadf08edac92e3a3ca1d544ead96e78df50aa85138a5b99ed93cffac2488e | Reconcile via block patches on Why/How |
| ref-verbatim-port | N.A - ref (not system/container/component) | Choice section (already amended by C3-1 for T08b) predates T11/A10 | ref-verbatim-port#n484@v1:sha256:c1ccc7f4faa7ce32f0a3ef9193ed1e92c013ea51f9469029690b25dbb6116974 | Append one sentence naming T11/A10 as sanctioned additions |
| c3-102 | component | Contract's load_schema row and Parent Fit's import lists describe a pre-T04/T11 surface | c3-102#n148@v1:sha256:8408bea7947baae1136d807e4e368ff50e51d85b87b5721804cec6a4685be86e | Reconcile via block patches; P1 scout finding |
| c3-103 | component | Contract's validate/main rows predate T04's card_id_pattern parameter | c3-103#n173@v1:sha256:d96f0b20739cd71a905bbe3f5e370f80fc13bcf520ac499e6a3bd78e2b5fc501 | Reconcile via block patches; P1 scout finding |

## Verification

| Check | Result |
| --- | --- |
| c3x read c3-101 --full piped through grep -q 'check_harness', 'c3-201', 'A10' | Each must exit 0 |
| c3x read c3-201 --full | grep -q 'scripts/manifest.py' |
| c3x read ref-ownership-classes --full | grep -q 'scripts/manifest.py' |
| c3x read ref-verbatim-port --full piped through grep -q 'T11', 'A10' | Each must exit 0 |
| c3x read c3-102 --full | grep -c 'raises on malformed JSON' |
| c3x read c3-102 --full | grep -q 'fails closed' |
| c3x read c3-103 --full piped through grep -q 'card_id_pattern: str', 'main(argv: list\[str\]) -> int' | Each must exit 0 |
| c3x check | Must exit 0, ok: true (stale-anchor warnings acceptable) |
| python3 -m unittest discover -s tests -q | Must stay green (doc-only change; no code touched) |
