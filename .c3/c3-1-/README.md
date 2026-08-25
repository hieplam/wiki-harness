---
id: c3-1
c3-seal: 09144b5991dd08698084dc612dc519ff764d5d0b9fbc55068d4042b28e2d78db
title: scripts
type: container
parent: c3-0
goal: |-
    Run the exact lint/hook checks ogp-wiki runs today — byte-identical — by forking `lint.py`,
    `card_frontmatter_lint.py`, `check_commit_msg.py`, and the two git hooks verbatim from ogp-wiki
    HEAD, plus only the specific additive fixes plan-v3 names (T03/T04/T08).
---

## Goal

Run the exact lint/hook checks ogp-wiki runs today — byte-identical — by forking `lint.py`,
`card_frontmatter_lint.py`, `check_commit_msg.py`, and the two git hooks verbatim from ogp-wiki
HEAD, plus only the specific additive fixes plan-v3 names (T03/T04/T08).

## Components

| ID | Name | Category | Status | Goal Contribution |
| --- | --- | --- | --- | --- |
| c3-101 | lint-core |  | active | Run the wiki-wide mechanical lint (broken links, orphans, card citations, card checks, |
| c3-102 | card-lint |  | active | Validate a single sourced-content card's YAML frontmatter against card-schema.json and report |
| c3-103 | commit-msg-lint |  | active | Validate a proposed commit message's format at commit time and report every violation, so a |
| c3-110 | git-hooks |  | active | Wire c3-101's wiki-wide lint and c3-103's commit-message check into every commit a wiki |

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
