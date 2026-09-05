#!/usr/bin/env python3
"""Stamp a brand-new wiki instance from scratch: scaffold, seed, hooks
wired, first commit made -- so a fresh wiki is immediately lint-clean and
ready to ingest, in one `python3 wiki-harness/init.py <target-dir> [flags]`
invocation (plan-v3 section 3.1, 16 ordered steps).

No --ci flag, no CI workflow, no upgrade-in-progress marker, no --resume
(A3, A4) -- none of that exists anywhere in this module. CLAUDE.md (root)
and its three nested stubs are seeded as ordinary MANAGED, TRACKED files
(v3/A7), hashed into the manifest alongside every other MANAGED/TEMPLATE
path.

Pure core: resolve_target_refusal(), missing_required_vars(),
apply_defaults(), parse_origins(), parse_answers_file(), merge_answers(),
apply_origins(), build_role_map(), commit_subject(), render(),
summary_text() -- plain data
in, plain data/decision out, no filesystem/subprocess/clock access. Impure
edges: every function below the "impure edges" marker (filesystem writes,
git/subprocess calls, the clock, interactive prompts, --answers-file
reads). main() is the orchestrator that calls the pure decisions and the
impure edges in the 16-step order plan-v3 section 3.1 specifies.

Python 3 stdlib only.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from manifest import compute_manifest, hash_tree, write_manifest  # noqa: E402

MANIFEST_FILENAME = ".wiki-harness-manifest.json"
# Written into every release payload by tools/build_release.py; absent
# from a git checkout, which answers the same questions with git.
RELEASE_METADATA_FILENAME = "RELEASE.json"

# Every variable the TEMPLATE-class sources substitute. `REQUIRED_VARS` is
# the subset a caller must actually answer; `DEFAULTED_VARS` is the subset
# apply_defaults() derives when the caller leaves it empty (v1.2.0 -- before
# that release all four were required, and --non-interactive refused when
# any was missing).
TEMPLATE_VARS = ("wiki_title", "org_name", "content_language", "repo_name")
REQUIRED_VARS = ("wiki_title",)
DEFAULTED_VARS = ("org_name", "content_language", "repo_name")
DEFAULT_CONTENT_LANGUAGE = "English"
PROMPT_LABELS = {
    "wiki_title": "Wiki title",
    "org_name": "Organisation name",
    "content_language": "Content language",
    "repo_name": "Repository name",
}

REFUSAL_MESSAGE = ("target directory {path} is not empty; re-run with "
                   "--force to scaffold into it anyway.")

NO_INPUT_MESSAGE = (
    "no input available to answer {label!r}; re-run with --non-interactive "
    "(and --wiki-title) to take the defaults without prompting.")

# Every MANAGED path copied verbatim (no per-instance variables) whose
# library source is not scripts/*.py or .githooks/* (those two sets are
# discovered dynamically off disk by copy_scripts()/copy_hooks(), so
# scripts/manifest.py rides along automatically -- A8).
MANAGED_COPY_MAP = (
    ("sources.AGENTS.md", "sources/AGENTS.md"),
    ("wiki.AGENTS.md", "wiki/AGENTS.md"),
    ("sources.cards.AGENTS.md", "sources/cards/AGENTS.md"),
)

# Every SEEDED path written once, verbatim, at init time only.
SEED_COPY_MAP = (
    ("recipes.md", "sources/cards/recipes.md"),
    ("VISION.skeleton.md", "VISION.md"),
    ("index.md.header.tmpl", "index.md"),
    ("gitignore.snippet", ".gitignore"),
)

CLAUDE_NESTED_PATHS = ("sources/CLAUDE.md", "sources/cards/CLAUDE.md", "wiki/CLAUDE.md")

# Static MANAGED/TEMPLATE paths hashed into the manifest (plan-v3 section
# 2.4), on top of the dynamically-discovered scripts/*.py and .githooks/*
# paths build_role_map() below folds in.
MANAGED_STATIC_PATHS = (
    "sources/AGENTS.md", "wiki/AGENTS.md", "sources/cards/AGENTS.md",
    "CLAUDE.md", "sources/CLAUDE.md", "sources/cards/CLAUDE.md", "wiki/CLAUDE.md",
)
TEMPLATE_STATIC_PATHS = ("AGENTS.md", "README.md")

GIT_IDENTITY_NAME = "wiki-harness init"
GIT_IDENTITY_EMAIL = "init@wiki-harness.invalid"

BYPASS_WARNING_TEMPLATE = (
    "Note: commits authored via the GitHub API or a cloud coding agent "
    "structurally bypass every local hook this scaffold just wired up; "
    "wiki-harness v{version} ships no mitigation for that class of commit at all."
)

HOOKS_PATH_FAILURE_MESSAGE = "failed to configure core.hooksPath for {target}"
HOOK_DRY_RUN_FAILURE_MESSAGE = ("hook dry-run failed for {target}; scaffold "
                                "left on disk for inspection")
COMMIT_FAILURE_MESSAGE = "scaffold commit failed for {target}; scaffold left on disk"
COMMIT_VERIFY_FAILURE_MESSAGE = ("scaffold commit did not land as expected "
                                 "for {target}; scaffold left on disk")


# ---- pure core ----

def resolve_target_refusal(target, exists, is_empty, force, is_dir=True):
    """Pure. Step 1: the exact refusal message, or None when nothing
    refuses. Two independent conditions refuse: (a) the target exists and
    occupies the path as something other than a directory (a plain file,
    for instance) -- there is no directory to scaffold into, and --force
    cannot change that, since forcing means "write into the non-empty
    directory anyway", not "delete what's there"; (b) the target is an
    existing, non-empty directory and --force was not passed. Nothing is
    ever written when this returns non-None."""
    if exists and not is_dir:
        return REFUSAL_MESSAGE.format(path=target)
    if exists and not is_empty and not force:
        return REFUSAL_MESSAGE.format(path=target)
    return None


def missing_required_vars(values):
    """Pure. Step 2: which REQUIRED variable is still missing (None or
    empty) after collection. Since v1.2.0 that is `wiki_title` alone --
    every other template variable is derived by apply_defaults()."""
    return [k for k in REQUIRED_VARS if not values.get(k)]


def apply_defaults(values, target_name):
    """Pure. Step 2: derives every template variable the caller left empty,
    so only --wiki-title has to be answered. `target_name` is the target
    directory's basename, resolved at the edge (main()) because `.` and a
    trailing slash both need the real path before a basename means
    anything. A value the caller did supply is never overridden."""
    filled = dict(values)
    if not filled.get("repo_name"):
        filled["repo_name"] = target_name
    if not filled.get("content_language"):
        filled["content_language"] = DEFAULT_CONTENT_LANGUAGE
    if not filled.get("org_name"):
        filled["org_name"] = filled.get("wiki_title") or ""
    return filled


def missing_vars_message(missing):
    flags = ", ".join(f"--{k.replace('_', '-')}" for k in missing)
    return f"missing required value(s) for --non-interactive mode: {flags}"


def parse_origins(raw):
    """Pure. Step 2's --origins value: comma-separated list, default
    ['session'] when empty/omitted."""
    if not raw:
        return ["session"]
    items = [o.strip() for o in raw.split(",") if o.strip()]
    return items or ["session"]


class NoInputError(Exception):
    """Raised when an interactive prompt has nothing to read -- init was run
    without --non-interactive from a script, a CI job, or any other non-tty
    context, so `input()` hits EOF. main() converts it into the same clean
    exit-2 stderr refusal every other invalid-input path uses; a traceback
    escaping a CLI is a crash to the user, not a verdict."""


class AnswersFileError(Exception):
    """Raised when --answers-file's content cannot be parsed into the shape
    collect_vars() expects (invalid JSON, a non-object top level, or a
    required variable whose value is not a JSON string) -- caught by
    main() and converted into the same clean exit-2 stderr refusal every
    other invalid-input path in this module uses (resolve_target_refusal(),
    missing_vars_message()), never an unhandled traceback."""


def parse_answers_file(text):
    """Pure. Parses --answers-file's JSON text (the 4 required variables
    plus an optional 'origins' comma-separated string, same shape as the
    individual flags) into a dict; no filesystem access of its own --
    read_answers_file() below is the impure edge that supplies `text`.
    Raises AnswersFileError -- deterministically, never an unhandled
    json.JSONDecodeError/AttributeError -- for malformed JSON, a non-object
    top level, or a required variable whose value is not a JSON string
    (the individual --flags are argparse-guaranteed to always be a str;
    the file path must guarantee the same shape)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnswersFileError(f"is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AnswersFileError(
            "must be a JSON object mapping variable names to string "
            f"values, not {type(data).__name__}")
    for key in TEMPLATE_VARS:
        if key in data and not isinstance(data[key], str):
            raise AnswersFileError(
                f"value for {key!r} must be a JSON string, got "
                f"{type(data[key]).__name__}")
    if "origins" in data and not isinstance(data["origins"], str):
        raise AnswersFileError(
            "value for 'origins' must be a JSON string, got "
            f"{type(data['origins']).__name__}")
    return data


