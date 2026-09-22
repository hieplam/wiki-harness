# Knowledge gaps — rules for this folder

This folder is the ledger of questions this wiki could not answer. It exists so the
wiki learns what it is missing instead of forgetting every miss.

| File | What | Mutability |
|---|---|---|
| `knowledge-gaps.jsonl` | The ledger. One JSON record per line. | **Append-only** — never edit, reorder or delete a line |
| `KNOWLEDGE_GAP.md` | A generated, human-readable view | Regenerated wholesale; never hand-edit |
| `gap-schema.json` | The single definition of record keys | **MANAGED** — every `upgrade` re-delivers the library's default verbatim; a local edit is drift |

## Never write to the ledger by hand

Use the CLI. It owns the id, the timestamp, the key order and the JSON encoding, and it
validates the record against the whole ledger before writing a byte:

```bash
python3 scripts/gap.py add --service <repo> --session <id> \
  --context "..." --prompt "..." --question "..." \
  --wiki-answer "..." --answer-given "..." --topics a,b
python3 scripts/gap.py resolve <gap-id> --card <card-id> --page wiki/<page>.md
python3 scripts/gap.py measure <gap-id> --verdict answered --wiki-answer "..."
python3 scripts/gap.py ratify  <gap-id> --verdict unrelated --reason "..."
python3 scripts/gap.py list --status opened
```

Prose arguments accept `@path` to read a file and `-` to read stdin, because a recorded
answer is usually paragraphs rather than a shell argument.

## The four record types

- **`gap`** — a question the wiki could not fully answer. Holds both what the wiki
  returned at the time (`wiki_answer`, the baseline you later measure against) and what
  the caller finally told the user (`answer_given`).
- **`resolution`** — intent: this card is meant to answer that gap.
- **`measurement`** — a re-run of the question against the wiki. Appendable any number
  of times, so improvement is a time series and a resolution is allowed to fail.
- **`ratification`** — a human judgement that the question is out of scope, with a reason.

## Status is derived, never stored

To compute a gap's status, walk the records that reference it **in file order** — the
order lines appear in the file — **not** in `at` order. In an append-only log the append
order is the truth; `at` is descriptive metadata and may legitimately be out of order (a
backfilled measurement, clock skew, a timezone mistake). Begin at `opened`. Then, for each
record in turn:

| Record | New status |
|---|---|
| `ratification` with `verdict: unrelated` | `unrelated` |
| `measurement` with `verdict: answered` | `answered` |
| `measurement` with `verdict: partial` or `still-missing` | `opened` |
| `resolution` | unchanged — intent is not evidence |

The last record wins. A gap with no records after it is `opened`.

There is no `status` field anywhere in the ledger, and adding one would be a schema
change, not a record. `scripts/gap_ledger.py` implements this fold; nothing else may.

## Widening the schema

`gap-schema.json` is **MANAGED**, not seeded: every `wiki-harness upgrade` re-delivers the
library's own default verbatim, and a plain hand-edit is reported as drift and refused. If
this wiki genuinely needs a wider record shape (a new key, enum, or type), first run
`upgrade --adopt-drift gaps/gap-schema.json`, then edit the file. That command deliberately
**forks this file from the library**: this wiki's `gap-schema.json` will no longer be
overwritten by future `upgrade` runs, and any schema improvement the library ships later has
to be re-applied here by hand. Do this only when the wider shape is genuinely needed, and
document why in the commit.

## Append-only is enforced, not requested

`scripts/lint.py` blocks a commit when the previously committed (HEAD) content is not a
byte prefix of the STAGED content — what will actually land in the next commit, not
merely what sits in the working file — and independently when the staged diff removes
any line. The working
tree is checked too, so tampering is caught even before it is staged. A deleted line, a
reordered line, a single edited byte, a truncation, and deleting the file to rewrite it are
all rejected, whether performed against the working file or staged directly. If you need to
correct a record, **append a correcting record** — that is what the event types are for.
