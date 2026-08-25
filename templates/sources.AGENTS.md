# Rules for `sources/`

A **source** is one artifact the wiki learned something from. It is stored twice: the bytes
go in `raw/` and never change; the meaning goes in a card in `cards/` and may be corrected.

| Folder | Holds | Rules |
|---|---|---|
| `raw/` | Verbatim artifact bytes | this file |
| `cards/` | One card per source: envelope + claims | [cards/AGENTS.md](./cards/AGENTS.md) |

## `raw/` is immutable

Write once at ingest. Never edit, never delete, **never move** — `scripts/lint.py`
(`check_raw_immutability`) fails any git status other than `A` for a path under
`sources/raw/`, and a rename is modelled as delete + add, so it trips too.

## `raw/` is FLAT and keyed by card id

```
sources/raw/<card-id>-<slug>.<ext>
sources/raw/src-2024-01-15-001-onboarding-guide.storage.html
```

Never mirror a source system's folder tree into `raw/`. A raw path is immutable, so it may
assert only what is **permanently true** — that these bytes are the capture behind card X.
Anything that can change (title, parent page, space, version) is mutable metadata and lives
in the card's frontmatter, where it can be corrected. A path-encoded parent becomes a lie you
are forbidden to fix the first time someone re-parents a page.

Reconstruct a source tree with `grep '^parent:' sources/cards/*.md`, not with `ls`.

## Store the original, not a rendering

Keep the source's own serialisation: Confluence storage-format XHTML, a Slack JSON export, a
raw email. Converting to markdown at ingest loses information you cannot recover, and the
file may never be re-written to fix it. Extension should reflect the real format
(`.storage.html`, `.json`, `.eml`, `.txt`).

Deliberately skipping part of a source tree is fine — say so in the card's `## Notes` and in
the commit body, so the gap is visible rather than looking like an oversight.
