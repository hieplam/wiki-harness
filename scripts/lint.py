#!/usr/bin/env python3
"""Mechanical lint for the wiki: broken links, orphan pages, card citations,
frontmatter, index sync, and raw-source immutability.

Pure core: parse/extract/resolve helpers and check_* functions (data in →
Findings out). Impure edges: scan()/git_changes()/main() at the bottom.
Python 3 stdlib only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import namedtuple
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card_frontmatter_lint import (  # noqa: E402  (needs the sys.path line above)
    RULES_FILES, SCHEMA_PATH, Finding, card_id_pattern_from_schema,
    card_id_scan_pattern, check_card, load_schema, parse_frontmatter, resolve)
from manifest import diff_manifest, hash_tree, is_valid_role, read_manifest  # noqa: E402

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

MANIFEST_FILENAME = ".wiki-harness-manifest.json"

# read_harness_manifest()'s return type: harness_version is the manifest's
# recorded library version (used only by the instance-fork WARN message
# below); recorded is the manifest's "files" map ({path: {"role":...,
# "sha256":...}}); actual is {path: sha256} freshly hashed off disk for
# every path recorded with a role this check judges.
ManifestState = namedtuple("ManifestState", "harness_version recorded actual")

# read_harness_manifest()'s other possible return value: the manifest file
# exists but cannot be trusted (invalid JSON, or a "files" entry missing
# the 'role'/'sha256' keys check_harness() relies on) -- `detail` is a
# short human-readable reason, folded into check_harness()'s one Finding.
ManifestMalformed = namedtuple("ManifestMalformed", "detail")


def extract_links(text):
    out = []
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        base = target.split("#")[0]
        if base:
            out.append(base)
    return out


PAGE_REQUIRED = ("title", "topics")


def _wiki_pages(files):
    return [p for p in files if p.startswith("wiki/") and p.endswith(".md")
            and PurePosixPath(p).name not in RULES_FILES]


def _cards(files):
    return [p for p in files if p.startswith("sources/cards/") and p.endswith(".md")
            and PurePosixPath(p).name not in RULES_FILES]


def check_broken_links(files):
    findings = []
    for path in sorted(files):
        if not path.endswith(".md"):
            continue
        for target in extract_links(files[path]):
            if resolve(path, target) not in files:
                findings.append(Finding("ERROR", "LINK", path,
                                        f"broken link: {target}"))
    return findings


def check_orphans(files):
    pages = _wiki_pages(files)
    inbound = set()
    for path in pages:
        for target in extract_links(files[path]):
            resolved = resolve(path, target)
            if resolved != path:
                inbound.add(resolved)
    return [Finding("WARN", "ORPHAN", p, "no inbound links from other wiki pages")
            for p in sorted(pages) if p not in inbound]


def check_card_citations(files, schema):
    """`schema` is the loaded card-schema.json keys dict, or None when
    load_schema() could not load one at all -- check_cards() already reports
    the CARD_SCHEMA finding for that case. Either that, or a schema that
    loaded fine but declares no id.pattern rule, quietly falls back to
    DEFAULT_CARD_ID_PATTERN (card_id_pattern_from_schema) rather than
    reporting it a second time. The scan itself stays unanchored
    (card_id_scan_pattern) so a citation is found anywhere in wiki prose,
    not just standing alone.

    The derived scan pattern is compiled inside a try/except: even a
    schema id.pattern that itself compiles fine can, in principle, derive a
    scan pattern that does not. Rather than crash the whole lint run, that
    fails closed with a single CARD_SCHEMA finding and skips the scan."""
    scan_pattern = card_id_scan_pattern(card_id_pattern_from_schema(schema))
    try:
        card_id_re = re.compile(scan_pattern)
    except re.error as exc:
        return [Finding("ERROR", "CARD_SCHEMA", SCHEMA_PATH,
                        f"key 'id': rule 'pattern' cannot be used to scan "
                        f"citations: {exc}")]
    findings = []
    card_ids = {PurePosixPath(p).stem for p in _cards(files)}
    cited = set()
    for path in sorted(_wiki_pages(files)):
        # group(0) is the whole match regardless of how many capturing
        # groups the schema's id.pattern declares -- findall() would return
        # tuples of the captured subgroups instead whenever the pattern has
        # any, silently misreporting every citation as unknown/unfiled.
        found = {m.group(0) for m in card_id_re.finditer(files[path])}
        for cid in sorted(found):
            cited.add(cid)
            if cid not in card_ids:
                findings.append(Finding("ERROR", "CITE", path,
                                        f"cites unknown card {cid}"))
    for cid in sorted(card_ids - cited):
        findings.append(Finding("ERROR", "UNFILED", f"sources/cards/{cid}.md",
                                "card is not cited by any wiki page"))
    return findings


def check_frontmatter(files):
    findings = []

    def require(meta, path, keys):
        for key in keys:
            if key not in meta or meta[key] in ("", []):
                findings.append(Finding("ERROR", "FM", path,
                                        f"missing required field '{key}'"))

    for path in sorted(_wiki_pages(files)):
        meta, errors = parse_frontmatter(files[path])
        findings += [Finding("ERROR", "FM", path, e) for e in errors]
        if meta is not None:
            require(meta, path, PAGE_REQUIRED)
    return findings


def check_cards(files):
    """Route every card to the card linter. Card rules live in
    sources/cards/card-schema.json; nothing about them is decided here."""
    schema, findings = load_schema(files.get(SCHEMA_PATH))
    if schema is None:
        return findings
    for path in sorted(_cards(files)):
        findings += check_card(path, files[path], schema, lambda p: p in files)
    return findings


def check_index_sync(files):
    index = files.get("index.md")
    if index is None:
        return [Finding("ERROR", "INDEX", "index.md", "index.md is missing")]
    findings = []
    listed = {resolve("index.md", t) for t in extract_links(index)}
    listed = {p for p in listed if p.startswith("wiki/")}
    pages = set(_wiki_pages(files))
    for p in sorted(pages - listed):
        findings.append(Finding("ERROR", "INDEX", "index.md",
                                f"wiki page not listed: {p}"))
    for p in sorted(listed - pages):
        findings.append(Finding("ERROR", "INDEX", "index.md",
                                f"listed page does not exist: {p}"))
    return findings


def check_raw_immutability(changes):
    return [Finding("ERROR", "RAW", path,
                    f"raw source changed (git status {status}) — sources/raw/ is immutable")
            for status, path in changes
            if path.startswith("sources/raw/") and not status.startswith("A")]


def check_harness(manifest_state):
    """Pure. Eighth check, mirroring check_raw_immutability(): plain data
    (a ManifestState, a ManifestMalformed, or None) in, Finding list out --
    never touches the filesystem itself. `manifest_state` is whatever
    read_harness_manifest() (the impure edge below) returned.

    manifest_state is None -> the manifest itself is missing entirely: one
    ERROR, and every other check keeps running normally (this function is
    never called from run(), so nothing else is short-circuited by it).

    manifest_state is a ManifestMalformed -> the manifest file exists but
    is not trustworthy (invalid JSON, or a "files" entry missing its
    'role'/'sha256' keys): one ERROR, same narrow blast radius as the
    missing-manifest case above. Fails closed exactly like
    check_card_citations()'s try/except around a bad regex and
    check_cards()'s graceful missing-schema handling -- a malformed
    manifest must never crash lint.py (the mandatory pre-commit hook)
    with an uncaught traceback and zero diagnostic output.

    Otherwise, judges each recorded path's drift (manifest.diff_manifest()
    against the freshly-hashed actual bytes): a managed/template path
    that's missing or hash-mismatched is an ERROR (harness-owned content
    changed or vanished without the manifest being updated); an
    instance-fork path whose hash differs from its recorded (pre-fork)
    hash is a WARN reminder that it will never receive future updates. No
    upgrade-in-progress-marker branch (v3, A3) -- that mechanism does not
    exist."""
    if manifest_state is None:
        return [Finding(
            "ERROR", "HARNESS", MANIFEST_FILENAME,
            "manifest missing — this wiki was not initialised with "
            "wiki-harness, or the manifest was deleted; run 'upgrade "
            "--adopt' to generate one.")]
    if isinstance(manifest_state, ManifestMalformed):
        return [Finding(
            "ERROR", "HARNESS", MANIFEST_FILENAME,
            f"manifest is malformed ({manifest_state.detail}) — this "
            "wiki's harness state cannot be trusted; run 'upgrade "
            "--adopt' to regenerate it.")]
    findings = []
    for drift in diff_manifest(manifest_state.recorded, manifest_state.actual):
        role = manifest_state.recorded[drift.path]["role"]
        if role in ("managed", "template"):
            if drift.status == "missing":
                findings.append(Finding(
                    "ERROR", "HARNESS", drift.path,
                    "managed file missing — harness is incomplete; "
                    "re-run upgrade or re-init."))
            elif drift.status == "hash_mismatch":
                expected = manifest_state.recorded[drift.path]["sha256"]
                found = manifest_state.actual[drift.path]
                findings.append(Finding(
                    "ERROR", "HARNESS", drift.path,
                    "local edit conflicts with library-managed content "
                    f"(expected sha256 {expected}, found sha256 {found}) "
                    "— this file is harness-owned; run 'upgrade "
                    f"--adopt-drift {drift.path}' if this is intentional, "
                    f"or 'git checkout -- {drift.path}' to discard it."))
        elif role == "instance-fork" and drift.status == "hash_mismatch":
            findings.append(Finding(
                "WARN", "HARNESS", drift.path,
                f"forked from wiki-harness at v{manifest_state.harness_version}; "
                "local edits are permanent and will not receive future "
                "updates."))
    return findings


def run(files, changes):
    """Loads the schema once here so check_card_citations() can be
    schema-driven; check_cards() still loads it a second time itself, since
    it is the one that must independently report a CARD_SCHEMA finding when
    the schema is missing or malformed."""
    schema, _ = load_schema(files.get(SCHEMA_PATH))
    findings = []
    for check in (check_broken_links, check_orphans):
        findings += check(files)
    findings += check_card_citations(files, schema)
    for check in (check_cards, check_frontmatter, check_index_sync):
        findings += check(files)
    findings += check_raw_immutability(changes)
    return findings


def parse_name_status(stdout):
    """Parse `git diff --name-status` output into (status, path) pairs.

    Rename lines (R###<TAB>old<TAB>new) are modeled as a delete of the old
    path plus an add of the new path, so a file renamed OUT of sources/raw/
    still trips the immutability check, while a file renamed INTO
    sources/raw/ is treated as an arrival (allowed), not a false-positive
    modify/rename of an existing raw file."""
    changes = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            changes.append(("D", parts[1]))
            changes.append(("A", parts[2]))
        elif len(parts) == 2:
            changes.append((parts[0], parts[1]))
    return changes


# ---- impure edges below this line ----

def scan(root):
    """Read the wiki tree from disk. Returns (files, encoding_findings).

    md/index/card files are decoded as utf-8-sig so a leading UTF-8 BOM is
    stripped before parse_frontmatter ever sees the text. A file that fails
    to decode as UTF-8 is reported as an ENCODING finding instead of raising
    — raw/ files stay existence-only and are never decoded, so they can't
    produce one. AGENTS.md files are read so their links get checked, but
    _wiki_pages/_cards exclude them: they are rules, not wiki content."""
    files = {}
    encoding_findings = []
    for pattern in ("index.md", "AGENTS.md", "VISION.md", "sources/AGENTS.md",
                    "sources/cards/card-schema.json", "sources/cards/recipes.md",
                    "wiki/**/*.md", "sources/cards/*.md"):
        for f in root.glob(pattern):
            if f.is_file():
                rel = f.relative_to(root).as_posix()
                try:
                    files[rel] = f.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    encoding_findings.append(Finding("ERROR", "ENCODING", rel,
                                                     "file is not valid UTF-8"))
    raw_dir = root / "sources" / "raw"
    if raw_dir.is_dir():
        for f in raw_dir.rglob("*"):
            if f.is_file():
                files[f.relative_to(root).as_posix()] = ""
    return files, encoding_findings


def git_changes(root):
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "HEAD", "--name-status"],
        capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return parse_name_status(result.stdout)


def hooks_finding(root):
    """In a git work tree, require core.hooksPath == .githooks so the
    commit-msg format check actually runs. Non-git roots (test fixtures)
    skip this check entirely."""
    is_worktree = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True)
    if is_worktree.returncode != 0:
        return []
    hooks_path = subprocess.run(
        ["git", "-C", str(root), "config", "--get", "core.hooksPath"],
        capture_output=True, text=True)
    if hooks_path.stdout.strip() != ".githooks":
        return [Finding("ERROR", "HOOKS", ".githooks",
                        "commit hook not active - run: git config core.hooksPath .githooks")]
    return []


def _manifest_shape_error(manifest):
    """Pure. Returns a short, human-readable reason `manifest` (an
    already-JSON-parsed dict) cannot be trusted as a files->role/sha256
    ledger, or None when its shape is usable. Mirrors load_schema()'s
    (card_frontmatter_lint.py) all-or-nothing validation: a manifest with
    even one malformed "files" entry is treated as fully untrustworthy --
    there is no principled way to trust the OTHER entries once the ledger
    itself is shown to be unreliable, e.g. by a hand edit or a partial
    migration. Also rejects a 'role' value that is not one of
    manifest.VALID_ROLES (manifest.is_valid_role()) -- check_harness()'s
    if/elif role chain has no branch for an unrecognized role, so letting
    one through here would silently swallow any real drift on that path
    instead of failing closed."""
    recorded = manifest.get("files")
    if not isinstance(recorded, dict):
        return "'files' is missing or not an object"
    for path, entry in recorded.items():
        if not isinstance(entry, dict) or "role" not in entry or "sha256" not in entry:
            return f"files entry {path!r} is missing 'role' or 'sha256'"
        if not is_valid_role(entry["role"]):
            return f"files entry {path!r} has unknown role {entry['role']!r}"
    return None


def read_harness_manifest(root):
    """Impure edge, mirroring hooks_finding(root): reads
    .wiki-harness-manifest.json directly off disk and, independent of
    scan()'s decoded files dict, reads raw bytes (manifest.hash_tree()'s
    Path.read_bytes()) of every path the manifest lists with a role
    check_harness() judges -- managed/template (the harness-owned content
    it can flag as drifted/missing) and instance-fork (the once-managed
    content it can flag as permanently forked) -- so a HARNESS finding is
    never masked by scan()'s UTF-8 decoding or its file-pattern globs.
    Returns None when the manifest file itself does not exist, or a
    ManifestMalformed when it exists but is not valid, trustworthy JSON --
    a truncated write (manifest.write_manifest() is a plain non-atomic
    Path.write_text()) or a hand edit must fail closed here, not raise.
    This includes bytes that are not valid UTF-8 at all: read_manifest()
    decodes with Path.read_text(encoding="utf-8") before ever parsing
    JSON, so that decode step's UnicodeDecodeError must fail closed here
    too, not just json.JSONDecodeError."""
    root = Path(root)
    try:
        manifest = read_manifest(root / MANIFEST_FILENAME)
    except json.JSONDecodeError as exc:
        return ManifestMalformed(f"invalid JSON: {exc}")
    except UnicodeDecodeError as exc:
        return ManifestMalformed(f"invalid UTF-8: {exc}")
    if manifest is None:
        return None
    shape_error = _manifest_shape_error(manifest)
    if shape_error is not None:
        return ManifestMalformed(shape_error)
    recorded = manifest["files"]
    hashed_paths = [path for path, entry in recorded.items()
                    if entry.get("role") in ("managed", "template", "instance-fork")]
    actual = hash_tree(root, hashed_paths)
    return ManifestState(manifest.get("harness_version", ""), recorded, actual)


def main(argv):
    root = Path(argv[argv.index("--root") + 1]) if "--root" in argv \
        else Path(__file__).resolve().parent.parent
    files, enc = scan(root)
    findings = run(files, git_changes(root)) + enc
    findings += hooks_finding(root)
    findings += check_harness(read_harness_manifest(root))
    for f in sorted(findings):
        print(f"{f.severity} {f.code} {f.path}: {f.message}")
    errors = sum(1 for f in findings if f.severity == "ERROR")
    print(f"lint: {errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
