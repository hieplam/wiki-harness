#!/usr/bin/env python3
"""Bring an existing wiki instance forward to a newer (or, with
--allow-downgrade, older) harness release in place (plan-v3 section 3.2).

Pure core: parse_semver()/compare_semver()/highest_semver_tag()/
parse_ls_remote_tags()/check_message() take already-fetched data in and
return a value out -- they never run git, touch the clock, or read the
filesystem. Impure edges: ls_remote_tags() (runs `git ls-remote --tags`),
run_check(), and main() (read the manifest off disk, print, exit) at the
bottom.

This module implements --check (T15) plus step 1 of the ordered upgrade
flow (T16): the clean-tree precondition, the manifest precondition, and the
refuse-before-write drift check over every manifest-recorded managed/
template path (a missing path counts as drift too, with its own distinct
message). All three gates run before any fetch or write.

T16B adds the core --apply write pipeline past those gates: resolve the
target version (step 6, --library-path or a real fetch/checkout),
scratch-copy the target tree (step 8), overwrite every managed/template
path in the scratch copy by reusing the resolved library checkout's own
init module (step 9 -- the single source of truth for the library->target
layout mapping, never duplicated here), compute and write the new manifest
into the scratch copy (Warchief amendment: step 9 addendum), lint the
scratch copy (step 10), promote-copy back to the real target with a bare
loop, excluding the manifest (step 11 -- T21 later wraps this exact loop in
try/except -> git checkout -- .), and write the new manifest to the real
target last (step 12). No guards yet: the downgrade guard (T17), the
--adopt-drift role-flip mechanism (T18), and the MAJOR-removal guard (T19)
all land on top of this pipeline in later tasks; see plan-v3.md's task
table.

Pure: is_clean_tree(), managed_template_files(), blocking_drifts(), and
format_drift_abort() take already-fetched data in and return a
predicate/dict/list/string out -- none of them run git, touch the clock, or
read the filesystem. Impure edges: git_status_porcelain(),
classify_manifest() (the single shared read-and-classify-the-manifest edge
behind both run_check() and read_manifest_for_upgrade()),
read_manifest_for_upgrade(), and run_upgrade() (the orchestrator that wires
porcelain -> clean predicate -> manifest read -> hash_tree -> diff_manifest
-> the pure blocking-drift decision -> print + exit code) at the bottom,
alongside run_check().
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from manifest import (  # noqa: E402
    compute_manifest, diff_manifest, hash_tree, read_manifest, write_manifest)

MANIFEST_FILENAME = ".wiki-harness-manifest.json"

# kind: "ok" (manifest holds the parsed dict) | "missing" | "invalid_json"
# (error holds the JSONDecodeError) | "invalid_utf8" (error holds the
# UnicodeDecodeError) | "non_object". Carries no message text and no exit
# code -- classify_manifest()'s callers each own their own presentation.
ManifestClassification = namedtuple("ManifestClassification", "kind manifest error")

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

# v3 (A3): this single message is the ENTIRE crash-recovery story -- no
# separate marker-file precondition, no --resume branch, anywhere. Quoted
# byte-for-byte in the T16 brief; reproduce it verbatim.
DIRTY_TREE_MESSAGE = (
    "commit or stash local changes before running upgrade -- if this "
    "follows an interrupted `upgrade --apply`, run `git checkout -- .` "
    "to discard the partial write and restore the pre-upgrade tree.")

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


def is_clean_tree(porcelain_output):
    """Pure. `porcelain_output` is git_status_porcelain()'s raw stdout
    (the impure edge below). True iff it indicates a clean working tree --
    `git status --porcelain` prints nothing at all (no leading/trailing
    whitespace either) for a clean tree, so any non-blank content is
    treated as dirty."""
    return porcelain_output.strip() == ""


def managed_template_files(files):
    """Pure. `files` is a manifest's "files" map ({path: {"role": ...,
    "sha256": ...}}). Returns the subset whose role is managed or
    template -- the only two roles step 1's drift check covers (plan-v3
    section 3.2); instance-fork/removed/any other recorded role is out of
    scope for this check entirely, exactly like check_harness() in
    lint.py."""
    return {path: entry for path, entry in files.items()
            if entry.get("role") in ("managed", "template")}


def blocking_drifts(drifts, adopt_drift_paths):
    """Pure. `drifts` is diff_manifest()'s list[Drift]; `adopt_drift_paths`
    is the set of paths named by --adopt-drift on this invocation. Returns
    the drifts that must abort this upgrade: any status other than "match"
    whose path was NOT named by --adopt-drift this run. (--adopt-drift
    itself does not yet flip the path's manifest role to instance-fork --
    that mechanism is T18; here it only suppresses the abort for this
    run.)"""
    adopt = set(adopt_drift_paths)
    return [d for d in drifts if d.status != "match" and d.path not in adopt]


def format_drift_abort(blocking, recorded, actual, harness_version):
    """Pure. `blocking` is blocking_drifts()'s output; `recorded` is a
    manifest's "files" map (or a role-filtered subset of it, e.g.
    managed_template_files()'s return value) covering every path named in
    `blocking`; `actual` is hash_tree()'s freshly-computed {path: sha256};
    `harness_version` is the manifest's recorded harness_version string.
    Returns the exact multi-line stderr message step 1 prints before
    aborting: a header stating nothing was fetched or written, then one
    line per drifted path naming the path, its expected-vs-actual hash (or
    the DISTINCT "file was deleted, expected to exist at v<X.Y.Z>."
    message when the drift is a missing path), and both remediation
    options (`git checkout -- <path>`, `upgrade --adopt-drift <path>`)."""
    lines = [
        "upgrade: refusing to proceed -- the following managed/template "
        "path(s) have drifted from the manifest; nothing was fetched or "
        "written:",
    ]
    for drift in blocking:
        if drift.status == "missing":
            detail = f"file was deleted, expected to exist at v{harness_version}."
        else:
            expected = recorded[drift.path]["sha256"]
            found = actual[drift.path]
            detail = f"expected sha256 {expected}, found sha256 {found}"
        lines.append(
            f"  {drift.path}: {detail} -- run `git checkout -- "
            f"{drift.path}` to discard the local change, or `upgrade "
            f"--adopt-drift {drift.path}` if this is intentional.")
    return "\n".join(lines)


def parse_to_version(to_arg):
    """Pure. Step 6/12: parses --to's raw value ('vX.Y.Z' or 'X.Y.Z') into
    (harness_version, source_ref) -- harness_version is the bare 'X.Y.Z'
    string the new manifest records, source_ref is always the 'vX.Y.Z' tag
    form (matching what a real git checkout in init.py's own
    read_source_ref() would record for a tagged release). Returns None for
    anything parse_semver() itself would reject; validating/erroring on
    that here is CLI polish (T24), out of scope for this task -- every
    fixture in this task's own tests always passes a well-formed --to."""
    parsed = parse_semver(to_arg)
    if parsed is None:
        return None
    harness_version = "{}.{}.{}".format(*parsed)
    return harness_version, f"v{harness_version}"


