---
target: c3-303
scope: whole
type: component
parent: c3-3
category: foundation
title: seeded-starters
---

## Goal

Hold every SEEDED-class source file a wiki instance gets written once, at `init` time only, as a
starting point the instance then owns completely — the library never touches these paths again on
any later `upgrade`.

## Parent Fit

| Field | Value |
|---|---|
| Container | c3-3 (templates) |
| Category | Foundation — `c3-210` (init) writes this component's files once; `c3-211` (upgrade) explicitly never touches them after |
| Depends on | `ref-ownership-classes` (this component *is* the SEEDED class named there) |
| Depended on by | `c3-210` (init, step 8: seed `recipes.md`, `card-schema.json` using `--origins`, `VISION.md` skeleton, `index.md` header, `.gitignore` snippet) |

## Purpose

Own `templates/recipes.md` (trust-meanings plus per-origin recipes — the part
`c3-302`'s `sources.cards.AGENTS.md` deliberately cut out), `templates/card-schema.default.json`
(minimal generic starter, `origin: [session]` only unless `--origins` widens it),
`templates/VISION.skeleton.md` (status enum + unblock-condition convention only, zero entries),
`templates/index.md.header.tmpl` (title + instruction line, zero rows), and
`templates/gitignore.snippet` (no longer lists `CLAUDE.md`, since `CLAUDE.md` is tracked, A7).
Non-goal: this component's files are seeded exactly once — no later `upgrade` run ever
re-renders or overwrites a SEEDED path, even across a MAJOR version bump; `id.pattern` inside the
seeded `card-schema.json` becomes the wiki's own sole source of truth for card-id shape the moment
`init` finishes (plan-v3 §4.4a).

## Governance

| Reference | Type | Governs | Precedence | Notes |
|---|---|---|---|---|
| ref-ownership-classes | ref | Every file here is SEEDED-class: written once by `init`, then 100% instance-owned; absent from the manifest's `files` map entirely (plan-v3 §2.4) | Hard | This component is one of the three that split `c3-3` along the ref's classes |

## Contract

| Surface | Direction | Contract | Boundary | Evidence |
|---|---|---|---|---|
| `templates/recipes.md`, `templates/card-schema.default.json`, `templates/VISION.skeleton.md`, `templates/index.md.header.tmpl`, `templates/gitignore.snippet` | OUT | Written once, verbatim (or with `--origins` substitution for `card-schema.default.json` only), to `sources/cards/recipes.md`, `sources/cards/card-schema.json`, `VISION.md`, `index.md`, `.gitignore`; never re-touched by `upgrade` | Static file, consumed only by `c3-210`'s seed step | plan-v3.md §2.1, §2.3 |
| Never re-rendered by `upgrade` | IN | `c3-211` step 9 explicitly excludes `seeded`/`instance`/`instance-fork` paths from its overwrite/re-render loop | Negative contract — absence of a write path | plan-v3.md §3.2 step 9 |

## Derived Materials

| Material | Must derive from | Allowed variance | Evidence |
|---|---|---|---|
| `sources/cards/recipes.md`, `sources/cards/card-schema.json`, `VISION.md`, `index.md`, `.gitignore` (every wiki instance, at `init` time only) | This component's own `Contract` surfaces — its 5 template sources, verbatim except `--origins` substitution in `card-schema.default.json` | Freely diverges from the source after `init` — that divergence is the intended, permanent instance ownership | plan-v3.md §2.3 (ownership map) |
