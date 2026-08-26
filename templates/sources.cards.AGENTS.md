# Rules for `sources/cards/`

A **card** is the envelope for exactly one source: where it came from, how much to trust it,
and the atomic claims extracted from it. Cards are mutable — claims and topics may improve.

Card id: `src-YYYY-MM-DD-NNN` (NNN = 3-digit sequence within that day, starting 001).
Filename is `<id>.md`, and `id:` must match the filename — lint checks this. To customize the id
shape, edit `id`'s `pattern` rule in [card-schema.json](./card-schema.json): it must be anchored as
`^...$` with no other anchors or flags before `^` (write flags inside the anchors, e.g.
`^(?i:src-...)$`).

## Frontmatter schema

The key set is defined once, in [card-schema.json](./card-schema.json), which
`scripts/card_frontmatter_lint.py` reads. Open that file to see every key, whether it is
required, what its value must look like, and what it means.

The key set is **closed**. A key that is not declared there is an `ERROR CARD_KEY` and the
commit is blocked:

```
ERROR CARD_KEY sources/cards/src-2024-01-15-003.md: unknown key 'source_author'
  - not declared in sources/cards/card-schema.json.
  Fix: remove the key, or add it under "keys" in that file and commit with op 'schema:'.
  Declared keys: date, id, origin, parent, raw, source_id, source_parent_id, source_space,
  source_url, source_version, topics, trust
```

To add a key, add it to `card-schema.json` in the same operation and commit with op `schema:`.
Never add a key to a card alone — that is how the documented schema and the enforced schema
drift apart.

Emit every `source_*` key the source system can supply. Their names are enforced; their values
are not yet, because a value rule generalised from one source system would be a guess — see
[../../VISION.md](../../VISION.md).

Source hierarchy lives in `parent` / `source_parent_id` and **not** in `sources/raw/` paths —
see [../AGENTS.md](../AGENTS.md) for why.

## Example

```markdown
---
id: src-2024-01-15-001
date: 2024-01-15
origin: session
trust: stated
topics: [widget-assembly]
---
## Claims
- One atomic, filing-ready fact per bullet.

## Notes
Context that isn't a claim (optional).
```

## Trust and contradiction

| trust | meaning |
|---|---|
| `verified-in-code` | Confirmed against source code or observed system behaviour |
| `stated` | Asserted by a person or document, unverified |
| `hearsay` | Second-hand |

Contradictions resolve by **higher trust first, then newer `date`** — which is why `date` is
the date the claim was *asserted*, not the date it was filed. A specification and a meeting
transcript are both `stated`, so the later one wins; neither becomes `verified-in-code` until
someone checks it against the code, and that check is its own ingest with `origin: session`.

## Writing claims

One atomic, filing-ready fact per bullet, in wiki vocabulary rather than the source's own
phrasing. A claim that needs "and" twice is usually three claims. Anything that is context
rather than a fact goes in `## Notes`.

Every card must be cited by at least one wiki page, or lint reports `UNFILED`.

### Per-origin recipes — what to extract

| origin | extract |
|---|---|
| `session` | Verified findings, decisions made, gotchas discovered |
| `transcript` | Speakers/personas, decisions + owners, commitments |
| `jira` | Problem → root cause → fix → affected services |
| `slack` | The question + the tribal answer |
| `confluence` / `research` | Concepts, definitions, procedures |

All recipes emit the SAME contract: a card with claims, filed into wiki pages. A recipe must
never invent its own wiki-page shape.