def merge_manifest_files(role_map, actual_hashes, old_files):
    """Pure. Step 12's manifest "files" input: every managed/template path
    step 9 just overwrote, hashed fresh in the scratch copy (`role_map` is
    the resolved library checkout's own build_role_map() output;
    `actual_hashes` is hash_tree()'s {path: sha256} over those same paths,
    mirroring init.py's own build_role_map()+hash_tree() pairing) -- plus
    every OLD instance-fork path carried over UNCHANGED, keeping its role
    and its recorded PRE-upgrade hash (no instance-fork paths exist yet at
    this point in the build -- T18 adds that role -- this still preserves
    the general shape for when it does, per the Warchief amendment's
    step-9 addendum)."""
    files = {path: {"role": role, "sha256": actual_hashes[path]}
             for path, role in role_map.items()}
    for path, entry in old_files.items():
        if entry.get("role") == "instance-fork":
            files[path] = {"role": "instance-fork", "sha256": entry["sha256"]}
    return files


# ---- impure edges below this line ----

def classify_manifest(manifest_path):
    """Impure edge: reads `manifest_path` off disk ONCE and classifies it
    into exactly one of the four failure modes {missing, invalid_json,
    invalid_utf8, non_object} or success -- the single shared classification
    ladder behind both run_check() (T15) and read_manifest_for_upgrade()
    (T16), which each map this structural result onto their own message
    wording, print-vs-return presentation, and exit-code-vs-tuple
    presentation. Never lets a JSONDecodeError/UnicodeDecodeError escape as
    a traceback; carries no message text and no exit code of its own."""
    if not manifest_path.is_file():
        return ManifestClassification("missing", None, None)
    try:
        manifest = read_manifest(manifest_path)
    except json.JSONDecodeError as exc:
        return ManifestClassification("invalid_json", None, exc)
    except UnicodeDecodeError as exc:
        return ManifestClassification("invalid_utf8", None, exc)
    if not isinstance(manifest, dict):
        return ManifestClassification("non_object", None, None)
    return ManifestClassification("ok", manifest, None)


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
    classification = classify_manifest(manifest_path)
    if classification.kind == "missing":
        print(f"upgrade --check: manifest {str(manifest_path)!r} is missing — this "
              "wiki was not initialised with wiki-harness; run 'upgrade --adopt' to "
              "generate one", file=sys.stderr)
        return 1
    if classification.kind == "invalid_json":
        print(f"upgrade --check: manifest {str(manifest_path)!r} is not "
              f"valid JSON ({classification.error})", file=sys.stderr)
        return 1
    if classification.kind == "invalid_utf8":
        print(f"upgrade --check: manifest {str(manifest_path)!r} is not "
              f"valid UTF-8 ({classification.error})", file=sys.stderr)
        return 1
    if classification.kind == "non_object":
        print(f"upgrade --check: manifest {str(manifest_path)!r} is not a "
              "JSON object", file=sys.stderr)
        return 1
    manifest = classification.manifest
    local_version = manifest.get("harness_version", "") if manifest else ""
    source_url = manifest.get("source_url", "") if manifest else ""
    tags = ls_remote_tags(source_url)
    if tags is None:
        print(f"upgrade --check: remote {source_url!r} is unreachable", file=sys.stderr)
        return 1
    print(check_message(local_version, tags))
    return 0


