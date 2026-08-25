---
target: c3-3
scope: whole
type: container
parent: c3-0
title: templates
---

## Goal

Hold every MANAGED/TEMPLATE/SEEDED source file a wiki instance is stamped with, split by
update-ownership class, so `lifecycle`'s `init`/`upgrade` can look up "is this path safe to
silently overwrite" without guessing from content or timestamps.

## Components

| ID | Name | Category | Status | Goal Contribution |
|---|---|---|---|---|

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
