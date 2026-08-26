#!/usr/bin/env python3
"""Bring an existing wiki instance forward to a newer (or, with
--allow-downgrade, older) harness release in place (plan-v3 section 3.2).

Pure core: parse_semver()/compare_semver()/highest_semver_tag()/
parse_ls_remote_tags()/check_message() take already-fetched data in and
return a value out -- they never run git, touch the clock, or read the
filesystem. Impure edges: ls_remote_tags() (runs `git ls-remote --tags`),
run_check(), and main() (read the manifest off disk, print, exit) at the
bottom.

This module currently implements only --check (T15): a standalone, no-write,
one-round-trip remote-tag comparison against the manifest's harness_version.
Every other flag and ordered step in plan-v3 section 3.2 (drift check,
promote, --adopt, ...) lands in later tasks (T16 onward) -- see plan-v3.md's
task table.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from manifest import read_manifest  # noqa: E402  (needs the sys.path line above)

MANIFEST_FILENAME = ".wiki-harness-manifest.json"

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

# --check's one round trip must stay bounded: a remote that is reachable
# but never responds (firewall drop, network black hole, stalled VPN path)
# must be reported as unreachable within this many seconds, never left to
# hang indefinitely.
LS_REMOTE_TIMEOUT_SECONDS = 10


def parse_semver(tag):
    """Pure. Parses a 'vX.Y.Z' or 'X.Y.Z' string into a (major, minor,
    patch) int tuple usable for ordering, or returns None for anything that
    doesn't match (a non-semver tag -- e.g. a release-candidate suffix, or
    an unrelated branch-name-shaped ref -- is simply ignored by every
    caller here, never raises). This includes a non-string `tag` (e.g. a
    manifest's harness_version field read back as JSON null): a caller
    such as check_message() feeds this whatever the manifest recorded,
    unvalidated, so a type mismatch here must return None exactly like an
    ill-formed string, never raise a TypeError out of the regex match."""
    if not isinstance(tag, str):
        return None
    m = SEMVER_RE.match(tag)
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def compare_semver(a, b):
    """Pure. Classic three-way comparator over two already-parsed semver
    tuples: -1 if a<b, 0 if equal, 1 if a>b. Shared by --check (this task)
    and the downgrade guard (T17) -- one shared, pure helper, per the T15
    brief."""
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def highest_semver_tag(tags):
    """Pure. Returns the tag string (verbatim, as given in `tags`) whose
    parsed semver is highest, ignoring any entry that isn't well-formed
    semver. Returns None if none of `tags` parses."""
    best_tag = None
    best_parsed = None
    for tag in tags:
        parsed = parse_semver(tag)
        if parsed is None:
            continue
        if best_parsed is None or compare_semver(parsed, best_parsed) > 0:
            best_tag = tag
            best_parsed = parsed
    return best_tag


def parse_ls_remote_tags(output):
    """Pure. Extracts tag names out of `git ls-remote --tags`'s raw stdout
    text (the impure edge ls_remote_tags() below captures it as `output`):
    each line is '<sha>\\trefs/tags/<name>', and an annotated tag also
    emits a second '<sha>\\trefs/tags/<name>^{}' line for the commit object
    it points at -- the '^{}' suffix is stripped so both lines yield the
    same tag name (a resulting duplicate is harmless to every caller here,
    which only ever cares about the highest tag, never a count)."""
    tags = []
    prefix = "refs/tags/"
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        ref = parts[1]
        if not ref.startswith(prefix):
            continue
        name = ref[len(prefix):]
        if name.endswith("^{}"):
            name = name[:-3]
        tags.append(name)
    return tags


def check_message(local_version, tags):
    """Pure. `local_version` is the manifest's recorded harness_version
    (e.g. "1.0.0"); `tags` is the list of raw tag name strings the impure
    edge fetched (ls_remote_tags()'s/parse_ls_remote_tags()'s return
    value). Returns the exact message --check prints, per plan-v3 section
    3.2: "up to date at vX.Y.Z" when no remote tag's semver exceeds the
    local version (or no remote tag is well-formed semver at all), else
    the exact "vY.Z.W available -- run `upgrade --to vY.Z.W --apply`"
    message naming the highest one.

    When `local_version` is missing or not well-formed semver, no
    comparison against `tags` is possible either way -- claiming "up to
    date" here would fabricate a result nobody actually computed, even
    when the remote genuinely carries a newer release. This case is
    surfaced explicitly instead, still under the module's unchanged exit-0
    contract (only an unreachable remote/checkout exits 1)."""
    local_parsed = parse_semver(local_version)
    if local_parsed is None:
        return (
            f"upgrade --check: local harness_version {local_version!r} is "
            "not valid semver -- cannot determine whether an upgrade is "
            "available")
    highest = highest_semver_tag(tags)
    highest_parsed = parse_semver(highest) if highest is not None else None
    if highest_parsed is not None and compare_semver(highest_parsed, local_parsed) > 0:
        remote_display = "v{}.{}.{}".format(*highest_parsed)
        return f"{remote_display} available -- run `upgrade --to {remote_display} --apply`"
    local_display = "v{}.{}.{}".format(*local_parsed)
    return f"up to date at {local_display}"


# ---- impure edges below this line ----

def ls_remote_tags(source_url):
    """Impure edge. Runs `git ls-remote --tags <source_url>` -- upgrade
    --check's one round trip (a local filesystem checkout path or a real
    remote URL are both valid arguments to git ls-remote; no fetch of file
    content, no scratch copy, no write, ever). Returns the parsed tag name
    list on success, or None when the remote/checkout is unreachable --
    either a non-zero exit (unknown host, missing path, network failure) or
    a reachable-but-unresponsive remote that fails to answer within
    LS_REMOTE_TIMEOUT_SECONDS (firewall drop, network black hole, stalled
    VPN path)."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", str(source_url)],
            capture_output=True, text=True, timeout=LS_REMOTE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    return parse_ls_remote_tags(result.stdout)


