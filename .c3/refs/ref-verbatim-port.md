---
id: ref-verbatim-port
c3-seal: 53991068f78be7adab57694c29ca6d902ec82625e58b6b707fe3939b0a01f966
title: Fork scripts byte-identical, never rewrite
type: ref
goal: |-
    Give every file in the `scripts` container an unambiguous provenance story so its behaviour
    never drifts silently away from what ogp-wiki committers already rely on today.
---

## Goal

Give every file in the `scripts` container an unambiguous provenance story so its behaviour
never drifts silently away from what ogp-wiki committers already rely on today.

## Choice

Fork `scripts/lint.py`, `scripts/card_frontmatter_lint.py`, `scripts/check_commit_msg.py`,
`.githooks/pre-commit`, and `.githooks/commit-msg` byte-for-byte from ogp-wiki HEAD commit
`f8b43fb` (T01), applying only the specific, itemized additive/prose fixes plan-v3 names by
number — T03 (genericize examples, byte-match `CARD_KEY`, fix the `raw:` example, remove a
dangling spec reference), T04 (schema-driven card-id mechanism, deleting the hardcoded
`CARD_ID_RE`), T08 (the `RULES_FILES` generalization) — never a freehand rewrite of the checks
themselves.

## Why

The baseline oracle at `/Users/hip/repo/wiki-harness-analysis/baseline` judges this whole
extraction by whether ogp-wiki's real, current, unmodified tree produces the exact same
findings, finding order, and exit codes before and after the port — a standing constraint on
every task in this engagement, not just this one. A rewrite, even a careful one, risks a
behavioural regression that a byte-identical fork avoids by construction: forking first and
then landing every deliberate change as its own named, separately tested commit (plan-v3 §5)
makes each behavioural delta reviewable in isolation, instead of buried inside a rewrite diff
where a reviewer cannot tell "ported as-is" from "changed on purpose."

## How

Port each file with `git show f8b43fb:scripts/lint.py > wiki-harness/scripts/lint.py` (and the
sibling paths), diff the result against the previous commit's tree to confirm zero unintended
bytes changed, then land each of T03/T04/T08's fixes as its own commit on top of the verbatim
port commit — never squashed into it. Source: `/Users/hip/repo/ogp-wiki/scripts/lint.py` at
HEAD `f8b43fb`.