def merge_answers(cli_values, cli_origins, file_values):
    """Pure. Step 2: merges --answers-file's values under individually-
    passed flags -- an explicit flag always wins over the file, and the
    file only fills gaps flags left empty. Returns (values, origins_raw),
    the latter still unparsed and ready for parse_origins()."""
    values = dict(cli_values)
    for key in TEMPLATE_VARS:
        if not values.get(key) and file_values.get(key):
            values[key] = file_values[key]
    origins_raw = cli_origins if cli_origins else file_values.get("origins")
    return values, origins_raw


def apply_origins(schema, origins):
    """Pure. Step 8: returns a copy of the parsed card-schema.default.json
    dict with 'origin's enum widened to `origins`."""
    result = copy.deepcopy(schema)
    result["keys"]["origin"]["enum"] = list(origins)
    return result


def render(text, variables):
    """Pure. Step 6: fills a TEMPLATE-class source's ${var} placeholders
    (stdlib string.Template) from `variables`."""
    from string import Template
    return Template(text).substitute(variables)


def build_role_map(scripts_paths, hooks_paths):
    """Pure. Step 10: every MANAGED/TEMPLATE path init just wrote, mapped
    to its manifest role -- exactly the set plan-v3 section 2.4 records,
    plus scripts/manifest.py automatically via scripts_paths (A8)."""
    roles = {}
    for p in scripts_paths:
        roles[p] = "managed"
    for p in hooks_paths:
        roles[p] = "managed"
    for p in MANAGED_STATIC_PATHS:
        roles[p] = "managed"
    for p in TEMPLATE_STATIC_PATHS:
        roles[p] = "template"
    return roles


