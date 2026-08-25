---
id: c3-3
c3-seal: a2df398d30eae87a25e17ad4674d661bbac585d602325784b093cfb8f78a69a1
title: templates
type: container
parent: c3-0
goal: |-
    Hold every MANAGED/TEMPLATE/SEEDED source file a wiki instance is stamped with, split by
    update-ownership class, so `lifecycle`'s `init`/`upgrade` can look up "is this path safe to
    silently overwrite" without guessing from content or timestamps.
---

## Goal

Hold every MANAGED/TEMPLATE/SEEDED source file a wiki instance is stamped with, split by
update-ownership class, so `lifecycle`'s `init`/`upgrade` can look up "is this path safe to
silently overwrite" without guessing from content or timestamps.

## Components

| ID | Name | Category | Status | Goal Contribution |
| --- | --- | --- | --- | --- |
| c3-301 | template-vars |  | active | Hold the two var-substituted (TEMPLATE-class) source files a wiki instance's root gets rendered |
| c3-302 | managed-sources |  | active | Hold every fixed-content (MANAGED-class) source file a wiki instance receives byte-for-byte, with |
| c3-303 | seeded-starters |  | active | Hold every SEEDED-class source file a wiki instance gets written once, at init time only, as a |

## Responsibilities

Own the canonical bytes (or var-substitution template) for every file class that is not 100%
INSTANCE-owned. Never own INSTANCE content itself — `sources/raw/*`, `sources/cards/src-*.md`,
and `wiki/*.md` have no template-container component because the library never ships bytes for
them.

## Complexity Assessment

Low logical complexity (no code, no branching — every artifact here is a file to copy or
substitute), but broad surface area: plan-v3 §2.3's ownership map lists roughly a dozen paths a
single `init`/`upgrade` run must place correctly, so most of the risk in this container is
completeness (every path in the ownership map has a source here) rather than correctness of any
one file.