def git_status_porcelain(target):
    """Impure edge. Runs `git status --porcelain` in `target` and returns
    its raw stdout (never raises on a non-zero exit -- there is no test
    coverage or brief requirement for a target that is not a git work tree
    at all, so this stays exactly as thin as the brief specifies: "a new
    edge ... returning its raw output")."""
    result = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain"],
        capture_output=True, text=True)
    return result.stdout


def read_manifest_for_upgrade(manifest_path):
    """Impure edge. Reads and parses `manifest_path`, mirroring run_check's
    existing fail-closed pattern (T15) for a missing, unparseable,
    non-UTF-8, or non-object manifest -- extended here to cover step 2's
    manifest precondition. Returns (manifest_dict, None) on success, or
    (None, <one-line error message>) for every failure mode, never letting
    a JSONDecodeError/UnicodeDecodeError escape as a traceback."""
    classification = classify_manifest(manifest_path)
    if classification.kind == "missing":
        return None, (
            f"upgrade: manifest {str(manifest_path)!r} is missing — this "
            "wiki was not initialised with wiki-harness; pass --adopt to "
            "adopt it")
    if classification.kind == "invalid_json":
        return None, (f"upgrade: manifest {str(manifest_path)!r} is not "
                      f"valid JSON ({classification.error})")
    if classification.kind == "invalid_utf8":
        return None, (f"upgrade: manifest {str(manifest_path)!r} is not "
                      f"valid UTF-8 ({classification.error})")
    if classification.kind == "non_object":
        return None, (f"upgrade: manifest {str(manifest_path)!r} is not a "
                      "JSON object")
    return classification.manifest, None