def commit_subject(version):
    """Pure. Step 14's exact commit subject."""
    return f"chore: scaffold from wiki-harness v{version}"


def bypass_warning(version):
    """Pure. Step 16's mandatory reminder that API/cloud-agent commits
    bypass every local hook, naming the release that ships no mitigation.
    `version` is the library's own VERSION, supplied by the caller --
    never a literal, so a wiki scaffolded from a later release is not
    told it came from an earlier one."""
    return BYPASS_WARNING_TEMPLATE.format(version=version)


def summary_text(target, commit_hash, version):
    """Pure. Step 16's summary, including the mandatory reminder that
    API/cloud-agent commits bypass every local hook and that this release
    ships no mitigation for that class of commit -- no '--ci' suggestion,
    because there is no --ci. Takes `version` the same way
    commit_subject() does; read_version() is the impure edge that supplies
    it."""
    short = commit_hash[:12] if commit_hash else commit_hash
    return (
        f"Scaffolded {target} -- lint clean, .githooks wired, first commit {short}.\n"
        "Next: start ingesting -- see AGENTS.md's Workflow: Ingest.\n"
        f"{bypass_warning(version)}"
    )


# ---- impure edges below this line ----

def _git(root, *args):
    """Impure edge. Isolates every git call this module makes from the
    host's global/system config (e.g. a commit.gpgsign=true policy with no
    usable signing key), so init always behaves the same regardless of the
    machine it runs on -- only this repo's own local config (set via the
    `git config` calls below) ever applies."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, env=env,
                          timeout=120)


def _copy_verbatim(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def read_answers_file(path):
    """Impure edge: reads and JSON-decodes an --answers-file path.
    parse_answers_file() above does the actual (pure) parsing/validation;
    this edge folds the filesystem-level failure (missing file, permission
    denied, bytes that are not valid UTF-8 at all, ...) into the same
    AnswersFileError channel and prefixes every message with `path` so the
    caller always knows which file was at fault -- never an unhandled
    OSError or UnicodeDecodeError traceback. UnicodeDecodeError is a
    ValueError subclass, not an OSError subclass, so it must be caught
    alongside OSError explicitly; it is not folded into that clause for
    free."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AnswersFileError(f"--answers-file {path} could not be read: {exc}") from exc
    try:
        return parse_answers_file(text)
    except AnswersFileError as exc:
        raise AnswersFileError(f"--answers-file {path} {exc}") from exc


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="init.py")
    parser.add_argument("target")
    parser.add_argument("--wiki-title", dest="wiki_title")
    parser.add_argument("--org-name", dest="org_name")
    parser.add_argument("--content-language", dest="content_language")
    parser.add_argument("--repo-name", dest="repo_name")
    parser.add_argument("--origins", default=None)
    parser.add_argument("--answers-file", dest="answers_file", default=None)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def _ask(prompt, label, text):
    """Impure edge. One prompt, with EOF converted into a typed refusal --
    `input()` raises EOFError the moment stdin is closed or exhausted, which
    is exactly what a script or a CI job running init without
    --non-interactive hands it."""
    try:
        return prompt(text).strip()
    except EOFError:
        raise NoInputError(NO_INPUT_MESSAGE.format(label=label)) from None


