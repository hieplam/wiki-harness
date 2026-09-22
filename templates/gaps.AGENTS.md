# Knowledge gaps — rules for this folder

This folder is the ledger of questions this wiki could not answer. It exists so the
wiki learns what it is missing instead of forgetting every miss.

| File | What | Mutability |
|---|---|---|
| `knowledge-gaps.jsonl` | The ledger. One JSON record per line. | **Append-only** — never edit, reorder or delete a line |
| `KNOWLEDGE_GAP.md` | A generated, human-readable view | Regenerated wholesale; never hand-edit |
| `gap-schema.json` | The ONLY definition of record keys | Change under a `schema:` commit |

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

## Append-only is enforced, not requested

`scripts/lint.py` blocks a commit when the committed content is not a byte prefix of the
working file, and independently when the staged diff removes any line. A deleted line, a
reordered line, a single edited byte, a truncation, and deleting the file to rewrite it
are all rejected. If you need to correct a record, **append a correcting record** — that
is what the event types are for.
