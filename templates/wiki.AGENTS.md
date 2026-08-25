# Rules for `wiki/`

A **wiki page** is durable knowledge about one topic, synthesised from claims across many
cards. Pages are mutable and fully agent-maintained. The folder is FLAT — no subfolders yet.

Filenames are `lowercase-kebab-case.md`.

## Frontmatter schema

| key | required? | value | enforced by lint |
|---|---|---|---|
| `title` | **REQUIRED** | human-readable page title | present and non-empty (`FM` error) |
| `topics` | **REQUIRED** | non-empty list, `[a, b]` | present and non-empty (`FM` error) |

No optional keys are defined for wiki pages yet. Unknown keys parse and are ignored.

## Example

```markdown
---
title: Widget assembly
topics: [widget-assembly]
---
Knowledge prose. Every non-obvious statement cites its card:
[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).
Link related pages inline: [quality checks](./quality-checks.md).

## Open questions
Unresolved contradictions or gaps live HERE, on the affected page (optional section).
```

## Citing

Cite the card as a relative link to `../sources/cards/<card-id>.md`, at the end of the
statement it supports. Lint fails a citation to a card id that does not exist (`CITE`), and
fails a card that no page cites (`UNFILED`).

Cite the source, not the folder: a page states what is true, and the card says who claimed it.
Never copy a source's structure into a page — one Confluence page may become three wiki pages,
or three may collapse into one.

## One page per durable topic

Split by what stays true, not by how the source was organised. A metric that other features
will also cite (`doc-chase-cycle-time`) earns its own page; a section that only exists because
a document had that heading does not.

Cross-link related pages inline. A page with no inbound link from another page is reported as
an `ORPHAN` warning — it means the knowledge is unreachable by anyone browsing.

## Open questions

Unresolved contradictions, gaps, and unverified numbers go in `## Open questions` **on the
affected page**, not in a central backlog. When a new claim contradicts the page, resolve it
by trust + date if that is clear-cut; if it is not, record both here and tell the human.

## Index

Every page must appear in `index.md`, grouped under a `##` topic heading, with a one-line
description. Lint fails both directions: a page missing from the index, and an index entry
pointing at a page that does not exist.