def collect_vars(args, prompt=input, read_answers=read_answers_file,
                 target_name=""):
    """Step 2's collection edge. `prompt` is an injected seam (default
    builtins.input) so the interactive path never has to be exercised to
    test the rest of this function's behaviour. `read_answers` is the
    matching seam for --answers-file (default read_answers_file) so the
    merge logic can be tested without a real file on disk. Precedence:
    an individually-passed flag always wins over the --answers-file value
    for the same key; the file only fills gaps flags left empty. Returns
    (values, origins_raw) -- the merged template values and the
    still-unparsed origins string, ready for parse_origins().

    Interactively, only REQUIRED_VARS re-prompts until answered; each
    DEFAULTED_VARS prompt offers apply_defaults()' derivation in brackets
    and an empty answer takes it. `target_name` (the resolved basename
    main() computes) is what that derivation needs; it is only ever used
    to build the offer, and main() applies the same pure derivation again
    afterwards, so a non-interactive run reaches the identical values."""
    cli_values = {
        "wiki_title": args.wiki_title,
        "org_name": args.org_name,
        "content_language": args.content_language,
        "repo_name": args.repo_name,
    }
    file_values = read_answers(args.answers_file) if args.answers_file else {}
    values, origins_raw = merge_answers(cli_values, args.origins, file_values)
    if not args.non_interactive:
        for key in REQUIRED_VARS:
            while not values[key]:
                values[key] = _ask(prompt, PROMPT_LABELS[key],
                                   f"{PROMPT_LABELS[key]}: ")
        for key in DEFAULTED_VARS:
            if values[key]:
                continue
            offered = apply_defaults(values, target_name)[key]
            values[key] = _ask(prompt, PROMPT_LABELS[key],
                               f"{PROMPT_LABELS[key]} [{offered}]: ") or offered
    return values, origins_raw


def git_init(target):
    """Step 3."""
    if not (target / ".git").exists():
        _git(target, "init", "-q")
    _git(target, "config", "user.email", GIT_IDENTITY_EMAIL)
    _git(target, "config", "user.name", GIT_IDENTITY_NAME)


def create_gitkeeps(target):
    """Step 4."""
    for rel in ("sources/raw/.gitkeep", "sources/cards/.gitkeep", "wiki/.gitkeep"):
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")


def copy_scripts(library_root, target):
    """Step 5 (scripts half). Returns the target-relative posix paths
    copied, discovered off disk so scripts/manifest.py rides along
    automatically (A8) without a second, hand-maintained list."""
    src_dir = library_root / "scripts"
    dst_dir = target / "scripts"
    dst_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for src in sorted(src_dir.glob("*.py")):
        _copy_verbatim(src, dst_dir / src.name)
        paths.append(f"scripts/{src.name}")
    return paths


def copy_hooks(library_root, target):
    """Step 5 (hooks half): copies githooks/* verbatim into <target>/.githooks/
    and chmod +x both."""
    src_dir = library_root / "githooks"
    dst_dir = target / ".githooks"
    dst_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for src in sorted(src_dir.iterdir()):
        if not src.is_file():
            continue
        dst = dst_dir / src.name
        _copy_verbatim(src, dst)
        dst.chmod(0o755)
        paths.append(f".githooks/{src.name}")
    return paths


def render_root_templates(library_root, target, values):
    """Step 6."""
    templates_dir = library_root / "templates"
    for tmpl_name, out_name in (("AGENTS.root.md.tmpl", "AGENTS.md"),
                                ("README.md.tmpl", "README.md")):
        text = (templates_dir / tmpl_name).read_text(encoding="utf-8")
        (target / out_name).write_text(render(text, values), encoding="utf-8")


