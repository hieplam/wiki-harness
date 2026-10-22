# Rules for `wiki/`

A **wiki page** is durable knowledge about one topic, synthesised from claims across many
cards. Pages are mutable and fully agent-maintained. The folder is FLAT — no subfolders yet.
A **decision page** is a wiki page that records one decision; see
[Decision pages](#decision-pages).

Filenames are `lowercase-kebab-case.md`.

## Frontmatter schema

| key | required? | value | enforced by lint |
|---|---|---|---|
| `title` | **REQUIRED** | human-readable page title | present and non-empty (`FM` error) |
| `topics` | **REQUIRED** | non-empty list, `[a, b]` | present and non-empty (`FM` error) |
| `kind` | optional | `decision` marks a decision page; any other value is ignored | — |
| `status` | decision pages: **REQUIRED** | `proposed`, `decided` or `superseded` | `DECISION` error |
| `decided` | optional | `YYYY-MM-DD`, the day it was decided; omit it when not known | format (`DECISION` error) |
| `supersedes` | optional | page name(s) this decision replaces: `old-page` or `[a, b]` | names a decision page (`DECISION` error) |
| `superseded_by` | decision pages with `status: superseded`: **REQUIRED** | page name(s) that replaced this one | names a decision page that names this one back (`DECISION` error) |

A **page name** is the file name without `.md`: `widgets-ship-singly` for
`wiki/widgets-ship-singly.md`. Only `title` and `topics` apply to an ordinary page; the other
keys apply when the page has `kind: decision`. Unknown keys parse and are ignored.

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

## Decision pages

A decision page records one decision: why it was needed, what was decided, which options lost,
and what is now true because of it. Write one when a source records any of:

- an incident, and the fix or rule that came out of it;
- a lesson learnt — write it as the rule the team now follows;
- a decision that holds today but was never written down.

One decision per page. A page that explains how something works links to the decision pages
that shaped it; it does not hold them.

A decision page has `kind: decision`, a `status`, and these four `##` sections, in any order,
next to any other sections it needs:

| section | holds |
|---|---|
| `## Context` | What led to the record: the incident (a timeline is welcome), the lesson, or "recorded as it stands today" |
| `## Decision` | What was decided, who decided it, and why |
| `## Rejected options` | Each option that lost, and why. Write `None considered.` when there were none |
| `## Consequences` | What is now true because of the decision, the good and the bad |

```markdown
---
title: Widgets ship in batches of ten
topics: [widget-assembly]
kind: decision
status: decided
decided: 2024-03-01
---
Widgets ship in batches of ten
[src-2024-03-01-001](../sources/cards/src-2024-03-01-001.md).

## Context
A single widget cost more to ship than to build.

## Decision
Ship in batches of ten. The owner decided this on 2024-03-01, because shipping cost per
widget fell below the build cost at that size.

## Rejected options
- Batches of a hundred: a batch took a month to fill.

## Consequences
- An urgent widget waits for its batch to fill.
```

A `proposed` page is a decision under discussion. It changes nothing on another page.

### Replacing a decision

Never edit a decided page into a different decision: write a new decision page, then

1. on the new page, set `supersedes: <old page name>`;
2. on the old page, set `status: superseded` and `superseded_by: <new page name>`, and leave
   the rest of it as it was — it is the history;
3. in `index.md`, change the old page's line under `## Decisions` to say `superseded`.

A `proposed` page may already name the page it would replace; the old page changes only when the
new one is `decided`. A decision that stops holding with no successor is replaced by a decision
to stop: write that page and supersede the old one.

Lint (`DECISION`) checks that both pages name each other, and that no chain of replacements loops
back on itself.

### Importing an ADR

An ADR (architecture decision record) from another system enters like any other source: store
the file in `sources/raw/`, write a card for it with `origin: adr`, then file its claims into
decision pages — one page per decision the ADR records. If `sources/cards/card-schema.json` does
not list `adr` in its `origin` enum, add it first, in a `schema:` commit.

| ADR part | decision page |
|---|---|
| Context, problem, decision drivers | `## Context` |
| Decision, chosen option | `## Decision` |
| Alternatives considered, considered options | `## Rejected options` |
| Consequences, risks, costs | `## Consequences` |
| Status accepted, implemented, done | `status: decided` |
| Status proposed, open, in progress | `status: proposed` |
| Status superseded | `status: superseded`, with `superseded_by` |

An ADR whose proposal was rejected, withdrawn or abandoned records a decision not to do it: file
it as `status: decided`, with the rejection as its `## Decision`. A deprecated ADR with no
successor: import it, then write the decision to stop and supersede it. Import a superseded ADR
only together with the ADR that replaced it. Leave out the parts that only serve the ADR's own
tool, such as content seals and tool commands; the raw file keeps them.

## Index

Every page must appear in `index.md`, grouped under a `##` topic heading, with a one-line
description. Lint fails both directions: a page missing from the index, and an index entry
pointing at a page that does not exist.

Every decision page appears a second time, as a list item in one `## Decisions` section, with
its status in the item. The item's first link is the entry. A later link, also on a wrapped
line or a nested item, is a reference:

```markdown
## Decisions

- [Widgets ship in batches of ten](./wiki/widgets-ship-in-batches.md) — decided 2024-03-01
- [Widgets ship singly](./wiki/widgets-ship-singly.md) — superseded by [batches of ten](./wiki/widgets-ship-in-batches.md)
```

Lint (`DECISION`) fails a decision page missing from that section, a line that does not state
the page's status, and an entry that is not a decision page.
