---
id: adr-20260826-stabilize-table-cell-escaping
c3-seal: 7a3c923b32a86b70bfb27fd7c4c531477ea42f3760505ce9c5323a8abc1b2d58
title: stabilize-table-cell-escaping
type: adr
goal: |-
    Stabilize the canonical markdown for the 9 onboarding facts (`c3-101`, `c3-102`, `c3-103`,
    `c3-201`, `c3-210`, `c3-211`, `c3-410`, `c3-411`, `rule-stdlib-only-py39`) whose table cells put
    `from __future__ import annotations` (and, for `c3-101`'s `scan(root)` Contract row, the globs
    `wiki/**/*.md` and `sources/cards/*.md`) in un-backticked prose, so that `c3x check`'s canonical
    markdown round-trip stops reporting `content_mismatch` for these files — without changing what
    any row asserts.
status: accepted
date: "2026-08-26"
---

## Goal

Stabilize the canonical markdown for the 9 onboarding facts (`c3-101`, `c3-102`, `c3-103`,
`c3-201`, `c3-210`, `c3-211`, `c3-410`, `c3-411`, `rule-stdlib-only-py39`) whose table cells put
`from __future__ import annotations` (and, for `c3-101`'s `scan(root)` Contract row, the globs
`wiki/**/*.md` and `sources/cards/*.md`) in un-backticked prose, so that `c3x check`'s canonical
markdown round-trip stops reporting `content_mismatch` for these files — without changing what
any row asserts.

## Context

`c3x check` fails with `error: sync check failed: canonical markdown drift detected` and lists
`content_mismatch` for exactly these 9 files. The root cause (verified by reading each fact with
`c3x read <id> --full` and diffing the returned body against the canonical `.md` on disk,
line-by-line) is that the C3 markdown serializer drops the literal `_` and `*` characters inside
un-backticked table cells when it re-renders a fact's canonical body for the round-trip check:
`from __future__ import annotations` re-renders as `from future import annotations` (the two
`__` pairs around `future` vanish), and, in `c3-101`'s `scan(root)` Contract row only, the
trailing globs `wiki/**/*.md` and `sources/cards/*.md` re-render as `wiki/**/.md` and
`sources/cards/.md` (the lone `*` immediately before `.md` vanishes; `sources/raw/*` later in
the same cell, followed by a space, round-trips untouched and needs no change). Every other
table cell in these 9 facts that contains a bare `*` not immediately followed by `.` — e.g.
`check_*`, `test_*.py`, `scripts/*.py` — round-trips byte-identical already and is left alone,
confirmed by the same read-vs-disk diff.

This drift is purely a rendering artifact of un-escaped markdown special characters; none of the
9 rows' asserted meaning is wrong or in question. The fix is to wrap exactly the tokens that
trigger the drift in backticks — inline code spans are opaque to the emphasis-parsing pass that
causes the drop — leaving every other character of every row untouched. `c3x repair` is
deliberately not used: this ADR lands the fix as a reviewed change-unit per fact, exactly like
any other frozen-fact edit.

One more wrinkle, discovered while drafting this ADR: any write-type wrapper operation (`add`,
`change accept`, ...) reseals every fact in the canvas from the same lossy renderer, so the
moment this ADR is added it temporarily re-drifts the canonical text of all 9 rows to the lossy
form (`c3x check` would show a *different*, but non-worsening, symptom mid-flight — the row text
itself, not just the round-trip check, briefly reads the lossy way). The block patches below
still land correctly on top of that intermediate state: each patch's `base` anchor is the lossy
hash `c3x read <id> --section <name> --cite` already reports (the same hash the reseal produces),
so `change apply`'s drift gate matches, and the patch body's backtick-escaped text is what
actually lands on disk once the unit applies — restoring and permanently protecting the original
meaning. For the same reason, this ADR's own Affected Topology Evidence column below cites each
entity's `## Goal` section (unaffected by the bug) rather than the specific drifting row: citing
the drifting row's own lossy hash directly is rejected by `add adr`'s citation-freshness check as
`stale`, because that check reseals-then-validates in a way the patch-apply gate does not.

## Decision

For each of the 9 facts, replace the one (two, for `c3-101`) offending table row with a `block`
patch whose body is byte-identical to the current row except that the drifting token is wrapped
in a backtick-delimited code span:

- `c3-101` Governance row (rule-stdlib-only-py39) and Contract row (`scan(root)`): wrap
`` `from __future__ import annotations` ``, `` `wiki/**/*.md` ``, and
`` `sources/cards/*.md` ``.
- `c3-102`, `c3-103`, `c3-201`, `c3-210`, `c3-211`, `c3-410`, `c3-411` Governance rows: wrap
`` `from __future__ import annotations` `` (the exact wording differs per row; only that
substring changes).
- `rule-stdlib-only-py39`'s "Not This" row ("A new module ships without ..."): wrap
`` `from __future__ import annotations` ``.