def copy_managed_agents(library_root, target):
    """Step 7."""
    templates_dir = library_root / "templates"
    for tmpl_name, out_rel in MANAGED_COPY_MAP:
        _copy_verbatim(templates_dir / tmpl_name, target / out_rel)


def seed_starters(library_root, target, origins):
    """Step 8."""
    templates_dir = library_root / "templates"
    for tmpl_name, out_rel in SEED_COPY_MAP:
        _copy_verbatim(templates_dir / tmpl_name, target / out_rel)

    schema = json.loads((templates_dir / "card-schema.default.json")
                        .read_text(encoding="utf-8"))
    schema = apply_origins(schema, origins)
    out = target / "sources/cards/card-schema.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def seed_claude_stubs(library_root, target):
    """Step 9: seeds CLAUDE.md (root) and the 3 nested stubs as ordinary
    MANAGED, tracked files -- no .gitignore coordination needed."""
    templates_dir = library_root / "templates"
    _copy_verbatim(templates_dir / "CLAUDE.root.tmpl", target / "CLAUDE.md")
    nested_src = templates_dir / "CLAUDE.nested.tmpl"
    for rel in CLAUDE_NESTED_PATHS:
        _copy_verbatim(nested_src, target / rel)


def read_version(library_root):
    """Impure edge. The library's own version, from its VERSION file.
    release-please rewrites that file on every release; take the first
    whitespace-delimited token so a stray trailing comment cannot ride into
    the consumer's manifest and init's summary line."""
    text = (library_root / "VERSION").read_text(encoding="utf-8").strip()
    return text.split()[0] if text.split() else ""


def read_release_metadata(library_root):
    """Impure edge. RELEASE.json, present only when the library root is an
    unpacked release payload rather than a git checkout.

    An installed wiki-harness runs from a tarball with no `.git`, so the
    three source_* edges below have nothing to interrogate and would record
    a local path, "unknown", and forty zeros in the consumer's manifest.
    tools/build_release.py records the real values here at release time.

    Returns {} for anything unusable -- absent, unreadable, not JSON, not a
    JSON object -- so the git path below still runs. This is read on a
    scaffold a person is waiting on: a malformed file must degrade, never
    raise."""
    path = library_root / RELEASE_METADATA_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _released(library_root, key):
    """Impure edge. One RELEASE.json string field, or None when the payload
    has no usable value for it. A non-string is treated as absent: the
    manifest's consumers expect strings, and a number here would travel
    into `upgrade --check`."""
    value = read_release_metadata(library_root).get(key)
    return value if isinstance(value, str) and value else None


def read_source_url(library_root):
    return (_released(library_root, "source_url")
            or _git(library_root, "config", "--get",
                    "remote.origin.url").stdout.strip()
            or str(library_root))


def read_source_ref(library_root):
    return (_released(library_root, "tag")
            or _git(library_root, "describe", "--tags",
                    "--always").stdout.strip()
            or "unknown")


def read_source_commit(library_root):
    return (_released(library_root, "commit")
            or _git(library_root, "rev-parse", "HEAD").stdout.strip()
            or "0" * 40)


def write_manifest_file(library_root, target, values, scripts_paths, hooks_paths):
    """Step 10."""
    role_map = build_role_map(scripts_paths, hooks_paths)
    actual = hash_tree(target, sorted(role_map))
    hashes = {path: {"role": role_map[path], "sha256": sha}
             for path, sha in actual.items()}
    manifest = compute_manifest(
        hashes, values, read_source_url(library_root),
        read_version(library_root), read_source_ref(library_root),
        read_source_commit(library_root),
        initialised_at=date.today().isoformat())
    write_manifest(target / MANIFEST_FILENAME, manifest)


def set_hooks_path(target):
    """Step 11: sets core.hooksPath, then reads it back to confirm the
    write landed."""
    _git(target, "config", "core.hooksPath", ".githooks")
    result = _git(target, "config", "--get", "core.hooksPath")
    return result.stdout.strip() == ".githooks"


