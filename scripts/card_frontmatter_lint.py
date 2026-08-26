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

# Filenames that hold rules, not card content, wherever they land inside
# sources/cards/: AGENTS.md (progressive-disclosure rules), recipes.md
# (sources/cards/recipes.md, T10's split), and CLAUDE.md (the tracked,
# single-line "@AGENTS.md" pointer files, A7). Declared here, once, because
# lint.py already imports from this module -- a reverse import would be
# circular -- so lint.py imports RULES_FILES rather than keeping its own
# copy; both entry points then agree on the same set by construction, never
# by keeping two literals in sync by hand.
RULES_FILES = {"AGENTS.md", "recipes.md", "CLAUDE.md"}

# Fallback only -- used when the schema is missing or malformed (that case
# already produces a CARD_SCHEMA finding) or when a schema load_schema()
# accepts as valid simply does not declare an id.pattern rule (load_schema()
# never requires an 'id' key, or a 'pattern' rule under it); never
# authoritative when the schema does declare one. The schema's own
# id.pattern, when present, is the single, sole declaration of card-id shape.
DEFAULT_CARD_ID_PATTERN = r"^src-\d{4}-\d{2}-\d{2}-\d{3}$"


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
    check while the file still looked like it enforced one; and a 'pattern'
    rule whose value is not a non-empty string that re.compile()s -- for ANY
    key, not only 'id' -- would otherwise raise, uncaught, inside
    _check_value()'s re.match() the moment a card is checked against it.

    'id's 'pattern' rule additionally carries a narrow, validated contract,
    because it is the single, sole declaration of card-id shape that BOTH
    lint.py's check_card_citations() (an unanchored substring scan, via
    card_id_scan_pattern()) and check_commit_msg.py's validate() (an
    anchored, whole-value match) derive their own matcher from. Recovering
    the citation-scan pattern by guessing at anchor shapes -- only
    recognizing '^' when it happens to be the pattern's first character,
    stripping '$' unless it looks escaped, and so on -- is an open-ended
    game against '(?i)^', '\\A', '\\Z', escaped '\\$', and whatever else a
    schema author writes next; a pattern like '(?i)^src-...$' would slip
    through such guessing with its embedded '^' intact, and without
    re.MULTILINE that '^' only matches true position 0 of the file, so
    check_card_citations() could never find a citation anywhere but the
    very start of a page. So the id.pattern value must instead (a) compile,
    (b) start with '^' as its literal first character, (c) end with an
    UNESCAPED '$' as its literal last character, (d) have a non-empty body
    between those two anchors, so stripping them can never yield an
    always-matching empty scan pattern, and (e) contain no other '^', '$',
    '\\A' or '\\Z' in that body (a simple text scan, not real character-class
    parsing -- see the loop below). Anything else fails closed exactly like
    an unknown rule name; a schema author who wants a case-insensitive id
    family writes the flag INSIDE the anchors, e.g. '^(?i:src-...)$', which
    satisfies the contract.
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
        if "pattern" in rules:
            pattern = rules["pattern"]
            if not isinstance(pattern, str) or not pattern:
                findings.append(Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                                        f"key '{key}': rule 'pattern' is not "
                                        f"a valid regex: value must be a "
                                        f"non-empty string"))
            else:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    findings.append(Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                                            f"key '{key}': rule 'pattern' is not "
                                            f"a valid regex: {exc}"))
                else:
                    if key == "id" and _violates_id_pattern_contract(pattern):
                        findings.append(Finding(
                            "ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                            "key 'id': rule 'pattern' must be anchored as "
                            "^...$ with no other anchors or flags before ^ "
                            "— write flags inside the anchors, e.g. "
                            "^(?i:src-...)$"))
    if findings:
        return None, findings
    return keys, []


def _violates_id_pattern_contract(pattern):
    """True when `pattern` (already known to be a non-empty string that
    re.compile()s) does not satisfy load_schema()'s narrow id.pattern
    contract -- see that function's docstring for why the contract is this
    narrow. A simple text scan, not a regex-semantics parse: it does not
    distinguish an anchor character inside a character class from one
    outside it, which can only make the check MORE strict, never less."""
    if not pattern.startswith("^") or not pattern.endswith("$"):
        return True
    body = pattern[:-1]
    trailing_backslashes = len(body) - len(body.rstrip("\\"))
    if trailing_backslashes % 2 == 1:
        return True  # the trailing '$' is an escaped literal, not the anchor
    inner = pattern[1:-1]
    if not inner:
        return True  # degenerate: an empty scan pattern matches everywhere
    if "\\A" in inner or "\\Z" in inner:
        return True
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\":
            i += 2
            continue
        if ch in "^$":
            return True
        i += 1
    return False


def card_id_scan_pattern(schema_id_pattern):
    """Derive an unanchored substring-search pattern from the schema's
    id.pattern: strip the required leading '^' and trailing '$'. Trivial
    and provably correct -- not a guess -- because load_schema()'s id.pattern
    contract (see its docstring) guarantees any pattern this function is
    ever handed by its real callers is exactly one leading '^' and one
    trailing unescaped '$' around a non-empty, anchor-free body. A pure
    string transform, not a second declaration of card-id shape -- lint.py
    uses this to find card ids embedded anywhere in wiki prose, while
    check_commit_msg.py's validate() matches the anchored id.pattern
    itself, whole-value, unchanged."""
    return schema_id_pattern[1:-1]


def card_id_pattern_from_schema(schema):
    """Derive the card-id pattern from a loaded schema (load_schema()'s
    return value), falling back to DEFAULT_CARD_ID_PATTERN only for the
    shapes a schema load_schema() has already accepted as valid can still
    present: `schema` is None (missing/malformed -- CARD_SCHEMA already
    reports that case), or the schema omits 'id' entirely, or declares 'id'
    with no 'pattern' rule under it. Every other shape -- a non-string,
    non-compiling, or contract-violating id.pattern -- is now rejected
    earlier, at load_schema() itself (see its docstring), so any schema
    this function receives that DOES declare id.pattern always carries a
    pattern already valid and contract-shaped. The single call site both
    check_card_citations() and check_commit_msg.py's main() use to derive
    their matcher."""
    if schema is None:
        return DEFAULT_CARD_ID_PATTERN
    return schema.get("id", {}).get("pattern", DEFAULT_CARD_ID_PATTERN)


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
        # Every card file, not only ones named 'src-*.md': the schema's
        # id.pattern is the single, sole declaration of card-id shape, and
        # discovery must not stay pinned to the library's former default
        # id prefix once a wiki customizes it away -- mirrors lint.py's own
        # location-based _cards() definition (sources/cards/*.md, minus
        # RULES_FILES, which hold rules, not card content).
        targets = [Path(a) for a in args] or \
            sorted(p for p in (root / "sources" / "cards").glob("*.md")
                   if p.name not in RULES_FILES)
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
