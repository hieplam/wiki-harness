---
target: c3-1
scope: whole
type: container
parent: c3-0
title: scripts
---

## Goal

Run the exact lint/hook checks ogp-wiki runs today — byte-identical — by forking `lint.py`,
`card_frontmatter_lint.py`, `check_commit_msg.py`, and the two git hooks verbatim from ogp-wiki
HEAD, plus only the specific additive fixes plan-v3 names (T03/T04/T08).

## Components

| ID | Name | Category | Status | Goal Contribution |
|---|---|---|---|---|

## Responsibilities

Own the three vendored linters and the two git hooks that wire them into every commit, and
guarantee their combined behaviour — findings, finding order, and exit codes — never drifts from
ogp-wiki's current, real tree. This container is the single place any lint check itself lives;
`lifecycle` calls into it (to lint a scratch copy before promoting an upgrade) but never
reimplements a check.

## Complexity Assessment

Low structural complexity (three small modules plus two POSIX-shell hooks, all ported verbatim),
but zero behavioural tolerance: the baseline oracle judges every change to this container against
ogp-wiki's real, current, unmodified tree, so even a whitespace-level output difference is a
regression here in a way it would not be elsewhere in the library.
