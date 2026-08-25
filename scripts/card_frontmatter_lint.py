#!/usr/bin/env python3
"""Card frontmatter lint for the wiki.

Owns the whole answer to "is this card valid?" - the frontmatter parser, the
schema loader and the per-card checks - so one module and one rule set judge a
card. scripts/lint.py imports from here and this module imports nothing back,
which is why the shared primitives (Finding, parse_frontmatter, resolve) live
here: a two-way import would be circular, and a second copy would be the very
duplication this file exists to remove.

Card rules are DATA, not code: sources/cards/card-schema.json is the single
source of truth, read both by this linter and by the agent writing cards.

Python 3 stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import namedtuple
from pathlib import Path, PurePosixPath

Finding = namedtuple("Finding", "severity code path message")  # severity: ERROR | WARN

SCHEMA_PATH = "sources/cards/card-schema.json"
RULE_KEYS = {"required", "enum", "pattern", "list", "path", "card_ref",
             "matches_filename", "description"}


KV_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def parse_frontmatter(text):
    """Restricted YAML subset: 'key: value' and 'key: [a, b]' lines only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, ["missing frontmatter block"]
    meta, errors = {}, []
    for i, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return meta, errors
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = KV_RE.match(line)
        if not m:
            errors.append(f"line {i}: not a 'key: value' line")
            continue
        key, value = m.group(1), m.group(2).strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value
    return meta, errors + ["frontmatter not closed with ---"]


def resolve(from_path, target):
    parts = list(PurePosixPath(from_path).parent.parts)
    for part in PurePosixPath(target).parts:
        if part == "..":
            if not parts:
                return f"<out-of-root>/{target}"
            parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def load_schema(text):
    """Parse card-schema.json. `text` is None when the file is missing.

    Fails closed: every problem returns (None, findings) so no card is checked
    against a schema we cannot trust. If a missing file meant "no rules",
    deleting it would be the cheapest way past a failing lint; if an unknown
    rule name were ignored, writing 'regex' instead of 'pattern' would retire a
    check while the file still looked like it enforced one.
    """
    if text is None:
        return None, [Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                              "schema file is missing")]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                              f"invalid JSON: {exc}")]
    keys = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(keys, dict) or not keys:
        return None, [Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                              "schema must have a non-empty 'keys' object")]
    findings = []
    known = ", ".join(sorted(RULE_KEYS))
    for key, rules in sorted(keys.items()):
        if not isinstance(rules, dict):
            findings.append(Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                                    f"key '{key}': rules must be an object"))
            continue
        for unknown in sorted(set(rules) - RULE_KEYS):
            findings.append(Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                                    f"key '{key}': unknown rule '{unknown}' "
                                    f"- known rules: {known}"))
    if findings:
        return None, findings
    return keys, []


def check_card(path, text, schema, exists):
    """Check one card against the schema.

    `exists(repo_relative_path) -> bool` is injected because the two callers
    know the tree differently: lint.py already holds a whole-tree map in
    memory, while the CLI and the git hook only have the disk.
    """
    meta, errors = parse_frontmatter(text)
    findings = [Finding("ERROR", "CARD_FM", path, e) for e in errors]
    if meta is None:
        return findings
    declared = ", ".join(sorted(schema))
    for key in sorted(set(meta) - set(schema)):
        findings.append(Finding(
            "ERROR", "CARD_KEY", path,
            f"unknown key '{key}' - not declared in {SCHEMA_PATH}. "
            f"Fix: remove the key, or add it under \"keys\" in that file and "
            f"commit with op 'schema:'. Declared keys: {declared}"))
    for key, rules in sorted(schema.items()):
        value = meta.get(key)
        if key not in meta or value in ("", []):
            if rules.get("required"):
                findings.append(Finding("ERROR", "CARD_KEY", path,
                                        f"missing required field '{key}'"))
            continue
        findings += _check_value(path, key, value, rules, exists)
    return findings


def _check_value(path, key, value, rules, exists):
    if rules.get("list") and not isinstance(value, list):
        return [Finding("ERROR", "CARD_VALUE", path,
                        f"'{key}' must be a list like [a, b]")]
    if isinstance(value, list):
        if not rules.get("list"):
            return [Finding("ERROR", "CARD_VALUE", path,
                            f"'{key}' must be a single value, not a list")]
        return []
    findings = []
    if "enum" in rules and value not in rules["enum"]:
        findings.append(Finding("ERROR", "CARD_VALUE", path,
                                f"'{key}' is '{value}' - must be one of: "
                                f"{', '.join(rules['enum'])}"))
    if "pattern" in rules and not re.match(rules["pattern"], value):
        findings.append(Finding("ERROR", "CARD_VALUE", path,
                                f"'{key}' is '{value}' - must match "
                                f"{rules['pattern']}"))
    if rules.get("matches_filename") and value != PurePosixPath(path).stem:
        findings.append(Finding("ERROR", "CARD_REF", path,
                                f"'{key}' is '{value}' but the filename stem is "
                                f"'{PurePosixPath(path).stem}'"))
    if rules.get("path") and not exists(resolve(path, value)):
        findings.append(Finding("ERROR", "CARD_REF", path,
                                f"'{key}' points at a missing file: {value}"))
    if rules.get("card_ref") and not exists(f"sources/cards/{value}.md"):
        findings.append(Finding("ERROR", "CARD_REF", path,
                                f"'{key}' points at a missing card: {value}"))
    return findings


# ---- impure edge below this line ----

def main(argv):
    args = list(argv)
    root = Path(__file__).resolve().parent.parent
    if "--root" in args:
        i = args.index("--root")
        root = Path(args[i + 1])
        del args[i:i + 2]
    schema_file = root / SCHEMA_PATH
    text = schema_file.read_text(encoding="utf-8-sig") if schema_file.is_file() else None
    schema, findings = load_schema(text)
    if schema is not None:
        targets = [Path(a) for a in args] or \
            sorted((root / "sources" / "cards").glob("src-*.md"))
        for target in targets:
            if not target.is_absolute() and not target.is_file() and (root / target).is_file():
                target = root / target
            rel = os.path.relpath(target.resolve(), root.resolve()).replace(os.sep, "/")
            if not target.is_file():
                findings.append(Finding("ERROR", "CARD_FM", rel, "file not found"))
                continue
            findings += check_card(rel, target.read_text(encoding="utf-8-sig"),
                                   schema, lambda p: (root / p).is_file())
    for f in sorted(findings):
        print(f"{f.severity} {f.code} {f.path}: {f.message}")
    errors = sum(1 for f in findings if f.severity == "ERROR")
    print(f"card lint: {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
