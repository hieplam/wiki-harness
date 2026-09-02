# Known limitations

This document records defects that were investigated during card `C3-3` (C3 governance
reconciliation, campaign `wiki-harness-extraction`) and deliberately left unfixed, together with
the ruling that accepted them. Both entries below trace to Shaman rulings R11 and R12.

## (A) `c3x check` is red on a fresh clone

**What it is.** Running `c3x check` from a clean checkout of this repository exits non-zero,
reporting `content_mismatch` for 9 facts (as of this card: `c3-101`, `c3-102`, `c3-103`, `c3-201`,
`c3-210`, `c3-211`, `c3-410`, `c3-411`, `rule-stdlib-only-py39`).

**Why.** `c3x repair` and `c3x check` are not round-trip stable for this corpus. The C3 serializer
strips backticks from markdown table cells when it re-canonicalizes a fact's body, and the parser
then interprets the resulting un-backticked `__`/`*` runs as markdown emphasis instead of literal
text — for example a table cell containing `` `from __future__ import annotations` `` is silently
turned into `from future import annotations` once the backticks are stripped and the double
underscores are consumed as emphasis markers. There is therefore no committed corpus state that is
simultaneously fact-correct (the code identifiers and paths read correctly) and `check`-green (the
serializer's canonical form matches the stored form) — repairing away the mismatch corrupts the
very content the facts exist to describe.

**Why it is not fixed in this campaign.** The corpus on `main` keeps the backticked, meaning-correct
form and accepts that `c3x check` is red as a result (Shaman ruling R11, superseding the earlier
ruling R10 that had called for a reconciling change-unit). The gate that actually matters for this
card — `c3x eval`, which checks that every fact's binding resolves against the shipped code — is
green (`total: 17, holds: 17, drift: 0`). `c3x check`'s content-mismatch is a serializer/parser
round-trip defect in the C3 runtime, not a drift between the facts and the code.

**Follow-up (out of scope for this campaign, R5: the campaign ends at T26).** Vendor or patch the
C3 runtime so canonicalization round-trips markdown table cells without mangling backticked
content, then re-run `c3x repair` and confirm `c3x check` goes green corpus-wide.

## (B) `c3-211`'s Contract row 1 states the `upgrade.py` target is optional; it is required

**The row, as currently stored** (`c3-211`, Contract table, surface column):

```
python3 wiki-harness/upgrade.py [<target-dir>] [--to vX.Y.Z] [--apply] [--adopt-drift <path> ...] [--allow-downgrade] [--commit] [--check]
```

The `[<target-dir>]` bracketing states the target directory argument is optional.

**Evidence that the row is false.**

- `upgrade.py:1181` — `parser.add_argument("target")` is a plain positional with no `nargs="?"`
  and no default; argparse therefore treats it as required.
- Running `python3 upgrade.py --check` (no target given) from a shipped tree fails immediately:
  `upgrade.py: error: the following arguments are required: target`, exit code 2.
- The sibling lifecycle fact `c3-210` (init) writes the equivalent CLI surface for `init.py` with
  the same argument UNBRACKETED: `python3 wiki-harness/init.py <target-dir> [flags]` — consistent
  with `target` being required there too.
- `/Users/hip/repo/wiki-harness-analysis/plan/plan-v3.md:409` (the plan of record `c3-211` itself
  cites as Evidence) also writes the surface with the target argument UNBRACKETED:
  `python3 wiki-harness/upgrade.py <target-dir> [flags]`.

**Why it is not fixed here.** Correcting the row requires authoring a C3 change-unit, which reseals
the corpus into the canonical (un-backticked) form that limitation (A) above shows is corrupt for
this corpus — `c3-211`'s own body carries the table cell `` `from __future__ import annotations` ``,
so even a change-unit scoped to only the Contract table's surface row would still force a full
resync/repair pass over the fact and corrupt that unrelated cell. Shaman ruling R11 forbids running
`c3x repair` or hand-editing `.c3/` facts for this card; ruling R12 records this specific defect as
accepted-and-visible rather than silently left for a future reader to rediscover.

**Follow-up (out of scope for this campaign, R5).** Fix this row's bracketing alongside the C3
runtime round-trip fix in limitation (A): once canonicalization is safe, run a proper change-unit
that corrects `c3-211`'s Contract row 1 to `python3 wiki-harness/upgrade.py <target-dir> [--to
vX.Y.Z] [--apply] [--adopt-drift <path> ...] [--allow-downgrade] [--commit] [--check]`.