This is the smallest change that makes the round-trip check pass: no row's asserted content
changes, only the markdown escaping of the substrings the serializer already mishandles. The
alternative — running `c3x repair` to rebuild the cache — was rejected because it papers over
the canonical markdown itself rather than fixing what the canonical markdown says, and it is not
a change-unit the CLI's audit trail can review.

Proof-first sequencing: the first patch below (`c3-102`) is applied and verified with
`c3x check --only c3-102` alone before the remaining 8 patches are added to this same
change-unit and the full `c3x check` is run.

## Affected Topology

| Entity | Type | Why affected | Evidence | Governance review |
| --- | --- | --- | --- | --- |
| c3-101 | component | Governance row and Contract row (scan(root)) carry the drifting tokens; Goal cited as evidence of the live entity since the drifting row's own cite is unstable (see Context) | c3-101#n100@v1:sha256:633523ed677c89602627f44aa55865b3f45d0b1c060837521cb0a7e990f47faa "Run the wiki-wide mechanical lint (broken links, orphans, card citations, card checks," | Backtick-escape only; no assertion changes |
| c3-102 | component | Governance row carries the drifting token; Goal cited as evidence of the live entity per the same reason | c3-102#n128@v1:sha256:c539f9ea1e1e70023000452635d67e75be016a2882f178e6d7aeedecdbd8d565 "Validate a single sourced-content card's YAML frontmatter against card-schema.json and report" | Backtick-escape only; no assertion changes |
| c3-103 | component | Governance row carries the drifting token; Goal cited as evidence of the live entity per the same reason | c3-103#n154@v1:sha256:1be14b74304152dffc73f12dd9b7fca2e2b4295d4354108d576d957ca1b659eb "Validate a proposed commit message's format at commit time and report every violation, so a" | Backtick-escape only; no assertion changes |
| c3-201 | component | Governance row carries the drifting token; Goal cited as evidence of the live entity per the same reason | c3-201#n217@v1:sha256:5647debd2277602cdd057ce61f6e31fbd919d0ff026ecc58ff7b4e8305369b98 "Compute and diff the one integrity ledger — path, role, sha256 per MANAGED/TEMPLATE file plus" | Backtick-escape only; no assertion changes |
| c3-210 | component | Governance row carries the drifting token; Goal cited as evidence of the live entity per the same reason | c3-210#n245@v1:sha256:2cba2aceeb3d79bfbe10c89f08553587d67a3389f8bc0baadec83cf19d768a4c "Stamp a brand-new wiki instance from scratch — scaffold, seed, hooks wired, first commit made —" | Backtick-escape only; no assertion changes |
| c3-211 | component | Governance row carries the drifting token; Goal cited as evidence of the live entity per the same reason | c3-211#n273@v1:sha256:d5fad8f079f65d5d320ffdad1df8cc079eac795bbad727248fa4856e795b94ff "Bring an existing wiki instance forward to a newer (or, with --allow-downgrade, older) harness" | Backtick-escape only; no assertion changes |
| c3-410 | component | Governance row carries the drifting token; Goal cited as evidence of the live entity per the same reason | c3-410#n422@v1:sha256:4bf5c52eea921ec91006890d4f516b9629e000ced8acaf40dd4355e9ec0f3b9a "Prove c3-1 (scripts) behaves correctly — including that it stays byte-identical to ogp-wiki and" | Backtick-escape only; no assertion changes |
| c3-411 | component | Governance row carries the drifting token; Goal cited as evidence of the live entity per the same reason | c3-411#n447@v1:sha256:9ff58214d7e79dab8108b474089b6f597fb3831c2686ed3df31cc07935efdf7a "Prove c3-2 (lifecycle) behaves correctly end-to-end — a fresh init lands lint-clean with a" | Backtick-escape only; no assertion changes |
| rule-stdlib-only-py39 | N.A - rule (not system/container/component; a coding-standard fact this ADR mutates) | "Not This" row carries the drifting token; Goal cited as evidence of the live entity per the same reason | rule-stdlib-only-py39#n507@v1:sha256:73c38cb86710504178722cecdfa01ab2c6b88aad384a6c516bc3edb8a1342c16 "Guarantee every wiki-harness Python module runs on the oldest interpreter a consuming wiki might" | Backtick-escape only; no assertion changes |

## Verification

| Check | Result |
| --- | --- |
| c3x check --only c3-102 (after the first patch alone) | Must be ok:true with no content_mismatch for c3-102 |
| c3x check (after all 9 patches apply) | Must be ok:true, content_mismatch absent from the issue list (stale eval-anchor warnings are pre-existing and unrelated) |
| python3 -m unittest discover -s tests -q | Must stay green (doc-only change-unit; no code touched) |
