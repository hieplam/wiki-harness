---
target: c3-301
scope: whole
type: component
parent: c3-3
category: foundation
title: template-vars
---

## Goal

Hold the two var-substituted (TEMPLATE-class) source files a wiki instance's root gets rendered
from at `init` time, so `AGENTS.md` and `README.md` carry the wiki's own identity instead of
generic library placeholder text.

## Parent Fit

| Field | Value |
|---|---|
| Container | c3-3 (templates) |
| Category | Foundation — `c3-210` (init) renders both files from this component's sources at step 6; nothing inside `c3-3` depends on this component |
| Depends on | `ref-ownership-classes` (this component *is* the TEMPLATE class named there) |
| Depended on by | `c3-210` (init, step 6: render `AGENTS.md`/`README.md` from these templates with the 4 variables); `c3-211` (upgrade, step 9: re-render the `template`-role paths using variables read back from the manifest) |

## Purpose

Own `templates/AGENTS.root.md.tmpl` (4 vars: `wiki_title`, `org_name`, `content_language`,
`repo_name`; carries the ownership-disclosure table row naming all four ownership classes) and
`templates/README.md.tmpl` (3 vars: `repo_name`, `wiki_title`, `org_name`; no longer instructs a
human to hand-create `CLAUDE.md`, since `init` step 9 now seeds it directly, tracked, every time).
Non-goal: this component never substitutes its own variables — that rendering step is `c3-210`'s
and `c3-211`'s, using the values `c3-201` (manifest) records.

## Governance

| Reference | Type | Governs | Precedence | Notes |
|---|---|---|---|---|
| ref-ownership-classes | ref | Both files here are TEMPLATE-class: rendered fresh from the 4 variables on every `init`/`upgrade`, never instance-forked without `--adopt-drift` | Hard | This component is one of the three that split `c3-3` along the ref's classes |
| ref-verbatim-port | ref | N.A - templates are new content this library authors, not ported from ogp-wiki's current tree | N.A - not applicable to this component | Recorded for completeness — this is the one ref every `c3-1` component cites and this component does not |

## Contract

| Surface | Direction | Contract | Boundary | Evidence |
|---|---|---|---|---|
| `templates/AGENTS.root.md.tmpl` | OUT | Renders to `<wiki>/AGENTS.md` given `wiki_title`, `org_name`, `content_language`, `repo_name`; the rendered output's ownership-disclosure table names all 4 classes `ref-ownership-classes` defines | Static template file, consumed by `c3-210`'s render step | plan-v3.md §2.1, §2.3 (`AGENTS.md` TEMPLATE row) |
| `templates/README.md.tmpl` | OUT | Renders to `<wiki>/README.md` given `repo_name`, `wiki_title`, `org_name`; contains no instruction to hand-create `CLAUDE.md` | Static template file, consumed by `c3-210`'s render step | plan-v3.md §2.3 (`README.md` TEMPLATE row, "no longer tells a human to hand-create CLAUDE.md") |

## Derived Materials

| Material | Must derive from | Allowed variance | Evidence |
|---|---|---|---|
| `<wiki>/AGENTS.md`, `<wiki>/README.md` (every wiki instance) | This component's own `Contract` surfaces — the two `.tmpl` sources, with only the 4/3 named variables substituted | The 4 substituted values only; every other byte fixed | plan-v3.md §2.3 (ownership map) |
