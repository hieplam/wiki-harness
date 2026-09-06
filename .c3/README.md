---
id: c3-0
c3-seal: 3aedb8b9aacfd15dc403c279e1ce8ddcc3d9585b9183c633f3babce9de13579f
title: wiki-harness
goal: |-
    Provide a versioned, standalone Python library that stamps a lint/hook/rules harness onto any
    wiki instance via `init`/`upgrade`, keeping every consuming wiki's linting behaviour byte-identical
    to what ogp-wiki runs today, so multiple wikis (ogp-wiki, ai-wiki, ...) can share one maintained
    source of truth instead of each forking its own copy of the scripts.
---

## Goal

Provide a versioned, standalone Python library that stamps a lint/hook/rules harness onto any
wiki instance via `init`/`upgrade`, keeping every consuming wiki's linting behaviour byte-identical
to what ogp-wiki runs today, so multiple wikis (ogp-wiki, ai-wiki, ...) can share one maintained
source of truth instead of each forking its own copy of the scripts.

## Containers

| ID | Name | Boundary | Status | Responsibilities | Goal Contribution |
| --- | --- | --- | --- | --- | --- |
| c3-1 | scripts |  | active | Run the exact lint/hook checks ogp-wiki runs today — byte-identical — by forking lint.py, | Run the exact lint/hook checks ogp-wiki runs today — byte-identical — by forking lint.py, |
| c3-2 | lifecycle |  | active | Stamp a brand-new wiki instance (init) and safely bring an existing one forward to a newer | Stamp a brand-new wiki instance (init) and safely bring an existing one forward to a newer |
| c3-3 | templates |  | active | Hold every MANAGED/TEMPLATE/SEEDED source file a wiki instance is stamped with, split by | Hold every MANAGED/TEMPLATE/SEEDED source file a wiki instance is stamped with, split by |
| c3-4 | tests |  | active | Prove the library's own correctness once, against a synthetic fixture that is never ogp-wiki | Prove the library's own correctness once, against a synthetic fixture that is never ogp-wiki |
| c3-5 | distribution | service | active | Put the harness on a user's machine and keep it current, so adopting a wiki is one command | Put the harness on a user's machine and keep it current, so adopting a wiki is one command |

## Abstract Constraints

| Constraint | Rationale | Affected Containers |
| --- | --- | --- |
| Python 3.9 floor, standard library only, no pyproject.toml/setup.py, no console-script entry points | A consuming wiki may run an older interpreter with no package-manager step available; a stdlib-only script runs the same way scripts/lint.py already does today, wherever python3 exists | scripts, lifecycle |
| Every ported script produces byte-identical findings, ordering, and exit codes against ogp-wiki's real, current, unmodified tree | ogp-wiki's baseline oracle at /Users/hip/repo/wiki-harness-analysis/baseline is the acceptance judge for this whole extraction; any behavioural drift in a linter would break the migration (T29) silently | scripts |
| No tests/ directory ships inside any wiki instance, ever | Per plan-v3 A6, the library's own suite is the only place any harness test lives; a wiki's own correctness is python3 scripts/lint.py exiting 0, already enforced by .githooks/pre-commit on every commit | tests, templates |
| No on-disk marker file, --resume flag, or --ci flag anywhere on the CLI surface | Per plan-v3 A3/A4, interrupted-upgrade resumability and CI are deliberately deferred, never partially seeded; the atomic promote in upgrade recovers instead via git checkout -- . | lifecycle |
