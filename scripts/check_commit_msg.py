#!/usr/bin/env python3
"""Validate a commit message against the wiki's operation-commit convention.

Subject format: <op>(<ref>): <summary>
  op  : ingest | lint | schema | chore
  ref : required for ingest (a card id matching card-schema.json's id.pattern),
        optional otherwise.
Merge/Revert/fixup/squash subjects are exempt.
Pure core: validate(). Edge: main() reads the message file (git commit-msg hook arg)
and the schema's id.pattern (sources/cards/card-schema.json under --root, default cwd).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card_frontmatter_lint import (  # noqa: E402  (needs the sys.path line above)
    DEFAULT_CARD_ID_PATTERN, SCHEMA_PATH, card_id_pattern_from_schema, load_schema)

OPS = ("ingest", "lint", "schema", "chore")
SUBJECT_RE = re.compile(r"^(ingest|lint|schema|chore)(\(([^)]*)\))?: \S.*$")
EXEMPT_PREFIXES = ("Merge", "Revert", "fixup!", "squash!")


def validate(message: str, card_id_pattern: str = DEFAULT_CARD_ID_PATTERN) -> list[str]:
    lines = [l for l in message.splitlines() if not l.startswith("#")]
    subject = lines[0].strip() if lines else ""
    if not subject:
        return ["empty commit message"]
    if subject.startswith(EXEMPT_PREFIXES):
        return []
    m = SUBJECT_RE.match(subject)
    if not m:
        return [
            f"subject must be '<op>(<ref>): <summary>' with op in {'/'.join(OPS)}; "
            f"got: '{subject}'"
        ]
    op, ref = m.group(1), m.group(3)
    if op == "ingest" and (not ref or not re.fullmatch(card_id_pattern, ref)):
        return ["ingest commits require ref = card id, e.g. "
                "'ingest(src-2026-08-06-001): summary'"]
    return []


# ---- impure edge below this line ----

def main(argv: list[str]) -> int:
    args = list(argv)
    root = Path.cwd()
    if "--root" in args:
        i = args.index("--root")
        root = Path(args[i + 1])
        del args[i:i + 2]
    msg_file = args[0]
    schema_file = root / SCHEMA_PATH
    try:
        text = schema_file.read_text(encoding="utf-8-sig") if schema_file.is_file() else None
    except UnicodeDecodeError:
        # Treated exactly like a missing schema file: load_schema(None)
        # reports it unreadable and card_id_pattern_from_schema() falls
        # back to DEFAULT_CARD_ID_PATTERN, same as every other schema
        # problem this edge already swallows rather than letting an
        # unhandled exception reach every commit, not only 'ingest' ones.
        text = None
    schema, _ = load_schema(text)
    card_id_pattern = card_id_pattern_from_schema(schema)
    with open(msg_file, encoding="utf-8") as f:
        errors = validate(f.read(), card_id_pattern=card_id_pattern)
    for e in errors:
        print(f"commit-msg: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