def run_lint(target):
    """Step 12. PYTHONDONTWRITEBYTECODE keeps a freshly scaffolded wiki free
    of scripts/__pycache__/*.pyc that this very step would otherwise
    generate: the seeded .gitignore hides them from the first commit, but a
    scaffold should not be littered by its own self-check."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(target / "scripts" / "lint.py"), "--root", str(target)],
        capture_output=True, text=True, env=env, timeout=120)
    return result.returncode == 0, result.stdout + result.stderr


def dry_run_hooks(target, subject):
    """Step 13: dry-runs both hooks directly, not via commit -- stages the
    scaffold first so pre-commit's lint runs against the current staged
    tree."""
    if _git(target, "add", "-A").returncode != 0:
        return False

    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    # The hooks shell out to lint.py; same reason as run_lint().
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    fd, msg_path = tempfile.mkstemp(suffix=".msg")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(subject + "\n")
        commit_msg_result = subprocess.run(
            [str((target / ".githooks" / "commit-msg").resolve()), msg_path],
            cwd=target, capture_output=True, text=True, env=env,
            timeout=120)
    finally:
        os.unlink(msg_path)
    if commit_msg_result.returncode != 0:
        return False

    pre_commit_result = subprocess.run(
        [str((target / ".githooks" / "pre-commit").resolve())],
        cwd=target, capture_output=True, text=True, env=env, timeout=120)
    return pre_commit_result.returncode == 0


def commit_scaffold(target, subject):
    """Step 14: a real subprocess `git commit`, exercising .githooks/* for
    real."""
    if _git(target, "add", "-A").returncode != 0:
        return False
    return _git(target, "commit", "-m", subject).returncode == 0


def verify_commit(target):
    """Step 15."""
    hash_result = _git(target, "log", "-1", "--format=%H")
    subject_result = _git(target, "log", "-1", "--format=%s")
    if hash_result.returncode != 0 or subject_result.returncode != 0:
        return False, "", ""
    return True, hash_result.stdout.strip(), subject_result.stdout.strip()


def main(argv):
    args = parse_args(argv)
    target = Path(args.target)
    library_root = Path(__file__).resolve().parent

    exists = target.exists() or target.is_symlink()
    target_is_dir = target.is_dir() if exists else True
    is_empty = not exists or (target_is_dir and not any(target.iterdir()))
    refusal = resolve_target_refusal(target, exists, is_empty, args.force,
                                     target_is_dir)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2

    # The basename apply_defaults() derives `repo_name` from. Resolved
    # first: `.` has an empty basename and a trailing slash keeps one only
    # after normalisation, so both spellings need the real path.
    target_name = target.resolve().name

    try:
        values, origins_raw = collect_vars(args, target_name=target_name)
    except (AnswersFileError, NoInputError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    missing = missing_required_vars(values)
    if missing:
        print(missing_vars_message(missing), file=sys.stderr)
        return 2
    values = apply_defaults(values, target_name)
    origins = parse_origins(origins_raw)

    target.mkdir(parents=True, exist_ok=True)

    git_init(target)                                                # step 3
    create_gitkeeps(target)                                         # step 4
    scripts_paths = copy_scripts(library_root, target)               # step 5
    hooks_paths = copy_hooks(library_root, target)                   # step 5
    render_root_templates(library_root, target, values)              # step 6
    copy_managed_agents(library_root, target)                        # step 7
    seed_starters(library_root, target, origins)                     # step 8
    seed_claude_stubs(library_root, target)                          # step 9
    write_manifest_file(library_root, target, values,                # step 10
                        scripts_paths, hooks_paths)

    if not set_hooks_path(target):                                   # step 11
        print(HOOKS_PATH_FAILURE_MESSAGE.format(target=target), file=sys.stderr)
        return 1

    lint_ok, lint_output = run_lint(target)                          # step 12
    print(lint_output)
    if not lint_ok:
        return 1

    version = read_version(library_root)
    subject = commit_subject(version)

    if not dry_run_hooks(target, subject):                           # step 13
        print(HOOK_DRY_RUN_FAILURE_MESSAGE.format(target=target), file=sys.stderr)
        return 1

    if not commit_scaffold(target, subject):                         # step 14
        print(COMMIT_FAILURE_MESSAGE.format(target=target), file=sys.stderr)
        return 1

    landed, commit_hash, commit_subj = verify_commit(target)         # step 15
    if not landed or commit_subj != subject:
        print(COMMIT_VERIFY_FAILURE_MESSAGE.format(target=target), file=sys.stderr)
        return 1

    print(summary_text(target, commit_hash, version))               # step 16
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
