---
target: c3-102
scope: whole
type: component
parent: c3-1
category: foundation
title: card-lint
---

## Goal

Validate a single sourced-content card's YAML frontmatter against `card-schema.json` and report
every schema violation, independent of the wiki-wide checks `c3-101` runs.

## Parent Fit

| Field | Value |
|---|---|
| Container | c3-1 (scripts) |
| Category | Foundation — `c3-101` (lint-core) calls into this component's `check_card`/`parse_frontmatter`/`load_schema`/`resolve` for its own `check_cards`/`check_frontmatter` checks |
| Depends on | Nothing inside `c3-1` |
| Depended on by | `c3-101` (lint-core, imports `SCHEMA_PATH, Finding, check_card, load_schema, parse_frontmatter, resolve` — this is how `c3-110`'s `pre-commit` hook reaches card validation, indirectly through `lint.py`); `c3-410` (lint-test-suite) |

## Purpose

Own `scripts/card_frontmatter_lint.py`: `parse_frontmatter` (split a card's leading YAML-ish
block from its body), `resolve` (resolve a `raw:` path relative to the card), `load_schema`
(parse `card-schema.json`), `check_card`/`_check_value` (validate one card's frontmatter fields
against the loaded schema's rules), plus T04's `card_id_scan_pattern()` addition that makes the
card-id shape schema-driven instead of the hardcoded `CARD_ID_RE` in `lint.py`. Non-goal: this
component never reads `card-schema.json` from disk itself in its pure functions — that stays an
edge, same as `c3-101`.

## Governance

| Reference | Type | Governs | Precedence | Notes |
|---|---|---|---|---|
| rule-pure-core-impure-edge | rule | `check_card`/`_check_value`/`parse_frontmatter`/`resolve`/`load_schema` take text/dicts in, return values out — no disk I/O inside them | Hard | Same split `c3-101` follows for its own pure/impure boundary |
| rule-stdlib-only-py39 | rule | Imports only `json`/`os`/`re`/`sys`/`collections`/`pathlib`, opens with `from __future__ import annotations` | Hard | Same floor every module in `scripts`/`lifecycle` targets |
| ref-verbatim-port | ref | Forked byte-identical from ogp-wiki HEAD `f8b43fb`, T04's `card_id_scan_pattern()` addition is the one sanctioned delta | Hard for the port | This component's `Contract` surfaces are the exact behaviour the ref requires stay byte-identical |

## Contract

| Surface | Direction | Contract | Boundary | Evidence |
|---|---|---|---|---|
| `check_card(path, text, schema, exists) -> list[Finding]` | IN/OUT | Given a card's path, raw text, the loaded schema dict, and an `exists` existence-check callable, returns every `Finding` for that one card; same inputs always produce the same findings | Pure function boundary | `/Users/hip/repo/ogp-wiki/scripts/card_frontmatter_lint.py:107` |
| `load_schema(text) -> dict` | IN/OUT | Parses `card-schema.json`'s raw text into the schema dict `check_card` consumes; raises on malformed JSON, never touches disk itself | Pure function boundary — reading the file bytes is the caller's job | `/Users/hip/repo/ogp-wiki/scripts/card_frontmatter_lint.py:70` |

## Derived Materials

| Material | Must derive from | Allowed variance | Evidence |
|---|---|---|---|
| `wiki-harness/scripts/card_frontmatter_lint.py` | `/Users/hip/repo/ogp-wiki/scripts/card_frontmatter_lint.py` at HEAD `f8b43fb`, byte-for-byte, per this component's own Contract surfaces, plus T04's `card_id_scan_pattern()` helper | Only T04's itemized delta | plan-v3.md §7 Phase 1 (T01/T04) |
