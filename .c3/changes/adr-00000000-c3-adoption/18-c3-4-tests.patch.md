---
target: c3-4
scope: whole
type: container
parent: c3-0
title: tests
---

## Goal

Prove the library's own correctness once, against a synthetic fixture that is never ogp-wiki
content, so every wiki instance the library stamps out inherits that proof by construction
instead of needing a `tests/` directory of its own.

## Components

| ID | Name | Category | Status | Goal Contribution |
|---|---|---|---|---|

## Responsibilities

Own the only test suite that exists anywhere in this engagement (per A6, no wiki instance —
not ogp-wiki after migration, not a freshly-`init`-ed wiki, not the synthetic `ai-wiki` smoke
fixture — ever gets a `tests/` folder). Hold the synthetic fixture wiki and every test module
that exercises `scripts`, `lifecycle`, and `templates` against it, including the genericity
check that greps the whole repo for 0 OGP-specific strings.

## Complexity Assessment

Moderate: this container carries the entire correctness burden for a library three other
containers depend on being right, but the fixture stays deliberately small and fully synthetic,
so the main complexity risk is coverage completeness (T02/T05/T06/T07's gap-closing tasks), not
fixture maintenance.
