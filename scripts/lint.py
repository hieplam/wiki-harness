#!/usr/bin/env python3
"""Mechanical lint for the OGP wiki (spec §7.1).

Pure core: parse/extract/resolve helpers and check_* functions (data in →
Findings out). Impure edges: scan()/git_changes()/main() at the bottom.
Python 3 stdlib only.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card_frontmatter_lint import (  # noqa: E402  (needs the sys.path line above)
    SCHEMA_PATH, Finding, check_card, load_schema, parse_frontmatter, resolve)

CARD_ID_RE = re.compile(r"src-\d{4}-\d{2}-\d{2}-\d{3}")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


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
            and PurePosixPath(p).name != "AGENTS.md"]


def _cards(files):
    return [p for p in files if p.startswith("sources/cards/") and p.endswith(".md")
            and PurePosixPath(p).name != "AGENTS.md"]


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


def check_card_citations(files):
    findings = []
    card_ids = {PurePosixPath(p).stem for p in _cards(files)}
    cited = set()
    for path in sorted(_wiki_pages(files)):
        for cid in sorted(set(CARD_ID_RE.findall(files[path]))):
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


def run(files, changes):
    findings = []
    for check in (check_broken_links, check_orphans, check_card_citations,
                  check_cards, check_frontmatter, check_index_sync):
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
                    "sources/cards/card-schema.json",
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


def main(argv):
    root = Path(argv[argv.index("--root") + 1]) if "--root" in argv \
        else Path(__file__).resolve().parent.parent
    files, enc = scan(root)
    findings = run(files, git_changes(root)) + enc
    findings += hooks_finding(root)
    for f in sorted(findings):
        print(f"{f.severity} {f.code} {f.path}: {f.message}")
    errors = sum(1 for f in findings if f.severity == "ERROR")
    print(f"lint: {errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
