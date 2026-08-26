#!/usr/bin/env python3
"""Compute and diff the one integrity ledger (.wiki-harness-manifest.json):
per-path role + sha256 for every MANAGED/TEMPLATE file, plus the run's
harness_version/source_ref/source_commit/source_url/vars metadata (plan-v3
section 2.4).

Pure core: compute_manifest()/diff_manifest()/is_valid_role() take
already-computed data in and return dicts/lists out -- they never open a
file, run git, or read the clock. Impure edges: hash_bytes()/hash_tree()
(reads bytes off disk) and read_manifest()/write_manifest() (reads/writes
.wiki-harness-manifest.json) at the bottom.

Never decides what to do about drift (abort, --adopt-drift, print) -- that
decision belongs to upgrade.py (T16), which calls diff_manifest() and
branches on its pure result.
"""
from __future__ import annotations

import hashlib
import json
from collections import namedtuple
from pathlib import Path

LIBRARY = "wiki-harness"

# The four ownership classes (ref-ownership-classes) plus "instance-fork"
# (written only by a future --adopt-drift, T18) and "removed" -- reserved,
# unused by any caller in this task, for a future MAJOR version's
# path-removal mechanism (plan-v3 Not-now item 13) -- reserving the enum
# value now means that later addition needs no breaking manifest-schema
# change.
VALID_ROLES = frozenset({"managed", "template", "instance-fork", "removed"})

# status: "match" (hash agrees) | "hash_mismatch" (path present in both,
# hash differs) | "missing" (path recorded but absent from the actual map)
Drift = namedtuple("Drift", "path status")


def is_valid_role(role):
    """Pure. True iff `role` is one of the reserved manifest role values,
    whether or not any caller in this task actually produces it yet."""
    return role in VALID_ROLES


def compute_manifest(hashes, vars, source_url, harness_version, source_ref,
                     source_commit, *, initialised_at):
    """Pure. Builds and returns the exact manifest dict shape plan-v3
    section 2.4 specifies.

    `hashes` is an already-computed {path: {"role": <role>, "sha256": <hex>}}
    map covering exactly the MANAGED/TEMPLATE (or already-adopted/removed)
    paths -- never SEEDED/INSTANCE (plan-v3 section 2.4: "files covers
    exactly MANAGED + TEMPLATE paths"). This function never hashes a file
    itself and never reads the clock -- `initialised_at` arrives as a plain
    string, computed by the caller's own I/O edge.

    Raises ValueError if any entry's role is not one of VALID_ROLES --
    persisting an unrecognized role would silently corrupt the ledger every
    later diff_manifest()/upgrade() call reads back.
    """
    files = {}
    for path in sorted(hashes):
        entry = hashes[path]
        role = entry["role"]
        if not is_valid_role(role):
            raise ValueError(f"unknown role {role!r} for path {path!r}")
        files[path] = {"role": role, "sha256": entry["sha256"]}
    return {
        "library": LIBRARY,
        "harness_version": harness_version,
        "source_ref": source_ref,
        "source_commit": source_commit,
        "source_url": source_url,
        "initialised_at": initialised_at,
        "vars": dict(vars),
        "files": files,
    }


def diff_manifest(recorded, actual):
    """Pure. `recorded` is a manifest's "files" map ({path: {"role": ...,
    "sha256": ...}}); `actual` is a freshly recomputed {path: sha256} for
    the same set of paths (the impure edge hash_tree() below builds one).

    Returns a list[Drift], one entry per path in `recorded`, sorted by
    path: "missing" when the path is recorded but absent from `actual`
    (e.g. deleted on disk since the manifest was written) -- distinct from
    "hash_mismatch", where the path is present in both but the bytes
    disagree -- and "match" otherwise. A path present in `actual` but
    absent from `recorded` is out of scope for this function entirely (it
    is not yet part of the ledger) and is ignored.
    """
    drifts = []
    for path in sorted(recorded):
        recorded_hash = recorded[path]["sha256"]
        if path not in actual:
            drifts.append(Drift(path, "missing"))
        elif actual[path] != recorded_hash:
            drifts.append(Drift(path, "hash_mismatch"))
        else:
            drifts.append(Drift(path, "match"))
    return drifts


# ---- impure edges below this line ----

def hash_bytes(data):
    """Impure-adjacent (no filesystem access, but named alongside the I/O
    edges since it is the primitive they both use): sha256 over raw bytes,
    never over decoded/re-encoded text, so this agrees byte-for-byte with
    whatever independently hashes the same file elsewhere (e.g. lint.py's
    HARNESS check, T11)."""
    return hashlib.sha256(data).hexdigest()


def hash_tree(root, paths):
    """Impure edge. Reads each of `paths` (relative to `root`) off disk via
    Path.read_bytes() and returns {path: sha256}. A path that does not
    exist on disk is simply absent from the returned map -- diff_manifest()
    is what reports that absence, as "missing", not this function raising."""
    root = Path(root)
    hashes = {}
    for path in paths:
        f = root / path
        if f.is_file():
            hashes[path] = hash_bytes(f.read_bytes())
    return hashes


def read_manifest(path):
    """Impure edge. Returns the parsed manifest dict, or None when `path`
    does not exist."""
    p = Path(path)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_manifest(path, manifest):
    """Impure edge. Serializes `manifest` as JSON (2-space indent, key
    order exactly as compute_manifest() built it, trailing newline) and
    writes it to `path`."""
    Path(path).write_text(json.dumps(manifest, indent=2) + "\n",
                          encoding="utf-8")
