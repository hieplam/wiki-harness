---
target: c3-2
scope: whole
type: container
parent: c3-0
title: lifecycle
---

## Goal

Stamp a brand-new wiki instance (`init`) and safely bring an existing one forward to a newer
harness release in place (`upgrade`), using a single integrity manifest (`manifest.py`) as the
shared source of truth both read and write for what is on disk versus what the library expects.

## Components

| ID | Name | Category | Status | Goal Contribution |
|---|---|---|---|---|

## Responsibilities

Own the whole lifecycle of a wiki instance's relationship to the library: first stamp, drift
detection against the recorded manifest, atomic promote (scratch-copy, lint, bare promote-copy,
write manifest), downgrade refusal, MAJOR-removal guard, and `--adopt-drift` for a path an owner
deliberately forked. This container is harness-own logic only — nothing ogp-wiki-specific lives
here; every var it substitutes (`wiki_title`, `org_name`, `content_language`, `repo_name`) comes
from the instance being stamped, not from any assumption about which wiki it is.

## Complexity Assessment

Highest-risk container in the library: `upgrade` is the only place a mistake can corrupt a
wiki owner's existing, already-committed content, so its atomic-promote/rollback path
(`try`/`except` -> `git checkout -- .`, no marker file, no `--resume`) is deliberately the most
heavily specified part of plan-v3 (§3.2, T16-T24).