def run_check(target):
    """Impure edge: --check's entire standalone flow (plan-v3 section
    3.2). Reads the local manifest's harness_version/source_url, fetches
    remote tags, prints the exact message check_message() computes, and
    returns the process exit code -- 1 only when the remote/checkout was
    unreachable OR the manifest itself could not be trusted, 0 in every
    other case. Never fetches file content, never writes anything.

    A manifest that exists but is not syntactically valid JSON (a
    truncated write, a hand edit) or that parses but is not a JSON object
    (e.g. a bare array/string/number) must fail closed here with the same
    clean error-message-plus-exit-1 pattern this function already uses
    for an unreachable remote (ls_remote_tags()'s own explicit
    try/except around TimeoutExpired) -- never an uncaught
    JSONDecodeError/AttributeError traceback out of read_manifest()'s
    json.loads() or this function's own manifest.get() field access."""
    manifest_path = Path(target) / MANIFEST_FILENAME
    if not manifest_path.is_file():
        print(f"upgrade --check: manifest {str(manifest_path)!r} is missing — this "
              "wiki was not initialised with wiki-harness; run 'upgrade --adopt' to "
              "generate one", file=sys.stderr)
        return 1
    try:
        manifest = read_manifest(manifest_path)
    except json.JSONDecodeError as exc:
        print(f"upgrade --check: manifest {str(manifest_path)!r} is not "
              f"valid JSON ({exc})", file=sys.stderr)
        return 1
    if manifest is not None and not isinstance(manifest, dict):
        print(f"upgrade --check: manifest {str(manifest_path)!r} is not a "
              "JSON object", file=sys.stderr)
        return 1
    local_version = manifest.get("harness_version", "") if manifest else ""
    source_url = manifest.get("source_url", "") if manifest else ""
    tags = ls_remote_tags(source_url)
    if tags is None:
        print(f"upgrade --check: remote {source_url!r} is unreachable", file=sys.stderr)
        return 1
    print(check_message(local_version, tags))
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="upgrade.py")
    parser.add_argument("target")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    if args.check:
        # --check ignores every other flag and runs as an early, standalone
        # branch, before any of the ordered steps in plan-v3 section 3.2 --
        # none of which exist yet (T16 onward).
        return run_check(Path(args.target))
    print("upgrade.py: only --check is implemented so far", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