def resolve_library_checkout(version, library_path):
    """Impure edge (step 6). If `library_path` is given, use it directly --
    the caller supplies a checkout already positioned at the target
    version; no network is ever touched on this branch. Otherwise, fetch
    and check out the target tag in this library's own checkout (the
    directory upgrade.py itself lives in -- exactly like init.py's
    library_root = Path(__file__).resolve().parent): `git -C <checkout>
    fetch --tags && git -C <checkout> checkout v<X.Y.Z>` (plan-v3 section
    3.2 step 6). No test in this task exercises this else-branch -- every
    fixture drives the pipeline via --library-path against a local fixture
    library git repo instead."""
    if library_path is not None:
        return Path(library_path)
    checkout = Path(__file__).resolve().parent
    subprocess.run(["git", "-C", str(checkout), "fetch", "--tags"],
                   capture_output=True, text=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", f"v{version}"],
                   capture_output=True, text=True)
    return checkout


def load_init_module(library_root):
    """Impure edge. Dynamically imports the resolved library checkout's
    OWN init.py as a module object -- never this process's already-
    imported init.py, if any -- so step 9's copy_scripts()/copy_hooks()/
    render_root_templates()/copy_managed_agents()/seed_claude_stubs()/
    build_role_map()/read_source_commit() and its MANAGED_STATIC_PATHS/
    TEMPLATE_STATIC_PATHS/MANAGED_COPY_MAP/CLAUDE_NESTED_PATHS constants
    are always exactly the TARGET version's, reusing init.py's own
    library->target layout mapping rather than a second, hand-maintained
    copy of it here."""
    spec = importlib.util.spec_from_file_location(
        "wiki_harness_upgrade_target_init", str(Path(library_root) / "init.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_target_to_scratch(target):
    """Impure edge (step 8). Copies the target wiki tree -- everything
    except .git -- into a brand-new tempfile.mkdtemp() scratch dir. Every
    subsequent write in this run happens here, never the real target,
    until step 11 promotes. tempfile.mkdtemp() is always a fresh,
    independent path, so the scratch copy can never land inside the real
    target's own working tree or its .git."""
    scratch_root = Path(tempfile.mkdtemp(prefix="wiki-harness-upgrade-"))
    scratch = scratch_root / "scratch"
    shutil.copytree(Path(target), scratch, ignore=shutil.ignore_patterns(".git"))
    return scratch


def overwrite_scratch(init_mod, library_root, scratch, values):
    """Impure edge (step 9). Overwrites every managed/template path in the
    scratch copy by calling back into the resolved library checkout's own
    init module -- the single source of truth for the library->target
    layout mapping -- rather than a second, hand-maintained copy of it
    here. Returns (scripts_paths, hooks_paths) so the caller can build the
    exact same role map init.py itself builds (init_mod.build_role_map()).
    seed_starters()/create_gitkeeps()/git_init() are never called -- those
    write seeded/instance paths, which an upgrade must never touch."""
    scripts_paths = init_mod.copy_scripts(library_root, scratch)
    hooks_paths = init_mod.copy_hooks(library_root, scratch)
    init_mod.render_root_templates(library_root, scratch, values)
    init_mod.copy_managed_agents(library_root, scratch)
    init_mod.seed_claude_stubs(library_root, scratch)
    return scripts_paths, hooks_paths


def run_scratch_lint(scratch):
    """Impure edge (step 10). Runs `python3 <scratch>/scripts/lint.py
    --root <scratch>` and returns (ok, output) -- output is stdout+stderr
    combined, so a caller that aborts on failure can print exactly what
    lint.py found."""
    result = subprocess.run(
        [sys.executable, str(Path(scratch) / "scripts" / "lint.py"),
         "--root", str(scratch)],
        capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def promote_scratch(scratch, target):
    """Impure edge (step 11). A BARE copy loop -- no try/except, T21 adds
    that later so its own brief's monkeypatch-this-loop framing has
    something concrete to wrap. Copies every file whose bytes differ
    between the scratch copy and the real target (or that is absent from
    the real target) from scratch back over the real target -- EXCLUDING
    .wiki-harness-manifest.json (the Warchief amendment: the scratch's
    manifest is never promoted wholesale; step 12 writes the real manifest
    separately, last)."""
    scratch = Path(scratch)
    target = Path(target)
    for src in sorted(scratch.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(scratch)
        if rel.as_posix() == MANIFEST_FILENAME:
            continue
        dst = target / rel
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())


def run_upgrade(target, adopt, adopt_drift_paths, to, library_path):
    """Impure edge: the orchestrator for every ordered step 3.2 gate this
    task implements. Wires git_status_porcelain() -> is_clean_tree()
    (precondition 1, exit 2) -> read_manifest_for_upgrade() (precondition
    2, exit 1 unless --adopt suppresses it) -> hash_tree()/diff_manifest()
    -> blocking_drifts()/format_drift_abort() (step 1, exit 1) -> the core
    apply pipeline (T16B): resolve_library_checkout() (step 6) ->
    copy_target_to_scratch() (step 8) -> overwrite_scratch() (step 9) ->
    compute_manifest()/write_manifest() into the scratch (the Warchief
    amendment's step-9 addendum) -> run_scratch_lint() (step 10, exit 1 on
    failure, real target untouched) -> promote_scratch() (step 11, bare
    loop, no rollback yet) -> write_manifest() to the real target LAST
    (step 12).

    `to` is --to's raw value ('vX.Y.Z'); `library_path` is --library-path
    or None. No downgrade/adopt-drift-role-flip/MAJOR-removal guard and no
    dry-run/--apply branch here -- those are later tasks' jobs (T17-T20);
    every caller of this function today always means "write".

    When --adopt is passed and the manifest precondition would otherwise
    fail (missing/unparseable/non-object/non-UTF-8), the adoption
    mechanism itself is out of scope for this task (T16 brief, "explicitly
    OUT of scope") -- this is reported as not-yet-implemented too, rather
    than either crashing or silently fabricating a manifest."""
    porcelain = git_status_porcelain(target)
    if not is_clean_tree(porcelain):
        print(DIRTY_TREE_MESSAGE, file=sys.stderr)
        return 2

    manifest_path = Path(target) / MANIFEST_FILENAME
    manifest, error = read_manifest_for_upgrade(manifest_path)
    if error is not None:
        if not adopt:
            print(error, file=sys.stderr)
            return 1
        print("upgrade: --adopt without an existing, valid manifest is "
              "not yet implemented", file=sys.stderr)
        return 3

    harness_version = manifest.get("harness_version", "")
    recorded = managed_template_files(manifest.get("files", {}))
    actual = hash_tree(target, recorded.keys())
    drifts = diff_manifest(recorded, actual)
    blocking = blocking_drifts(drifts, adopt_drift_paths)
    if blocking:
        print(format_drift_abort(blocking, recorded, actual, harness_version),
              file=sys.stderr)
        return 1

    new_harness_version, new_source_ref = parse_to_version(to)

    library_root = resolve_library_checkout(new_harness_version, library_path)
    init_mod = load_init_module(library_root)

    scratch = copy_target_to_scratch(target)
    values = manifest.get("vars", {})
    scripts_paths, hooks_paths = overwrite_scratch(
        init_mod, library_root, scratch, values)
    role_map = init_mod.build_role_map(scripts_paths, hooks_paths)
    actual_hashes = hash_tree(scratch, sorted(role_map))
    new_source_commit = init_mod.read_source_commit(library_root)
    new_files = merge_manifest_files(role_map, actual_hashes, manifest.get("files", {}))
    new_manifest = compute_manifest(
        new_files, values, manifest.get("source_url", ""), new_harness_version,
        new_source_ref, new_source_commit,
        initialised_at=manifest.get("initialised_at", ""))
    write_manifest(scratch / MANIFEST_FILENAME, new_manifest)         # step 9 addendum

    lint_ok, lint_output = run_scratch_lint(scratch)                  # step 10
    if not lint_ok:
        print(lint_output, file=sys.stderr)
        return 1

    promote_scratch(scratch, target)                                 # step 11
    write_manifest(Path(target) / MANIFEST_FILENAME, new_manifest)    # step 12
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="upgrade.py")
    parser.add_argument("target")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--to")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--adopt", action="store_true")
    parser.add_argument("--adopt-drift", action="append", default=[])
    parser.add_argument("--library-path")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    if args.check:
        # --check ignores every other flag and runs as an early, standalone
        # branch, before any of the ordered steps in plan-v3 section 3.2.
        return run_check(Path(args.target))
    return run_upgrade(Path(args.target), args.adopt, args.adopt_drift,
                       args.to, args.library_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
