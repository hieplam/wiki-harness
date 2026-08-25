---
target: c3-401
scope: whole
type: component
parent: c3-4
category: foundation
title: fixture
---

## Goal

Provide the one small, fully synthetic wiki tree every test in this container exercises against,
so the library's own test suite never depends on — or risks leaking — real ogp-wiki content.

## Parent Fit

| Field | Value |
|---|---|
| Container | c3-4 (tests) |
| Category | Foundation — both `c3-410` and `c3-411` depend on this fixture; neither test-suite component builds its own fixture tree |
| Depends on | Nothing inside `c3-4` |
| Depended on by | `c3-410` (lint-test-suite, exercises `c3-101`/`c3-102`/`c3-103` against this fixture); `c3-411` (lifecycle-test-suite, `init`/`upgrade` tests scaffold and mutate copies of this fixture) |

## Purpose

Own `tests/fixtures/sample-wiki/`: a small, fully synthetic wiki instance — never ogp-wiki
content — including a customized (`ai-...`-prefixed) `card-schema.json` variant proving the
schema-driven card-id mechanism (T04) works for an `id.pattern` other than ogp-wiki's, and a
`recipes.md` fixture proving `c3-410`'s `RULES_FILES` generalization fix (T08) actually excludes
`recipes.md` from card checks. Non-goal: this fixture is never expanded to mirror ogp-wiki's real
tree size or content — it stays deliberately small and purpose-built per assertion.

## Governance

| Reference | Type | Governs | Precedence | Notes |
|---|---|---|---|---|
| adr-00000000-c3-adoption | adr | This ADR is the record of why this fixture exists as its own component, separate from the two test-suite components (`c3-410`/`c3-411`) that consume it | Informational — no ref/rule targets fixture data directly | Fixture content is markdown/JSON test data, not Python source; `rule-stdlib-only-py39` and `rule-pure-core-impure-edge` target `.py` modules only |

## Contract

| Surface | Direction | Contract | Boundary | Evidence |
|---|---|---|---|---|
| `tests/fixtures/sample-wiki/` | OUT | A complete, minimal, synthetic wiki tree (root files, `sources/`, `wiki/`) that `lint.py --root` can run against directly; contains zero strings that also appear in ogp-wiki's real content | Static fixture directory, read (and copied, for `init`/`upgrade` tests) by every test in `c3-410`/`c3-411` | plan-v3.md §2.1 (`tests/fixtures/sample-wiki/`) |
| Customized `card-schema.json` fixture variant | OUT | Uses an `id.pattern` other than ogp-wiki's `src-\d{4}-\d{2}-\d{2}-\d{3}` shape, proving `c3-102`'s schema-driven id mechanism (T04) is not secretly still hardcoded to ogp-wiki's pattern | Static fixture file | plan-v3.md §2.1, §4.4a |

## Derived Materials

| Material | Must derive from | Allowed variance | Evidence |
|---|---|---|---|
| `tests/fixtures/sample-wiki/` on disk | This component's own `Contract` surfaces above — it has no other source to derive from; it *is* the source | Content may grow only to cover a genuinely new test case, never to approximate real ogp-wiki content | plan-v3.md §7 Phase 1 (T02) |
