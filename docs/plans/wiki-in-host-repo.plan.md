# Plan — wiki-in-host-repo: a wiki is a folder of its repo, with the agent at the repo root

| Field | Value |
| --- | --- |
| Card | `~/.tribe/-Users-home-repos-wiki-harness/cards/wiki-in-host-repo.md` (goals G1–G11, decisions D1–D8, calls K2–K11, S0, guardrails H1–H6, rulings S1–S7) |
| Spec | `docs/specs/wiki-in-host-repo.spec.md` — the How; every section number below is the spec's |
| Base | `main` @ 203c4aa (v1.4.1); work branch `feat/wiki-in-host-repo` |
| Tasks | 26 (Tasks 1–3 build the ratchet and record the baseline before any build task) |

## Global Constraints

Implementer: dispatch each implementation/fix task to the `hunter` subagent — never a generic implementer.

Purity: core logic stays deterministic and side-effect-free; every outside-world dependency (database, network, filesystem, clock, random, global state) enters through an abstraction injected from the edge — never constructed inside core logic (see `~/.claude/rules/pure-core.md`).

1. **The contract.** The card is the contract; the spec is the How. A task's code blocks are the
   brief: build them as written. A gap between a code block and the spec, or a test that cannot
   be made to pass without changing behaviour the spec fixes, goes back to the Warchief as
   `NEEDS_CONTEXT` — never a silent deviation.
2. **Repository rules (`AGENTS.md`, quoted by number).** Hard rule 1: Python 3.9, stdlib only,
   `from __future__ import annotations` first. Hard rule 2: pure core, impure edges below the
   `# ---- impure edges ----` marker, module docstrings list which functions are which. Hard rule
   3: edges fail closed — narrow `except`, no traceback out of a CLI or hook, every
   `subprocess.run` carries `timeout=`, every git call the harness makes for a decision sets
   `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` to `os.devnull` (spec §5.3 names the one deliberate
   exception: `lint.py` reads the effective hooks config). Hard rule 4 is governed by card ruling
   S0: "Changing `scripts/lint.py`, `githooks/*` and `scripts/check_commit_msg.py` for this card
   is permitted". Hard rule 5: no OGP-specific string in `scripts/`, `githooks/`, `templates/`
   (`tests/test_genericity.py`). Hard rule 6: the compatibility policy binds every change.
3. **Tests.** Write the failing test first and watch it fail. Every git call in a test isolates
   host config (`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` = `os.devnull`) and carries identity
   through `GIT_AUTHOR_*`/`GIT_COMMITTER_*` environment variables or `-c user.*`; every
   `subprocess.run` in new test code carries `timeout=`. Every new entry point that takes a path
   is exercised with a relative and an absolute target (`fixtures-mirror-reality.md`).
4. **Suite time (ruling S6).** No task's Done block runs the full suite. Done blocks run the
   task's own test modules. The whole suite runs once, in the background, in Task 25; CI is the
   authoritative full run. A foreground Bash call is capped at 10 minutes: run a full
   `tools/e2e_in_host.py` (no `--only`) in the background, as Tasks 3 and 25 do.
5. **Commits.** One commit per task, ticking the task's own checkboxes in the same commit,
   message `<type>(<scope>): <summary>` plus one final paragraph carrying both trailers, e.g.
   `-m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 4/26'`. Never a co-author trailer. The PR is
   squash-merged (ruling S7), so task commit types record history only; the release type comes
   from the squash commit (Task 25).
6. **Footprint discipline in code.** No harness command stages, commits, resets, cleans or writes
   a repo path outside its footprint (H1); every path written outside the wiki folder is proven
   inside the repo root first (H4); the harness never writes `user.name`/`user.email` (H2) and
   never overwrites a file it did not create (H3).
7. **C3 (ruling S4).** No `.c3/` edits in this card. Task 24 lists the pending fact deltas.
8. **Oracle (dispatch brief, quoted).** "Under-checking (a raw-file change or a wiki-touching
   commit that slips through) is a bug; over-checking (refusing a commit that touches the wiki
   folder in an ambiguous way) is by design. … touching anything outside the footprint (H1–H4) is
   a bug, whatever the convenience."
9. **Adjudication rule for every audit of this plan — REFUTED in advance:**
   - the changed expected hook text in `tests/test_lint_cli.py` `PreCommitHook` (Task 8: the 1.x
     text is the in-host defect, spec §1.3, S0);
   - the `.githooks` files added to `tests/test_harness_e2e.py` `HooksFindingPositivePath` (Task
     10: the old fixture pinned the G3 hole, spec §1.3);
   - the rewritten `tests/test_init.py` assertions listed in Tasks 13 and 16 (`init`'s contract
     changes in this MAJOR release, D3/D7);
   - standalone fixtures in `tests/test_upgrade.py` and `tests/test_gap_cli.py` built by
     `tests/fixtures/standalone_wiki.py` instead of `init.py` (Task 9; their assertions are
     unchanged, G9 Verify);
   - the over-checks the Oracle declares by design: a commit touching `wiki/` and other paths is
     judged by the wiki's rules; `git commit --allow-empty` right after a wiki commit is judged
     (S1); `ERROR HOOKS` for a hook manager other than the five config files of S3;
   - `lint.py` reading the effective `core.hooksPath` without isolating host config (spec §5.3);
   - any 1.x defect outside this card's goals: record it as a hardening candidate, do not fix it
     here (hard rule 4).
10. **Exact strings.** Every message, path and constant written in a task's code block is the
    contract for that string (CLI surface, compatibility policy §2).

## Way of work

The card records `Executor: tribe`. Its reasons, from the card: a permission surface (the harness
writes into a repo it does not own — files, index, git config, hooks), cross-component contracts
(init ↔ manifest ↔ upgrade ↔ lint ↔ hooks ↔ bridge), lifecycle code in a new topology, and two
past bugs of exactly this class escaped review (v1.0.0's relative-path crash past 248 green
tests; #46 7a's silently disabled raw check). What would justify a lighter mode: a split into
cards small enough that every defect surfaces in a task's Green or the E2E scenario — rejected by
D1 (one card).

Executor: tribe

- The full tribe delivery executes this plan: a full-build Warchief (`agents/warchief.md`) takes the committed spec and plan and runs its Method steps 4–8 — a Hunter (`subagent_type: hunter`) per task, the two-lens Skinner audit per task (the contract lens and the cold lens, dispatched in one message), the Tracker every audit round, the Warchief adjudicating every finding with its own fix loop, the harness-gap gate, then the PR, every check green, and `gh pr merge --merge`.
- Under the campaign harness the runner's executor session acts as that Warchief, one turn per task, and this plan also carries orchestrate-campaign's "tribe cards — campaign plan additions" and ends with its Harness-gap gate task. Without the harness (the owner's explicit words) the Shaman dispatches the Warchief (`subagent_type: warchief`) and receives its SHIPPED / NEEDS_DIRECTION / BLOCKED.
- The plan's Global Constraints names the Hunter as the implementer, as `agents/warchief.md` Method step 3 requires.

- The runner still drives the tasks in order and runs each task's Done commands itself; end a
  task's turn only after its audit closed.
- Every dispatched worker (Hunter, Skinner) writes its report under the campaign home's `reports/`
  directory (the brief names the campaign home), with the gate output it relied on pasted
  verbatim.
- Dispatch the Tracker at every audit round (Warchief Method step 6.0b), each with its own report file
  `<campaign home>/reports/tracker-<card id>-<round>.md` (`<round>` = `task-3`, `wave-2`, `fix-1`,
  `final`). Use the runner's card id as your card slug — in these file names, in `gap-gate.ts --card`,
  and in every `Tribe-Card:` trailer.
- Scout's governance proposals ride this card's PR: rule/anti-rule drafts as reviewable text, a debt
  proposal as its recorded check command + description only — the debt entity itself is created
  later, by ratified `gap-rule.ts` execution. Do not self-ratify; record each proposal and its
  proposed disposition under a `## Harness gaps` heading in the PR body. Only a gap needing an
  owner-only decision escalates NEEDS_DIRECTION.

**Merge method (ruling S7).** This repository refuses merge commits (`allow_merge_commit: false`),
so the block's `gh pr merge --merge` cannot run here. The delivery merges by squash with the body
Task 25 writes, exactly:
`gh pr merge --squash --subject "feat(init)!: init scaffolds the wiki as a folder of its repository, with a bridge for the agent at the root" --body-file docs/evidence/in-host-squash-body.md`,
then checks `git log -1 --format=%B origin/main` ends with the `BREAKING CHANGE:` paragraph.

## Ratchet ids used by the tasks

`tools/e2e_in_host.py` prints one line per check id (spec §7.1). Each build task's Green names the
ids it turns from FAIL to PASS, run with `--only`. Baseline: Task 3 commits
`docs/evidence/in-host-e2e-baseline.txt`; after: Task 25 commits
`docs/evidence/in-host-e2e-after.txt`.

---

### Task 1: Ratchet tool — core, G1, G4 and G8 scenarios

Builds the ratchet's skeleton and its first three scenarios. No harness code changes.

**Files**
- Create: `tools/e2e_in_host.py`
- Create: `tests/test_e2e_in_host_tool.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_e2e_in_host_tool.py`:

```python
"""Unit tests for the in-host ratchet tool's pure core, plus one smoke run."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import e2e_in_host as e2e  # noqa: E402


class Formatting(unittest.TestCase):
    def test_pass_line(self):
        self.assertEqual(e2e.format_result(e2e.Result("G1.1[x]", True, "init exits 0", "")),
                         "PASS G1.1[x] init exits 0")

    def test_fail_line_carries_the_reason(self):
        self.assertEqual(e2e.format_result(e2e.Result("G4.4", False, "same everywhere", "rc 1 vs 0")),
                         "FAIL G4.4 same everywhere -- rc 1 vs 0")

    def test_total(self):
        results = [e2e.Result("a", True, "t", ""), e2e.Result("b", False, "t", "r")]
        self.assertEqual(e2e.format_total(results), "TOTAL 1/2")


class Selection(unittest.TestCase):
    def test_empty_only_selects_everything(self):
        self.assertTrue(e2e.selected("G5.2", []))

    def test_prefix_selects(self):
        self.assertTrue(e2e.selected("G5.2", ["G5"]))
        self.assertFalse(e2e.selected("G5.2", ["G4"]))

    def test_scenario_selected_by_check_prefix(self):
        self.assertTrue(e2e.scenario_selected("G5", ["G5.2"]))
        self.assertTrue(e2e.scenario_selected("G5", ["G5"]))
        self.assertTrue(e2e.scenario_selected("G5", []))
        self.assertFalse(e2e.scenario_selected("G5", ["G4.1"]))


class Footprint(unittest.TestCase):
    def test_folder_entry_covers_everything_below(self):
        self.assertFalse(e2e.outside_footprint("wiki/index.md", ["wiki/"]))
        self.assertTrue(e2e.outside_footprint("wikis/index.md", ["wiki/"]))

    def test_file_entry_is_exact(self):
        self.assertFalse(e2e.outside_footprint("WIKI.md", ["wiki/", "WIKI.md"]))
        self.assertTrue(e2e.outside_footprint("src/app.py", ["wiki/", "WIKI.md"]))

    def test_diff_reports_changed_vanished_and_appeared_paths_outside_only(self):
        before = {"src/a.py": "1", "src/b.py": "2", "wiki/x.md": "3"}
        after = {"src/a.py": "9", "wiki/x.md": "4", "src/c.py": "5"}
        self.assertEqual(e2e.diff_snapshots(before, after, ["wiki/"]),
                         ["src/a.py", "src/b.py", "src/c.py"])


class Smoke(unittest.TestCase):
    def test_the_tool_runs_a_scenario_and_prints_a_total(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "e2e_in_host.py"), "--only", "G8"],
            capture_output=True, text=True, timeout=600)
        lines = result.stdout.splitlines()
        self.assertTrue(lines and lines[-1].startswith("TOTAL "), result.stdout + result.stderr)
        self.assertTrue(any(line.split()[1] == "G8.1" for line in lines[:-1]), result.stdout)
        self.assertIn(result.returncode, (0, 1))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
```

Expected: `ModuleNotFoundError: No module named 'e2e_in_host'`, exit 1.

- [ ] **Step 3: Write `tools/e2e_in_host.py`**

```python
#!/usr/bin/env python3
"""The in-host ratchet: one end-to-end scenario for card wiki-in-host-repo.

Builds real repositories in a throwaway directory, runs the harness exactly as a person
types it (subprocesses, relative and absolute targets, no hand-made workaround), and
prints one line per check -- `PASS <id> <text>` or `FAIL <id> <text> -- <reason>` --
then `TOTAL <passed>/<total>`. Exit 0 only when every selected check passes.

Repo-internal: lives in tools/, never scripts/, so init never vendors it into a wiki.

Pure core: Result, format_result(), format_total(), selected(), scenario_selected(),
outside_footprint(), diff_snapshots(), added_config().
Impure edges: everything below the "impure edges" marker.
Python 3.9 stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TITLE = "Acme Widgets"
NAME_FLAGS = ("--wiki-title", TITLE, "--non-interactive")

# `git init` writes these keys into every new repository; they say nothing about what the
# harness did, so the config comparison ignores them.
GIT_INIT_DEFAULT_KEYS = frozenset({
    "core.repositoryformatversion", "core.filemode", "core.bare", "core.logallrefupdates",
    "core.ignorecase", "core.precomposeunicode", "core.symlinks",
})

# One check outcome. `reason` is "" for a pass.
Result = namedtuple("Result", "check_id ok text reason")


# ---- pure core ----

def format_result(result):
    """Pure. One output line."""
    if result.ok:
        return f"PASS {result.check_id} {result.text}"
    return f"FAIL {result.check_id} {result.text} -- {result.reason}"


def format_total(results):
    """Pure. The last output line."""
    passed = sum(1 for r in results if r.ok)
    return f"TOTAL {passed}/{len(results)}"


def selected(check_id, only):
    """Pure. `only` is a list of id prefixes; an empty list selects every check."""
    return not only or any(check_id.startswith(prefix) for prefix in only)


def scenario_selected(name, only):
    """Pure. A scenario runs when no filter is given, or a filter names it or one of its
    checks (`G5` and `G5.2` both select scenario `G5`)."""
    if not only:
        return True
    return any(prefix == name or prefix.startswith(name + ".") or name.startswith(prefix)
               for prefix in only)


def outside_footprint(path, footprint):
    """Pure. True when the repo-relative POSIX `path` lies outside every footprint entry.
    An entry ending in '/' is a folder and covers everything below it; any other entry is
    exactly one file."""
    for entry in footprint:
        if entry.endswith("/") and path.startswith(entry):
            return False
        if path == entry:
            return False
    return True


def diff_snapshots(before, after, footprint):
    """Pure. `before`/`after` map repo-relative paths to a fingerprint (a sha256, or an
    index entry). Returns, sorted, every path outside the footprint that changed,
    vanished or appeared."""
    paths = set(before) | set(after)
    return sorted(p for p in paths
                  if outside_footprint(p, footprint) and before.get(p) != after.get(p))


def added_config(before, after):
    """Pure. The `key=value` lines `after` has and `before` lacks, ignoring the keys
    `git init` writes; plus the lines `before` had that `after` lost."""
    def meaningful(lines):
        return {line for line in lines if line.split("=", 1)[0] not in GIT_INIT_DEFAULT_KEYS}
    return sorted(meaningful(after) - meaningful(before)), sorted(meaningful(before) - meaningful(after))


# ---- impure edges ----

def isolated_env(extra=None):
    """Impure edge (reads os.environ). Host git config is neutralised so a machine's
    settings cannot change a verdict; identity travels in the environment, as a person's
    global config would supply it."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "E2E Owner"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "owner@example.invalid"
    env.update(extra or {})
    return env


def run(args, cwd, extra_env=None, timeout=300):
    """Impure edge. One bounded subprocess with stdin closed (a prompt gets EOF)."""
    return subprocess.run([str(a) for a in args], cwd=str(cwd), capture_output=True,
                          text=True, env=isolated_env(extra_env), timeout=timeout,
                          stdin=subprocess.DEVNULL)


def git(root, *args):
    """Impure edge."""
    return run(["git", "-C", root, *args], cwd=root, timeout=120)


def init_cmd(lib, target, flags=NAME_FLAGS):
    """Impure-adjacent: the exact argv a person types for `init`."""
    return [sys.executable, Path(lib) / "init.py", target, *flags]


def init_repo(root):
    """Impure edge."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")


def write(path, text, mode=None):
    """Impure edge."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def make_codebase(root, dirty=True):
    """Impure edge. A repository that already has code -- and, with `dirty`, an unrelated
    uncommitted edit and an unrelated staged file, the shape a person runs `init` in."""
    init_repo(root)
    write(root / "src" / "app.py", 'print("app")\n')
    write(root / "README.md", "# Acme widgets\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "feat: host code")
    if dirty:
        with (root / "src" / "app.py").open("a", encoding="utf-8") as handle:
            handle.write("# uncommitted edit\n")
        write(root / "src" / "staged.py", "STAGED = True\n")
        git(root, "add", "src/staged.py")
    return root


def worktree_snapshot(root):
    """Impure edge. {repo-relative path: sha256} for every file outside .git."""
    out = {}
    for path in sorted(Path(root).rglob("*")):
        rel = path.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or not path.is_file():
            continue
        out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def index_snapshot(root):
    """Impure edge. {path: 'mode sha stage'} from `git ls-files -s`."""
    out = {}
    for line in git(root, "ls-files", "-s").stdout.splitlines():
        meta, _, path = line.partition("\t")
        out[path] = meta
    return out


def local_config(root):
    """Impure edge."""
    return git(root, "config", "--local", "--list").stdout.splitlines()


def read_json(path):
    """Impure edge. None when absent or not JSON."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def footprint_of(root, before_paths):
    """Impure edge. `wiki/`, the manifest's recorded bridge paths, and a root AGENTS.md /
    CLAUDE.md that did not exist before (seeded by init, K9)."""
    entries = ["wiki/"]
    manifest = read_json(root / "wiki" / ".wiki-harness-manifest.json") or {}
    bridge = manifest.get("bridge") if isinstance(manifest, dict) else None
    entries += sorted(bridge) if isinstance(bridge, dict) else []
    entries += [name for name in ("AGENTS.md", "CLAUDE.md") if name not in before_paths]
    return entries


def head_paths(root):
    """Impure edge. Paths the HEAD commit changed."""
    return git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root",
               "HEAD").stdout.split()


def check(check_id, text, ok, reason):
    """Impure-adjacent constructor kept beside the edges for readability."""
    return Result(check_id, bool(ok), text, "" if ok else reason)


def last_line(result):
    """The last non-empty line a subprocess printed, for a FAIL reason."""
    lines = [l for l in (result.stdout + result.stderr).splitlines() if l.strip()]
    return f"exit {result.returncode}: {lines[-1] if lines else '(no output)'}"


def in_host_repo(lib, root, dirty=False):
    """Impure edge. An in-host repository made the way a person makes one: `init .` at the
    root of a codebase. When the library under test cannot produce the layout (the
    pre-2.0 baseline), the shape is built by hand -- the library's init into `wiki/`,
    its nested `.git` removed, committed, hooks pointed at `wiki/.githooks` -- and the
    returned note says so, so a baseline line never hides how its fixture was made."""
    make_codebase(root, dirty=dirty)
    result = run(init_cmd(lib, "."), cwd=root)
    if (root / "wiki" / ".wiki-harness-manifest.json").is_file() and not (root / "wiki" / ".git").exists():
        return root, ""
    if (root / "wiki").exists():
        shutil.rmtree(root / "wiki")
    built = run(init_cmd(lib, root / "wiki"), cwd=root)
    if built.returncode != 0:
        raise ValueError(f"cannot build the in-host shape by hand: {last_line(built)}")
    shutil.rmtree(root / "wiki" / ".git", ignore_errors=True)
    git(root, "add", "wiki")
    git(root, "commit", "-q", "--no-verify", "-m", "chore: add the wiki folder by hand", "--", "wiki")
    git(root, "config", "core.hooksPath", "wiki/.githooks")
    return root, f" (hand-built shape: init {last_line(result)})"


# ---- scenarios: each returns a list of Result ----

G1_FORMS = ("codebase-dot", "codebase-abs", "empty-rel", "empty-abs")


def scenario_g1(lib, work):
    """G1: `init` at a codebase's root and at an empty directory, relative and absolute."""
    results = []
    for form in G1_FORMS:
        root = work / f"g1-{form}"
        if form.startswith("codebase"):
            make_codebase(root)
        elif form == "empty-abs":
            root.mkdir(parents=True)
        before_tree = worktree_snapshot(root) if root.exists() else {}
        before_index = index_snapshot(root) if (root / ".git").exists() else {}
        before_config = local_config(root) if (root / ".git").exists() else []
        if form == "codebase-dot":
            result = run(init_cmd(lib, "."), cwd=root)
        elif form == "empty-rel":
            result = run(init_cmd(lib, root.name), cwd=work)
        else:
            result = run(init_cmd(lib, root.resolve()), cwd=work)
        tag = f"[{form}]"
        ok_init = result.returncode == 0
        results.append(check(f"G1.1{tag}", "init exits 0", ok_init, last_line(result)))
        if not ok_init:
            for n, text in ((2, "in-host layout"), (3, "no gitlink"),
                            (4, "outside the footprint unchanged"),
                            (5, "git config changed only by the hooks wiring"),
                            (6, "the init commit holds only footprint paths")):
                results.append(check(f"G1.{n}{tag}", text, False, "init did not succeed"))
            continue
        layout_ok = ((root / "wiki" / "index.md").is_file() and (root / ".git").exists()
                     and not (root / "wiki" / ".git").exists())
        results.append(check(f"G1.2{tag}", "in-host layout: wiki/index.md, one .git at the root",
                             layout_ok, "no wiki/index.md, or a nested wiki/.git"))
        gitlinks = [p for p, meta in index_snapshot(root).items() if meta.startswith("160000")]
        results.append(check(f"G1.3{tag}", "no gitlink in the index", not gitlinks,
                             f"gitlinks: {gitlinks}"))
        footprint = footprint_of(root, before_tree)
        changed = (diff_snapshots(before_tree, worktree_snapshot(root), footprint)
                   + diff_snapshots(before_index, index_snapshot(root), footprint))
        results.append(check(f"G1.4{tag}", "every path outside the footprint is unchanged (worktree and index)",
                             not changed, f"changed outside the footprint: {changed[:5]}"))
        added, removed = added_config(before_config, local_config(root))
        results.append(check(f"G1.5{tag}", "git config changed only by core.hooksPath=wiki/.githooks",
                             added == ["core.hookspath=wiki/.githooks"] and not removed,
                             f"added {added}, removed {removed}"))
        subject = git(root, "log", "-1", "--format=%s").stdout.strip()
        outside = [p for p in head_paths(root) if outside_footprint(p, footprint)]
        results.append(check(f"G1.6{tag}", "the init commit holds only footprint paths",
                             subject.startswith("chore: scaffold from wiki-harness v") and not outside,
                             f"subject {subject!r}, outside paths {outside[:5]}"))
    return results


def scenario_g4(lib, work):
    """G4: every shipped script gives the same result from the root, the wiki folder and an
    unrelated directory, typed with a relative script path."""
    root, note = in_host_repo(lib, work / "g4")
    schema_path = root / "wiki" / "sources" / "cards" / "card-schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["keys"]["id"]["pattern"] = r"^doc-\d{3}$"
    write(schema_path, json.dumps(schema, indent=2) + "\n")
    write(root / "wiki" / "sources" / "cards" / "doc-001.md",
          "---\nid: doc-001\ndate: 2026-10-05\norigin: session\ntrust: stated\n"
          "topics: [widgets]\n---\n## Claims\n- a claim\n")
    msg = work / "msg.txt"
    write(msg, "ingest(doc-001): file a doc\n")
    elsewhere = work / "elsewhere"
    elsewhere.mkdir(parents=True, exist_ok=True)
    gap_args = ["add", "--no-commit", "--service", "acme", "--session", "s1", "--context", "c",
                "--prompt", "p", "--question", "q", "--wiki-answer", "none",
                "--answer-given", "none", "--topics", "widgets"]
    run([sys.executable, "wiki/scripts/gap.py", *gap_args], cwd=root)
    places = (("root", root), ("wiki", root / "wiki"), ("elsewhere", elsewhere))

    def rel(path, cwd):
        return os.path.relpath(path, cwd)

    scripts = (
        ("G4.1", "lint.py", lambda cwd: [rel(root / "wiki/scripts/lint.py", cwd)], None),
        ("G4.2", "card_frontmatter_lint.py",
         lambda cwd: [rel(root / "wiki/scripts/card_frontmatter_lint.py", cwd),
                      rel(root / "wiki/sources/cards/doc-001.md", cwd)], None),
        ("G4.3", "gap.py list",
         lambda cwd: [rel(root / "wiki/scripts/gap.py", cwd), "list"], "nonempty"),
        ("G4.4", "check_commit_msg.py",
         lambda cwd: [rel(root / "wiki/scripts/check_commit_msg.py", cwd), str(msg)], "exit0"),
    )
    results = []
    for check_id, name, argv, extra in scripts:
        outs = {}
        for label, cwd in places:
            r = run([sys.executable, *argv(cwd)], cwd=cwd)
            outs[label] = (r.returncode, r.stdout, r.stderr)
        same = len(set(outs.values())) == 1
        rc, out, _ = outs["root"]
        ok = same and (extra != "nonempty" or out.strip()) and (extra != "exit0" or rc == 0)
        reason = f"rc by place {[(k, v[0]) for k, v in outs.items()]}{note}"
        results.append(check(check_id, f"{name}: same result from root, wiki/ and elsewhere",
                             ok, reason))
    return results


def scenario_g8(lib, work):
    """G8: init with no name flags derives names from the repository, not the folder `wiki`."""
    root = make_codebase(work / "acme-widgets", dirty=False)
    result = run(init_cmd(lib, ".", flags=("--non-interactive",)), cwd=root)
    readme = root / "wiki" / "README.md"
    agents = root / "wiki" / "AGENTS.md"
    ok = (result.returncode == 0 and readme.is_file() and agents.is_file()
          and "acme-widgets" in readme.read_text(encoding="utf-8")
          and "acme-widgets" in agents.read_text(encoding="utf-8")
          and "source of truth for wiki" not in readme.read_text(encoding="utf-8"))
    return [check("G8.1", "init with no name flags names the repository in README and AGENTS.md",
                  ok, last_line(result))]


SCENARIOS = (
    ("G1", scenario_g1),
    ("G4", scenario_g4),
    ("G8", scenario_g8),
)


def run_scenario(name, fn, lib, work):
    """Impure edge. A scenario whose setup breaks reports one FAIL line instead of crashing
    the ratchet: on the pre-2.0 baseline most setups are expected to break."""
    work.mkdir(parents=True, exist_ok=True)
    try:
        return fn(lib, work)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        return [Result(f"{name}.setup", False, f"{name} scenario setup", f"setup: {exc!r}")]


def main(argv):
    parser = argparse.ArgumentParser(
        prog="e2e_in_host.py",
        description="End-to-end ratchet for the in-host layout (card wiki-in-host-repo).")
    parser.add_argument("--library", default=str(REPO_ROOT),
                        help="the wiki-harness checkout under test (default: this one)")
    parser.add_argument("--only", action="append", default=[],
                        help="run only checks whose id starts with this prefix (repeatable)")
    parser.add_argument("--keep", action="store_true",
                        help="keep the work directory and print its path on stderr")
    args = parser.parse_args(argv)
    lib = Path(args.library).resolve()
    work = Path(tempfile.mkdtemp(prefix="wiki-harness-e2e-")).resolve()
    results = []
    try:
        for name, fn in SCENARIOS:
            if scenario_selected(name, args.only):
                results += run_scenario(name, fn, lib, work / name)
    finally:
        if args.keep:
            print(f"work directory: {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)
    results = [r for r in results if selected(r.check_id, args.only)
               or r.check_id.endswith(".setup")]
    for result in results:
        print(format_result(result))
    print(format_total(results))
    return 0 if results and all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests and a scenario**

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
python3 tools/e2e_in_host.py --only G4 --only G8
```

Expected: the unit tests print `OK`. The scenario run (on the unchanged 1.4.1 library) prints
`PASS G4.1 …`, `PASS G4.2 …`, `PASS G4.3 …`, `FAIL G4.4 …` (each with
`(hand-built shape: …)` in the FAIL reason only), `FAIL G8.1 …`, then `TOTAL 3/5`, exit 1 — the
card's provisional G4 baseline 3/4 and G8 0/1.

#### Verify

- **Goal:** the ratchet exists and measures G1, G4 and G8 before any build task (card "Goals":
  "the plan's FIRST task builds it and records the baseline BEFORE any build task").
- **Red:** `python3 -m unittest tests.test_e2e_in_host_tool -q` → `ModuleNotFoundError: No module named 'e2e_in_host'`, exit 1.
- **Green:** `python3 -m unittest tests.test_e2e_in_host_tool -q` → last line `OK`, exit 0; and `python3 tools/e2e_in_host.py --only G4 --only G8` → `TOTAL 3/5`, exit 1, with `FAIL G4.4` and `FAIL G8.1`.
- **Stub check:** an empty `main` prints no `TOTAL` line and fails the smoke test; a tool that
  printed PASS without running init would show `PASS G8.1` on the 1.4.1 library, where
  `init --non-interactive` with no `--wiki-title` exits 2 — the Green's `FAIL G8.1` rules it out.

#### Done

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
```

- [ ] **Step 5: Commit**

```bash
git add tools/e2e_in_host.py tests/test_e2e_in_host_tool.py docs/plans/wiki-in-host-repo.plan.md
git commit -m "test(e2e): add the in-host ratchet with its G1, G4 and G8 scenarios" -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 1/26'
```

---

### Task 2: Ratchet tool — G2, G3 and G6 scenarios

Adds the commit-gate, hooks-proof and workaround scenarios. No harness code changes.

**Files**
- Modify: `tools/e2e_in_host.py` (new helpers and scenarios; extend `SCENARIOS`)
- Modify: `tests/test_e2e_in_host_tool.py` (one pure test, one smoke)

- [ ] **Step 1: Write the failing tests** — append to `tests/test_e2e_in_host_tool.py`, above
  the `if __name__` line:

```python
class ManagerConfigs(unittest.TestCase):
    def test_pre_commit_config_names_both_wiki_hooks(self):
        text = e2e.PRE_COMMIT_CONFIG
        self.assertIn("entry: wiki/.githooks/pre-commit", text)
        self.assertIn("entry: wiki/.githooks/commit-msg", text)

    def test_lefthook_config_names_both_wiki_hooks(self):
        self.assertIn("run: wiki/.githooks/pre-commit", e2e.LEFTHOOK_CONFIG)
        self.assertIn("run: wiki/.githooks/commit-msg {1}", e2e.LEFTHOOK_CONFIG)


class SmokeG6(unittest.TestCase):
    def test_g6_prints_one_line_per_workaround(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "e2e_in_host.py"), "--only", "G6"],
            capture_output=True, text=True, timeout=600)
        ids = [line.split()[1] for line in result.stdout.splitlines()[:-1]]
        self.assertEqual(ids, ["G6.W1", "G6.W2", "G6.W3", "G6.W4", "G6.W5", "G6.W6"],
                         result.stdout + result.stderr)
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
```

Expected: `AttributeError: module 'e2e_in_host' has no attribute 'PRE_COMMIT_CONFIG'` and the
G6 smoke failing (`[] != ['G6.W1', …]`), exit 1.

- [ ] **Step 3: Add to `tools/e2e_in_host.py`** — the constants and helpers go above
  `# ---- scenarios`, the scenarios after `scenario_g8`, and `SCENARIOS` becomes the tuple below.

```python
# A hook manager's config at the repo root that runs the wiki's hooks (ruling S3). The
# manager itself is never installed: the HOOKS proof is a file read.
PRE_COMMIT_CONFIG = """repos:
  - repo: local
    hooks:
      - id: wiki-pre-commit
        name: wiki checks
        entry: wiki/.githooks/pre-commit
        language: system
        pass_filenames: false
      - id: wiki-commit-msg
        name: wiki commit message
        entry: wiki/.githooks/commit-msg
        language: system
        stages: [commit-msg]
"""

LEFTHOOK_CONFIG = """pre-commit:
  commands:
    wiki:
      run: wiki/.githooks/pre-commit
commit-msg:
  commands:
    wiki:
      run: wiki/.githooks/commit-msg {1}
"""

# What a manager installs into .git/hooks; it succeeds so init's own commit can land.
MANAGER_SHIM = "#!/bin/sh\n# File generated by a hook manager\nexit 0\n"

HUSKY_OWNER_HOOK = "#!/bin/sh\necho owner-pre-commit >> \"$(git rev-parse --git-dir)/owner-hook.log\"\n"

PAGE = "---\ntitle: Widget tips\ntopics: [widgets]\n---\nTighten gently.\n"


def make_husky_codebase(root):
    """Impure edge. A codebase whose own hooks live in a tracked `.husky/` directory."""
    make_codebase(root, dirty=False)
    write(root / ".husky" / "pre-commit", HUSKY_OWNER_HOOK, 0o755)
    write(root / "package.json", '{"name": "acme"}\n')
    git(root, "config", "core.hooksPath", ".husky")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "chore: husky")
    return root


def make_manager_codebase(root):
    """Impure edge. A codebase whose hook manager installed `.git/hooks/pre-commit`."""
    make_codebase(root, dirty=False)
    write(root / ".git" / "hooks" / "pre-commit", MANAGER_SHIM, 0o755)
    return root


def lint(root):
    """Impure edge. The wiki's lint, typed from the repo root."""
    return run([sys.executable, "wiki/scripts/lint.py"], cwd=root)


def add_raw(root):
    """Impure edge. One committed raw source (fixture setup, so it bypasses the hooks)."""
    write(root / "wiki" / "sources" / "raw" / "probe.txt", "raw v1\n")
    git(root, "add", "wiki/sources/raw/probe.txt")
    git(root, "commit", "-q", "--no-verify", "-m", "chore: add a raw source")


def commit(root, message, *extra):
    """Impure edge. A real `git commit`, through whatever hooks the repo has."""
    return git(root, "commit", "-q", "-m", message, *extra)


def add_page(root):
    """Impure edge. A lint-clean page plus its index line, staged."""
    write(root / "wiki" / "wiki" / "widget-tips.md", PAGE)
    with (root / "wiki" / "index.md").open("a", encoding="utf-8") as handle:
        handle.write("\n## Widgets\n- [Widget tips](./wiki/widget-tips.md)\n")
    git(root, "add", "wiki")


def raw_edit_refused(root):
    """Impure edge. Stage an edit of the committed raw source, try to commit, restore."""
    with (root / "wiki" / "sources" / "raw" / "probe.txt").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    git(root, "add", "wiki/sources/raw/probe.txt")
    result = commit(root, "lint: edit raw")
    git(root, "reset", "-q", "--hard", "HEAD")
    return result


def scenario_g2(lib, work):
    """G2: every wiki invariant holds in the in-host layout, through the real hooks."""
    root, note = in_host_repo(lib, work / "g2")
    add_raw(root)
    results = []
    r = raw_edit_refused(root)
    results.append(check("G2.1", "a staged edit of an existing raw file is refused",
                         r.returncode != 0 and "ERROR RAW sources/raw/probe.txt" in r.stdout + r.stderr,
                         last_line(r) + note))
    git(root, "rm", "-q", "wiki/sources/raw/probe.txt")
    r = commit(root, "lint: delete raw")
    git(root, "reset", "-q", "--hard", "HEAD")
    results.append(check("G2.2", "a staged delete of a raw file is refused",
                         r.returncode != 0 and "ERROR RAW" in r.stdout + r.stderr, last_line(r) + note))
    git(root, "mv", "wiki/sources/raw/probe.txt", "src/probe.txt")
    r = commit(root, "lint: move raw out")
    git(root, "reset", "-q", "--hard", "HEAD")
    results.append(check("G2.3", "moving a raw file out of wiki/ is refused",
                         r.returncode != 0 and "ERROR RAW" in r.stdout + r.stderr, last_line(r) + note))
    add_page(root)
    r = commit(root, "add a page")
    results.append(check("G2.4", "a wiki-touching commit with a free-form subject is refused",
                         r.returncode != 0 and "commit-msg:" in r.stdout + r.stderr, last_line(r) + note))
    r = commit(root, "lint: add a page")
    results.append(check("G2.5", "the same commit with a convention subject is accepted",
                         r.returncode == 0, last_line(r) + note))
    r = git(root, "commit", "-q", "--amend", "-m", "reword without the convention")
    results.append(check("G2.8", "rewording a wiki commit to a free-form subject is refused (S1)",
                         r.returncode != 0 and "commit-msg:" in r.stdout + r.stderr,
                         last_line(r) + note))
    with (root / "src" / "app.py").open("a", encoding="utf-8") as handle:
        handle.write("# host change\n")
    git(root, "add", "src/app.py")
    r = commit(root, "Tweak the app the host's way")
    results.append(check("G2.6", "a host-only commit with a free-form subject is accepted, no lint run",
                         r.returncode == 0 and "lint:" not in r.stdout + r.stderr,
                         last_line(r) + note))
    return results


def scenario_g3(lib, work):
    """G3: the commit gate fails closed -- lint reports HOOKS until the checks really run."""
    results = []
    root, note = in_host_repo(lib, work / "g3")
    git(root, "config", "--unset", "core.hooksPath")
    r = lint(root)
    results.append(check("G3.1", "unwired: lint exits 1 with ERROR HOOKS",
                         r.returncode == 1 and "ERROR HOOKS" in r.stdout, last_line(r) + note))
    git(root, "config", "core.hooksPath", "wiki/.githooks")
    r = lint(root)
    results.append(check("G3.2", "wired: lint exits 0", r.returncode == 0, last_line(r) + note))
    git(root, "config", "core.hooksPath", ".githooks")
    r = lint(root)
    results.append(check("G3.3", "core.hooksPath naming a missing folder: ERROR HOOKS",
                         "ERROR HOOKS" in r.stdout, last_line(r) + note))

    husky = make_husky_codebase(work / "g3-husky")
    owner_hook = (husky / ".husky" / "pre-commit").read_bytes()
    r_init = run(init_cmd(lib, "."), cwd=husky)
    r = lint(husky)
    side_pre = husky / ".husky" / "pre-commit.wiki-harness"
    side_msg = husky / ".husky" / "commit-msg.wiki-harness"
    ok = (r_init.returncode == 0 and (husky / ".husky" / "pre-commit").read_bytes() == owner_hook
          and side_pre.is_file() and side_msg.is_file() and "ERROR HOOKS" in r.stdout)
    results.append(check("G3.4", "husky: owner hook byte-identical, side files written, ERROR HOOKS",
                         ok, f"init {last_line(r_init)}; lint {last_line(r)}"))
    merged = False
    if side_pre.is_file() and side_msg.is_file():
        with (husky / ".husky" / "pre-commit").open("a", encoding="utf-8") as handle:
            handle.write(side_pre.read_text(encoding="utf-8").splitlines()[-1] + "\n")
        write(husky / ".husky" / "commit-msg", side_msg.read_text(encoding="utf-8"), 0o755)
        merged = True
    r = lint(husky)
    refused = None
    if merged:
        add_raw(husky)
        refused = raw_edit_refused(husky)
    results.append(check("G3.5", "husky after the merge: lint exits 0 and a raw edit is refused",
                         merged and r.returncode == 0 and refused is not None
                         and refused.returncode != 0,
                         f"lint {last_line(r)}"))

    for check_id, name, filename, text in (
            ("G3.6", "pre-commit framework", ".pre-commit-config.yaml", PRE_COMMIT_CONFIG),
            ("G3.7", "lefthook", "lefthook.yml", LEFTHOOK_CONFIG)):
        repo = make_manager_codebase(work / f"g3-{filename.strip('.')}")
        r_init = run(init_cmd(lib, "."), cwd=repo)
        before = lint(repo)
        write(repo / filename, text)
        after = lint(repo)
        results.append(check(check_id, f"{name}: ERROR HOOKS until its config runs the wiki hooks, then lint exits 0 (S3)",
                             r_init.returncode == 0 and "ERROR HOOKS" in before.stdout
                             and after.returncode == 0,
                             f"init {last_line(r_init)}; before {last_line(before)}; after {last_line(after)}"))
    return results


def scenario_g6(lib, work):
    """G6 (mechanical): each granado-espada workaround the harness owns is unnecessary."""
    root, note = in_host_repo(lib, work / "g6")
    add_raw(root)
    results = []
    r = raw_edit_refused(root)
    results.append(check("G6.W1", "raw immutability holds in-host (was: host pre-commit re-implements it)",
                         r.returncode != 0 and "ERROR RAW" in r.stdout + r.stderr, last_line(r) + note))
    r = lint(root)
    results.append(check("G6.W2", "the wiki's own hooks are the repo's hooks (was: host .githooks/)",
                         "ERROR HOOKS" not in r.stdout and r.returncode == 0, last_line(r) + note))
    with (root / "src" / "app.py").open("a", encoding="utf-8") as handle:
        handle.write("# host change\n")
    git(root, "add", "src/app.py")
    r = commit(root, "Free-form host commit")
    results.append(check("G6.W3", "the wiki convention applies only to wiki commits (was: commit-msg wrapper)",
                         r.returncode == 0, last_line(r) + note))
    schema_path = root / "wiki" / "sources" / "cards" / "card-schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["keys"]["id"]["pattern"] = r"^doc-\d{3}$"
    write(schema_path, json.dumps(schema, indent=2) + "\n")
    msg = work / "msg.txt"
    write(msg, "ingest(doc-001): file a doc\n")
    from_root = run([sys.executable, "wiki/scripts/check_commit_msg.py", msg], cwd=root)
    from_wiki = run([sys.executable, "scripts/check_commit_msg.py", msg], cwd=root / "wiki")
    results.append(check("G6.W4", "scripts work from the root with no cd (was: (cd wiki && ...))",
                         (from_root.returncode, from_root.stderr) == (from_wiki.returncode, from_wiki.stderr)
                         and from_root.returncode == 0, last_line(from_root) + note))
    tracked = set(git(root, "ls-files").stdout.split())
    bridge = {"WIKI.md", ".claude/skills/ask-wiki/SKILL.md", ".claude/skills/ingest-wiki/SKILL.md"}
    wiki_md = root / "WIKI.md"
    wiki_text = wiki_md.read_text(encoding="utf-8") if wiki_md.is_file() else ""
    results.append(check("G6.W5", "the bridge maps paths from the root (was: path-translation table)",
                         bridge <= tracked and "wiki/wiki/" in wiki_text,
                         f"untracked or missing: {sorted(bridge - tracked)}{note}"))
    results.append(check("G6.W6", "the bridge names branch policy as the repo's rule (was: branch before gap.py)",
                         "Branch and merge policy are this repository's own rules" in wiki_text,
                         f"WIKI.md lacks the branch-policy sentence{note}"))
    return results


SCENARIOS = (
    ("G1", scenario_g1),
    ("G2", scenario_g2),
    ("G3", scenario_g3),
    ("G4", scenario_g4),
    ("G6", scenario_g6),
    ("G8", scenario_g8),
)
```

- [ ] **Step 4: Run the tests and the new scenarios**

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
python3 tools/e2e_in_host.py --only G2 --only G3 --only G6
```

Expected: `OK`; the scenario run on the unchanged library ends `TOTAL 1/20`, exit 1: G3.1 passes
(1.x lint reports HOOKS when nothing is configured); every other line fails — the card's
provisional baselines (raw edit refused 0/1, wiki subject enforced 0/1, G3 0/3, workarounds 7).

#### Verify

- **Goal:** the ratchet measures G2, G3 (including S3's two managers) and G6's harness-owned
  workarounds W1–W6 before any build task.
- **Red:** `python3 -m unittest tests.test_e2e_in_host_tool -q` → `AttributeError: module 'e2e_in_host' has no attribute 'PRE_COMMIT_CONFIG'`, exit 1.
- **Green:** `python3 -m unittest tests.test_e2e_in_host_tool -q` → `OK`, exit 0; `python3 tools/e2e_in_host.py --only G2 --only G3 --only G6` → `TOTAL 1/20`, exit 1, with `PASS G3.1` the only PASS.
- **Stub check:** a scenario that returned fixed PASS lines would report `PASS G2.1` on the 1.4.1
  library, whose lint cannot see `wiki/sources/raw/` changes (spec §1.2); the Green's `TOTAL 1/20`
  rules it out, and the G6 smoke fails unless all six W-lines are printed in order.

#### Done

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
```

- [ ] **Step 5: Commit**

```bash
git add tools/e2e_in_host.py tests/test_e2e_in_host_tool.py docs/plans/wiki-in-host-repo.plan.md
git commit -m "test(e2e): add the G2, G3 and G6 ratchet scenarios" -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 2/26'
```

---

### Task 3: Ratchet tool — releases, G1.7, G2.7, G5, G7, G9, G11, and the baseline

Adds the release builder (two local releases of the library under test, and the published
v1.4.1 rebuilt offline and checked against its published hash), the upgrade scenarios, and
commits the full baseline before any build task.

**Files**
- Modify: `tools/e2e_in_host.py`
- Modify: `tests/test_e2e_in_host_tool.py`
- Create: `docs/evidence/in-host-e2e-baseline.txt`

- [ ] **Step 1: Write the failing tests** — append above the `if __name__` line:

```python
class Releases(unittest.TestCase):
    def test_r2_marks_every_text_template_it_changes(self):
        self.assertEqual(e2e.R2_MARK_MD, "\n<!-- 2.0.1 -->\n")
        self.assertEqual(e2e.R2_MARK_SH, "# 2.0.1\n")

    def test_the_published_v1_hash_is_pinned(self):
        self.assertEqual(e2e.V1_SHA256,
                         "3519f9e00eb0aa2c7c3cf2eef2e9095f2bf66d307eb3df981a21b33830a0ef99")

    def test_granado_hooks_call_the_wiki_scripts_directly(self):
        self.assertIn('python3 "$root/wiki/scripts/lint.py"', e2e.GRANADO_PRE_COMMIT)
        self.assertIn('wiki/scripts/check_commit_msg.py', e2e.GRANADO_COMMIT_MSG)
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
```

Expected: `AttributeError: module 'e2e_in_host' has no attribute 'R2_MARK_MD'`, exit 1.

- [ ] **Step 3: Add to `tools/e2e_in_host.py`** — constants and builders above `# ---- scenarios`,
  scenarios after `scenario_g8`, then the final `SCENARIOS`. Also add the G2.7 control to the end
  of `scenario_g2` as shown.

```python
V1_SHA256 = "3519f9e00eb0aa2c7c3cf2eef2e9095f2bf66d307eb3df981a21b33830a0ef99"
V1_ORIGIN = "https://github.com/hieplam/wiki-harness"
R2_MARK_MD = "\n<!-- 2.0.1 -->\n"
R2_MARK_SH = "# 2.0.1\n"
SOURCE_PATHS = ("init.py", "upgrade.py", "bin", "scripts", "githooks", "templates", "tools")

# granado-espada's real hooks (2026-10-04), the G11 fixture.
GRANADO_PRE_COMMIT = """#!/bin/sh
root=$(git rev-parse --show-toplevel)
python3 "$root/wiki/scripts/lint.py" || exit 1
changed_raw=$(git diff --cached --name-status --no-renames -- wiki/sources/raw/ | grep -v '^A')
if [ -n "$changed_raw" ]; then
    echo "pre-commit: wiki/sources/raw/ is immutable" >&2
    exit 1
fi
"""
GRANADO_COMMIT_MSG = """#!/bin/sh
root=$(git rev-parse --show-toplevel)
if git diff --cached --name-only -- wiki/ | grep -q .; then
    exec python3 "$root/wiki/scripts/check_commit_msg.py" --root "$root/wiki" "$1"
fi
"""
GRANADO_SKILL = "---\nname: ask-wiki\ndescription: Hand-written bridge.\n---\n# Ask the wiki\n"


def sha256_of(path):
    """Impure edge."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unpack(archive, into):
    """Impure edge. Unpacks a payload tarball; returns its top-level directory."""
    import tarfile
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as tar:
        names = tar.getnames()
        top = names[0].split("/")[0]
        if any(n.startswith("/") or ".." in Path(n).parts for n in names):
            raise ValueError(f"payload {archive} has an unsafe member")
        tar.extractall(into)
    return into / top


def build_release(lib, work, version, origin, parent_src=None, mark=False):
    """Impure edge. The library under test, labelled `version`, built into a payload by its
    own tools/build_release.py from a throwaway repo whose origin is the local bare repo
    `origin` (which receives the tag, so `upgrade --check` works offline). With `mark`,
    every bridge template and templates/wiki.AGENTS.md gain a 2.0.1 marker."""
    src = work / f"src-{version}"
    if parent_src is None:
        src.mkdir(parents=True)
        for rel in SOURCE_PATHS:
            source = Path(lib) / rel
            if source.is_dir():
                shutil.copytree(source, src / rel,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                shutil.copy2(source, src / rel)
        init_repo(src)
        git(src, "remote", "add", "origin", str(origin))
    else:
        shutil.copytree(parent_src, src)
    write(src / "VERSION", f"{version}\n")
    if mark:
        targets = [src / "templates" / "wiki.AGENTS.md"]
        bridge = src / "templates" / "bridge"
        targets += sorted(bridge.glob("*")) if bridge.is_dir() else []
        for target in targets:
            suffix = R2_MARK_SH if target.name.endswith(".wiki-harness") else R2_MARK_MD
            with target.open("a", encoding="utf-8") as handle:
                handle.write(suffix)
    git(src, "add", "-A")
    git(src, "commit", "-q", "--no-verify", "-m", f"release {version}")
    git(src, "tag", f"v{version}")
    pushed = git(src, "push", "-q", "origin", f"v{version}")
    if pushed.returncode != 0:
        raise ValueError(f"cannot push v{version}: {last_line(pushed)}")
    out = work / "dist"
    built = run([sys.executable, src / "tools" / "build_release.py", "--tag", f"v{version}",
                 "--out-dir", out], cwd=src)
    if built.returncode != 0:
        raise ValueError(f"cannot build v{version}: {last_line(built)}")
    return src, unpack(out / f"wiki-harness-{version}.tar.gz", work / "payloads" / version)


def build_v1(work):
    """Impure edge. The published v1.4.1 payload, rebuilt offline from this repository's
    v1.4.1 tag and proven byte-identical to the published archive."""
    common = git(REPO_ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    src = work / "v1src"
    cloned = run(["git", "clone", "-q", "--branch", "v1.4.1", common, src], cwd=work)
    if cloned.returncode != 0:
        raise ValueError(f"cannot clone tag v1.4.1: {last_line(cloned)}")
    git(src, "remote", "set-url", "origin", V1_ORIGIN)
    built = run([sys.executable, src / "tools" / "build_release.py", "--tag", "v1.4.1",
                 "--out-dir", work / "v1dist"], cwd=src)
    archive = work / "v1dist" / "wiki-harness-1.4.1.tar.gz"
    if built.returncode != 0 or not archive.is_file():
        raise ValueError(f"cannot build v1.4.1: {last_line(built)}")
    if sha256_of(archive) != V1_SHA256:
        raise ValueError(f"v1.4.1 rebuilt as {sha256_of(archive)}, published {V1_SHA256}")
    return unpack(archive, work / "payloads" / "1.4.1")


def releases(lib, work):
    """Impure edge. R1 (2.0.0) and R2 (2.0.1) of the library under test."""
    origin = work / "origin.git"
    run(["git", "init", "-q", "--bare", origin], cwd=work)
    src1, r1 = build_release(lib, work, "2.0.0", origin)
    _src2, r2 = build_release(lib, work, "2.0.1", origin, parent_src=src1, mark=True)
    return r1, r2


def in_host_from(payload, root, dirty):
    """Impure edge. An in-host repo initialised by a payload's init (hand-built shape when the
    payload cannot produce it, as in_host_repo())."""
    return in_host_repo(payload, root, dirty=dirty)


def upgrade_cmd(payload, target, *flags):
    """The argv the launcher runs for `wiki-harness upgrade` with a fetched payload."""
    return [sys.executable, Path(payload) / "upgrade.py", target, *flags,
            "--library-path", payload]


def standalone_v1(v1, root):
    """Impure edge. A standalone wiki exactly as a real 1.x consumer has it."""
    r = run([sys.executable, v1 / "init.py", root.name, "--non-interactive",
             "--wiki-title", "Consumer Wiki"], cwd=root.parent)
    if r.returncode != 0:
        raise ValueError(f"v1.4.1 init failed: {last_line(r)}")
    return root


def scenario_g5(lib, work):
    """G5: upgrade --check and --apply on an in-host wiki change only its footprint, with an
    unrelated dirty file and an unrelated staged file present."""
    r1, r2 = releases(lib, work)
    root, note = in_host_from(r1, work / "g5", dirty=True)
    results = []
    r = run(upgrade_cmd(r2, "wiki", "--check")[:4], cwd=root)
    results.append(check("G5.1", "upgrade --check names v2.0.1",
                         r.returncode == 0 and "v2.0.1 available" in r.stdout, last_line(r) + note))
    before_tree, before_index = worktree_snapshot(root), index_snapshot(root)
    r = run(upgrade_cmd(r2, "wiki", "--to", "v2.0.1", "--apply", "--commit"), cwd=root)
    ok = r.returncode == 0
    results.append(check("G5.2", "upgrade --apply --commit succeeds with unrelated changes present",
                         ok, last_line(r) + note))
    footprint = footprint_of(root, before_tree)
    changed = (diff_snapshots(before_tree, worktree_snapshot(root), footprint)
               + diff_snapshots(before_index, index_snapshot(root), footprint))
    results.append(check("G5.3", "every path outside the footprint is unchanged (worktree and index)",
                         ok and not changed, f"changed {changed[:5]}" if ok else "upgrade did not succeed"))
    staged = git(root, "diff", "--cached", "--name-only").stdout.split()
    outside = [p for p in head_paths(root) if outside_footprint(p, footprint)]
    subject = git(root, "log", "-1", "--format=%s").stdout.strip()
    results.append(check("G5.4", "the upgrade commit holds only footprint paths; src/staged.py stays staged",
                         ok and subject.startswith("chore: upgrade wiki-harness") and not outside
                         and "src/staged.py" in staged,
                         f"subject {subject!r}, outside {outside[:5]}, staged {staged}"))
    agents = root / "wiki" / "wiki" / "AGENTS.md"
    manifest = read_json(root / "wiki" / ".wiki-harness-manifest.json") or {}
    results.append(check("G5.5", "R2's managed change landed and the manifest records 2.0.1",
                         ok and agents.is_file() and "<!-- 2.0.1 -->" in agents.read_text(encoding="utf-8")
                         and manifest.get("harness_version") == "2.0.1",
                         f"harness_version {manifest.get('harness_version')!r}"))
    return results


def scenario_g7(lib, work):
    """G7: upgrade keeps the bridge in step and never overwrites an owner's edit unasked."""
    r1, r2 = releases(lib, work)
    results = []
    skill_rel = ".claude/skills/ask-wiki/SKILL.md"
    plain, note = in_host_from(r1, work / "g7-plain", dirty=False)
    r = run(upgrade_cmd(r2, "wiki", "--to", "v2.0.1", "--apply"), cwd=plain)
    skill = plain / skill_rel
    results.append(check("G7.1", "an untouched ask-wiki skill gets R2's text",
                         r.returncode == 0 and skill.is_file() and "<!-- 2.0.1 -->" in skill.read_text(encoding="utf-8"),
                         last_line(r) + note))
    edited, note = in_host_from(r1, work / "g7-edited", dirty=False)
    owner = "---\nname: ask-wiki\ndescription: The owner's own words.\n---\n# Mine\n"
    if (edited / skill_rel).is_file():
        write(edited / skill_rel, owner)
        git(edited, "add", skill_rel)
        git(edited, "commit", "-q", "-m", "Edit the ask-wiki skill")
    r = run(upgrade_cmd(r2, "wiki", "--to", "v2.0.1", "--apply"), cwd=edited)
    still = (edited / skill_rel).is_file() and (edited / skill_rel).read_text(encoding="utf-8") == owner
    results.append(check("G7.2", "an owner-edited skill blocks the upgrade and stays untouched",
                         r.returncode == 1 and still, last_line(r) + note))
    r = run(upgrade_cmd(r2, "wiki", "--to", "v2.0.1", "--apply", "--adopt-drift", skill_rel), cwd=edited)
    still = (edited / skill_rel).is_file() and (edited / skill_rel).read_text(encoding="utf-8") == owner
    agents = edited / "wiki" / "wiki" / "AGENTS.md"
    results.append(check("G7.3", "--adopt-drift lets it proceed and keeps the owner's bytes",
                         r.returncode == 0 and still and "<!-- 2.0.1 -->" in agents.read_text(encoding="utf-8"),
                         last_line(r) + note))
    husky = make_husky_codebase(work / "g7-husky")
    owner_hook = (husky / ".husky" / "pre-commit").read_bytes()
    r_init = run(init_cmd(r1, "."), cwd=husky)
    r = run(upgrade_cmd(r2, "wiki", "--to", "v2.0.1", "--apply"), cwd=husky)
    side = husky / ".husky" / "pre-commit.wiki-harness"
    results.append(check("G7.4", "husky: the side file gets R2's text, the owner's hook never",
                         r_init.returncode == 0 and r.returncode == 0 and side.is_file()
                         and side.read_text(encoding="utf-8").endswith(R2_MARK_SH)
                         and (husky / ".husky" / "pre-commit").read_bytes() == owner_hook,
                         f"init {last_line(r_init)}; upgrade {last_line(r)}"))
    return results


def scenario_g9(lib, work):
    """G9: a standalone wiki built by the real v1.4.1 keeps working after upgrading to 2.0."""
    v1 = build_v1(work)
    r1, _r2 = releases(lib, work)
    root = standalone_v1(v1, work / "consumer")
    write(root / "wiki" / "lonely.md", "---\ntitle: Lonely\ntopics: [misc]\n---\nNo links in.\n")
    with (root / "index.md").open("a", encoding="utf-8") as handle:
        handle.write("\n## Misc\n- [Lonely](./wiki/lonely.md)\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "lint: add a lonely page")
    tracked_before = set(git(root, "ls-files").stdout.split())
    lint_before = sorted(run([sys.executable, "scripts/lint.py"], cwd=root).stdout.splitlines())
    r = run(upgrade_cmd(r1, ".", "--to", "v2.0.0", "--apply", "--commit"), cwd=root)
    results = []
    lint_after = sorted(run([sys.executable, "scripts/lint.py"], cwd=root).stdout.splitlines())
    results.append(check("G9.1", "lint gives the same findings on unchanged content",
                         r.returncode == 0 and lint_after == lint_before,
                         f"upgrade {last_line(r)}; before {lint_before}; after {lint_after}"))
    tracked_after = set(git(root, "ls-files").stdout.split())
    top = git(root, "rev-parse", "--show-toplevel").stdout.strip()
    results.append(check("G9.2", "structure kept: every 1.x path in place, no bridge, still the top level",
                         tracked_before <= tracked_after and not (root / "WIKI.md").exists()
                         and not (root / ".claude").exists() and Path(top).resolve() == root.resolve(),
                         f"missing {sorted(tracked_before - tracked_after)[:5]}"))
    add_raw_standalone = root / "sources" / "raw" / "probe.txt"
    write(add_raw_standalone, "raw v1\n")
    git(root, "add", "sources/raw/probe.txt")
    git(root, "commit", "-q", "-m", "chore: add a raw source")
    with add_raw_standalone.open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    git(root, "add", "sources/raw/probe.txt")
    raw = git(root, "commit", "-q", "-m", "lint: edit raw")
    git(root, "reset", "-q", "--hard", "HEAD")
    bad = git(root, "commit", "-q", "--allow-empty", "-m", "not a convention")
    empty = git(root, "commit", "-q", "--allow-empty", "-m", "lint: empty")
    results.append(check("G9.3", "hooks behave the same: raw edit and free-form subject refused, lint runs on --allow-empty",
                         raw.returncode != 0 and "ERROR RAW" in raw.stdout + raw.stderr
                         and bad.returncode != 0 and "lint:" in empty.stdout + empty.stderr,
                         f"raw {last_line(raw)}; bad {last_line(bad)}; empty {last_line(empty)}"))
    manifest = read_json(root / ".wiki-harness-manifest.json") or {}
    results.append(check("G9.4", "the manifest has no bridge section and records 2.0.0",
                         "bridge" not in manifest and manifest.get("harness_version") == "2.0.0",
                         f"keys {sorted(manifest)}"))
    return results


def scenario_g11(lib, work):
    """G11: a 1.x wiki already in the in-host shape by hand (granado-espada's) gains the bridge."""
    v1 = build_v1(work)
    r1, _r2 = releases(lib, work)
    root = make_codebase(work / "granado", dirty=False)
    r = run([sys.executable, v1 / "init.py", root / "wiki", "--non-interactive",
             "--wiki-title", "Granado Wiki"], cwd=root)
    if r.returncode != 0:
        raise ValueError(f"v1.4.1 init into wiki/ failed: {last_line(r)}")
    shutil.rmtree(root / "wiki" / ".git")
    write(root / ".githooks" / "pre-commit", GRANADO_PRE_COMMIT, 0o755)
    write(root / ".githooks" / "commit-msg", GRANADO_COMMIT_MSG, 0o755)
    write(root / ".claude" / "skills" / "ask-wiki" / "SKILL.md", GRANADO_SKILL)
    write(root / "CLAUDE.md", "# Host rules\n")
    git(root, "config", "core.hooksPath", ".githooks")
    git(root, "add", "-A")
    git(root, "commit", "-q", "--no-verify", "-m", "chore: wiki folder by hand")
    keep = {rel: (root / rel).read_bytes() for rel in
            (".githooks/pre-commit", ".claude/skills/ask-wiki/SKILL.md", "CLAUDE.md")}
    up = run(upgrade_cmd(r1, "wiki", "--to", "v2.0.0", "--apply", "--commit"), cwd=root)
    results = [check("G11.1", "upgrade exits 0", up.returncode == 0, last_line(up))]
    side_skill = root / ".claude" / "skills" / "ask-wiki" / "SKILL.wiki-harness.md"
    results.append(check("G11.2", "hand-written ask-wiki untouched; SKILL.wiki-harness.md beside it",
                         (root / ".claude/skills/ask-wiki/SKILL.md").read_bytes() == keep[".claude/skills/ask-wiki/SKILL.md"]
                         and side_skill.is_file(), last_line(up)))
    results.append(check("G11.3", "ingest-wiki skill and WIKI.md created",
                         (root / ".claude/skills/ingest-wiki/SKILL.md").is_file() and (root / "WIKI.md").is_file(),
                         last_line(up)))
    results.append(check("G11.4", "the repo's own pre-commit untouched; pre-commit.wiki-harness beside it",
                         (root / ".githooks/pre-commit").read_bytes() == keep[".githooks/pre-commit"]
                         and (root / ".githooks/pre-commit.wiki-harness").is_file(), last_line(up)))
    bridge = (read_json(root / "wiki" / ".wiki-harness-manifest.json") or {}).get("bridge") or {}
    wanted = {".claude/skills/ask-wiki/SKILL.wiki-harness.md", ".claude/skills/ingest-wiki/SKILL.md",
              "WIKI.md", ".githooks/pre-commit.wiki-harness", ".githooks/commit-msg.wiki-harness"}
    results.append(check("G11.5", "the manifest's bridge section lists them",
                         wanted <= set(bridge), f"bridge keys {sorted(bridge)}"))
    lint_out = lint(root)
    results.append(check("G11.6", "root CLAUDE.md untouched, link line printed, lint WARNs BRIDGE",
                         (root / "CLAUDE.md").read_bytes() == keep["CLAUDE.md"] and "@WIKI.md" in up.stdout
                         and "WARN BRIDGE ../CLAUDE.md" in lint_out.stdout, last_line(lint_out)))
    results.append(check("G11.7", "granado's hooks prove the wiki checks run: no ERROR HOOKS",
                         "ERROR HOOKS" not in lint_out.stdout, last_line(lint_out)))
    return results


def scenario_g1_payload(lib, work):
    """G1.7: init through a built payload (no .git in the library) produces the layout."""
    r1, _r2 = releases(lib, work)
    root = make_codebase(work / "g1-payload")
    r = run(init_cmd(r1, root), cwd=work)
    manifest = read_json(root / "wiki" / ".wiki-harness-manifest.json") or {}
    return [check("G1.7", "init from a release payload produces the in-host layout",
                  r.returncode == 0 and (root / "wiki" / "index.md").is_file()
                  and not (root / "wiki" / ".git").exists() and manifest.get("source_ref") == "v2.0.0",
                  last_line(r))]
```

Add the G2.7 control at the end of `scenario_g2`, right before its `return results`:

```python
    v1 = build_v1(work)
    control = standalone_v1(v1, work / "g2-standalone")
    write(control / "sources" / "raw" / "probe.txt", "raw v1\n")
    git(control, "add", "sources/raw/probe.txt")
    git(control, "commit", "-q", "-m", "chore: add a raw source")
    with (control / "sources" / "raw" / "probe.txt").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    git(control, "add", "sources/raw/probe.txt")
    r = git(control, "commit", "-q", "-m", "lint: edit raw")
    results.append(check("G2.7", "control: the same raw edit is refused in a v1.4.1 standalone wiki",
                         r.returncode != 0 and "ERROR RAW sources/raw/probe.txt" in r.stdout + r.stderr,
                         last_line(r)))
```

And the final registry:

```python
SCENARIOS = (
    ("G1", scenario_g1),
    ("G1.7", scenario_g1_payload),
    ("G2", scenario_g2),
    ("G3", scenario_g3),
    ("G4", scenario_g4),
    ("G5", scenario_g5),
    ("G6", scenario_g6),
    ("G7", scenario_g7),
    ("G8", scenario_g8),
    ("G9", scenario_g9),
    ("G11", scenario_g11),
)
```

`scenario_selected("G1", ["G1.7"])` is true, so `--only G1.7` also runs scenario `G1`; that is
accepted (the result filter still prints only `G1.7`).

- [ ] **Step 4: Run the unit tests, then record the baseline in the background**

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
python3 tools/e2e_in_host.py > docs/evidence/in-host-e2e-baseline.txt 2>&1; echo "exit=$?"
```

Run the second command as a background job (Global Constraint 4) and wait for it. Expected:
`exit=1`; the file ends with a `TOTAL` line; `grep -c '^PASS' docs/evidence/in-host-e2e-baseline.txt`
and `grep -c '^FAIL' …` are recorded in the commit message body. The passes the spec predicts on
the 1.4.1 library: G1.1 and G1.3 for the two `empty-*` forms, G2.7, G3.1, G4.1–G4.3, G5.1,
G9.1–G9.4, G11.1, G11.7. Any other PASS is reported to the Warchief before committing (a
baseline is measured, never adjusted).

#### Verify

- **Goal:** the committed tool measures the baseline for G1–G9 and G11 before any build task
  (card "Goals", Ratchet column).
- **Red:** `python3 -m unittest tests.test_e2e_in_host_tool -q` → `AttributeError: module 'e2e_in_host' has no attribute 'R2_MARK_MD'`, exit 1.
- **Green:** `python3 -m unittest tests.test_e2e_in_host_tool -q` → `OK`, exit 0; and `tail -n 1 docs/evidence/in-host-e2e-baseline.txt` → a `TOTAL` line whose second number is 81 (24 G1 + 1 G1.7 + 8 G2 + 7 G3 + 4 G4 + 5 G5 + 6 G6 + 4 G7 + 1 G8 + 4 G9 + 7 G11), with `grep -c '^PASS' docs/evidence/in-host-e2e-baseline.txt` → `16`.
- **Stub check:** a baseline file written by hand would not reproduce: `python3 tools/e2e_in_host.py --only G9 --only G11.7` re-run in the audit must reproduce its G9 and G11.7 lines; a builder that skipped the published-hash check could not report `PASS G9.1` once the tag is missing (setup FAIL).

#### Done

```bash
python3 -m unittest tests.test_e2e_in_host_tool -q
test -s docs/evidence/in-host-e2e-baseline.txt
```

- [ ] **Step 5: Commit**

```bash
git add tools/e2e_in_host.py tests/test_e2e_in_host_tool.py docs/evidence/in-host-e2e-baseline.txt docs/plans/wiki-in-host-repo.plan.md
git commit -m "test(e2e): add the upgrade and release scenarios and record the in-host baseline" -m "Baseline on the unchanged 1.4.1 library: see docs/evidence/in-host-e2e-baseline.txt." -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 3/26'
```

---

### Task 4: `scripts/repo_layout.py` — the layout, side-file and hooks decisions (pure)

One new vendored module holding every decision about where a wiki sits in its repository
(spec §3, §5.2, §5.3, §5.6). Nothing calls it yet.

**Files**
- Create: `scripts/repo_layout.py`
- Create: `tests/test_repo_layout.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_repo_layout.py`:

```python
"""repo_layout.py: pure decisions about where a wiki sits in its repository."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import repo_layout as rl  # noqa: E402

P = PurePosixPath


class ClassifyLayout(unittest.TestCase):
    def test_no_work_tree(self):
        self.assertIsNone(rl.classify_layout(P("/r/wiki"), None))

    def test_standalone(self):
        self.assertEqual(rl.classify_layout(P("/r"), P("/r")), rl.STANDALONE)

    def test_in_host(self):
        self.assertEqual(rl.classify_layout(P("/r/wiki"), P("/r")), rl.IN_HOST)

    def test_other_folders_are_subfolders(self):
        self.assertEqual(rl.classify_layout(P("/r/docs/kb"), P("/r")), rl.SUBFOLDER)
        self.assertEqual(rl.classify_layout(P("/r/kb"), P("/r")), rl.SUBFOLDER)
        self.assertEqual(rl.classify_layout(P("/r/x/wiki"), P("/r")), rl.SUBFOLDER)


class SidePath(unittest.TestCase):
    def test_marker_goes_before_the_last_suffix(self):
        self.assertEqual(rl.side_path(".claude/skills/ask-wiki/SKILL.md"),
                         ".claude/skills/ask-wiki/SKILL.wiki-harness.md")
        self.assertEqual(rl.side_path("WIKI.md"), "WIKI.wiki-harness.md")

    def test_marker_is_appended_without_a_suffix(self):
        self.assertEqual(rl.side_path(".husky/pre-commit"), ".husky/pre-commit.wiki-harness")
        self.assertEqual(rl.side_path(".gitignore"), ".gitignore.wiki-harness")


class PlanHooks(unittest.TestCase):
    def test_nothing_configured_and_no_hooks_wires(self):
        self.assertEqual(rl.plan_hooks(None, None, ()), rl.HooksPlan(rl.WIRE, None))

    def test_already_pointing_at_the_wiki_hooks(self):
        self.assertEqual(rl.plan_hooks("wiki/.githooks", "wiki/.githooks", ()),
                         rl.HooksPlan(rl.ALREADY_WIRED, "wiki/.githooks"))

    def test_a_repo_hooks_dir_gets_side_files(self):
        self.assertEqual(rl.plan_hooks(".husky", ".husky", ()),
                         rl.HooksPlan(rl.SIDE_FILES, ".husky"))

    def test_husky_nine_side_files_go_beside_the_editable_hook(self):
        self.assertEqual(rl.plan_hooks(".husky/_", ".husky/_", ()),
                         rl.HooksPlan(rl.SIDE_FILES, ".husky"))

    def test_hooks_in_the_git_dir_are_print_only(self):
        self.assertEqual(rl.plan_hooks(None, None, ("pre-commit",)),
                         rl.HooksPlan(rl.PRINT_ONLY, None))

    def test_a_hooks_path_outside_the_work_tree_is_print_only(self):
        self.assertEqual(rl.plan_hooks("/home/me/hooks", None, ()),
                         rl.HooksPlan(rl.PRINT_ONLY, None))


class UnprovenHooks(unittest.TestCase):
    def test_the_wiki_hooks_dir_proves_both(self):
        texts = {"pre-commit": "x", "commit-msg": "x"}
        self.assertEqual(rl.unproven_hooks("wiki", True, texts, {}, []), [])

    def test_a_merged_side_line_proves_its_hook(self):
        texts = {"pre-commit": '#!/bin/sh\n"$(git rev-parse --show-toplevel)/wiki/.githooks/pre-commit" || exit 1\n'}
        self.assertEqual(rl.unproven_hooks("wiki", False, texts, {}, []), ["commit-msg"])

    def test_a_comment_proves_nothing(self):
        texts = {"pre-commit": "# note: wiki/.githooks/pre-commit\n",
                 "commit-msg": "  # wiki/.githooks/commit-msg\n"}
        self.assertEqual(rl.unproven_hooks("wiki", False, texts, {}, []),
                         ["pre-commit", "commit-msg"])

    def test_calling_the_scripts_directly_proves_them(self):
        texts = {"pre-commit": 'python3 "$root/wiki/scripts/lint.py" || exit 1\n',
                 "commit-msg": 'exec python3 "$root/wiki/scripts/check_commit_msg.py" --root x "$1"\n'}
        self.assertEqual(rl.unproven_hooks("wiki", False, texts, {}, []), [])

    def test_the_gate_script_alone_proves_neither(self):
        texts = {"pre-commit": "python3 wiki/scripts/commit_gate.py pre-commit\n"}
        self.assertEqual(rl.unproven_hooks("wiki", False, texts, {}, []),
                         ["pre-commit", "commit-msg"])

    def test_husky_parent_hook_counts(self):
        parent = {"pre-commit": "wiki/.githooks/pre-commit\n", "commit-msg": "wiki/.githooks/commit-msg \"$1\"\n"}
        self.assertEqual(rl.unproven_hooks("wiki", False, {"pre-commit": ". h", "commit-msg": ". h"},
                                           parent, []), [])

    def test_a_manager_config_counts(self):
        config = "      - id: w\n        entry: wiki/.githooks/pre-commit\n        entry: wiki/.githooks/commit-msg\n"
        self.assertEqual(rl.unproven_hooks("wiki", False, {}, {}, [config]), [])

    def test_a_commented_manager_line_counts_for_nothing(self):
        config = "# entry: wiki/.githooks/pre-commit\n"
        self.assertEqual(rl.unproven_hooks("wiki", False, {}, {}, [config]),
                         ["pre-commit", "commit-msg"])


class Messages(unittest.TestCase):
    def test_without_a_repo_hooks_dir_the_fix_is_the_config(self):
        self.assertEqual(
            rl.hooks_message("wiki", None, ["pre-commit", "commit-msg"]),
            "the wiki's pre-commit and commit-msg check(s) do not run on commits - "
            "run: git config core.hooksPath wiki/.githooks")

    def test_with_a_repo_hooks_dir_the_fix_is_the_merge(self):
        self.assertEqual(
            rl.hooks_message("wiki", ".husky", ["pre-commit"]),
            "the wiki's pre-commit check(s) do not run on commits - "
            "add the line in .husky/pre-commit.wiki-harness to .husky/pre-commit")

    def test_the_link_line_carries_the_token(self):
        self.assertIn(rl.BRIDGE_LINK_TOKEN, rl.BRIDGE_LINK_LINE)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_repo_layout -q
```

Expected: `ModuleNotFoundError: No module named 'repo_layout'`, exit 1.

- [ ] **Step 3: Write `scripts/repo_layout.py`**

```python
#!/usr/bin/env python3
"""Where a wiki sits in its git repository, and what that means for its commit hooks.

A wiki folder is in one of three layouts (classify_layout): it IS the repository
("standalone" -- every 1.x wiki), it is the repository's top-level `wiki/` folder
("in-host" -- what init produces since 2.0), or it is some other folder of a repository
("subfolder" -- hand-made setups only).

Pure: every function here takes already-gathered data and returns a value; nothing
reads a file, runs git or reads the environment. lint.py, commit_gate.py, init.py and
upgrade.py gather the facts at their own edges and ask these functions what to do.
Pure core: classify_layout(), side_path(), side_files_dir(), wiki_hooks_rel(),
plan_hooks(), proof_tokens(), calls_any(), unproven_hooks(), hooks_message().
Impure edges: none.

Python 3 stdlib only.
"""
from __future__ import annotations

from collections import namedtuple
from pathlib import PurePosixPath

WIKI_FOLDER = "wiki"
SIDE_MARKER = "wiki-harness"
HOOK_NAMES = ("pre-commit", "commit-msg")
# Set by commit_gate.py when it runs lint.py: the pre-commit gate is running, which
# proves the hooks are wired, so lint does not ask (spec 5.3).
GATE_ENV = "WIKI_HARNESS_GATE"
BRIDGE_LINK_TOKEN = "@WIKI.md"
BRIDGE_LINK_LINE = ("Wiki: before you answer a question about this project's domain or "
                    "change anything under `wiki/`, read @WIKI.md.")
# Hook managers whose config, at the repository root, may run the wiki's hooks (ruling S3).
MANAGER_CONFIG_FILES = (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml",
                        ".lefthook.yml", ".lefthook.yaml")

STANDALONE = "standalone"
IN_HOST = "in-host"
SUBFOLDER = "subfolder"

WIRE = "wire"                     # set core.hooksPath to the wiki's own .githooks
SIDE_FILES = "side-files"         # write <dir>/<hook>.wiki-harness beside the repo's hooks
ALREADY_WIRED = "already-wired"   # core.hooksPath already names the wiki's .githooks
PRINT_ONLY = "print-only"         # the repo's hooks live outside its work tree: write nothing
HooksPlan = namedtuple("HooksPlan", "action hooks_dir")


def classify_layout(wiki_root, top_level):
    """Pure. `wiki_root` and `top_level` are resolved absolute paths; `top_level` is None
    when the wiki is not inside a git work tree (then the answer is None)."""
    if top_level is None:
        return None
    if wiki_root == top_level:
        return STANDALONE
    if wiki_root.parent == top_level and wiki_root.name == WIKI_FOLDER:
        return IN_HOST
    return SUBFOLDER


def side_path(path):
    """Pure. The D4 side-file name for a repo-relative POSIX path: the marker goes before
    the last suffix (`SKILL.md` -> `SKILL.wiki-harness.md`), or at the end when there is
    none (`pre-commit` -> `pre-commit.wiki-harness`)."""
    p = PurePosixPath(path)
    if p.suffix:
        return str(p.with_name(f"{p.stem}.{SIDE_MARKER}{p.suffix}"))
    return str(p.with_name(f"{p.name}.{SIDE_MARKER}"))


def side_files_dir(hooks_dir_rel):
    """Pure. Where the side files go for a repo-relative hooks dir. Husky 9 points
    core.hooksPath at its generated `.husky/_` stubs (ignored by git); the hook a person
    edits is the same-named file one level up, so the side files go there."""
    p = PurePosixPath(hooks_dir_rel)
    return str(p.parent) if p.name == "_" else str(p)


def wiki_hooks_rel(wiki_rel):
    """Pure. The wiki's own hooks folder, relative to the repository top level."""
    return f"{wiki_rel}/.githooks"


def plan_hooks(configured_hooks_path, configured_dir_rel, default_dir_hooks, wiki_rel=WIKI_FOLDER):
    """Pure. D4 (spec 5.2). `configured_hooks_path` is the repo's own core.hooksPath value
    or None when unset; `configured_dir_rel` is that value resolved against the top level
    and expressed relative to it, or None when it lies outside the work tree or inside
    .git; `default_dir_hooks` names the HOOK_NAMES files present in $GIT_DIR/hooks."""
    if configured_hooks_path is None and not default_dir_hooks:
        return HooksPlan(WIRE, None)
    if configured_hooks_path is not None and configured_dir_rel == wiki_hooks_rel(wiki_rel):
        return HooksPlan(ALREADY_WIRED, configured_dir_rel)
    if configured_hooks_path is not None and configured_dir_rel is not None:
        return HooksPlan(SIDE_FILES, side_files_dir(configured_dir_rel))
    return HooksPlan(PRINT_ONLY, None)


def proof_tokens(wiki_rel, hook):
    """Pure. Strings whose presence on a non-comment line proves `hook` runs the wiki's
    check. commit_gate.py is deliberately not one: one line naming it could be either
    hook, and proving both from it would under-check."""
    direct = "lint.py" if hook == "pre-commit" else "check_commit_msg.py"
    return (f"{wiki_rel}/.githooks/{hook}", f"{wiki_rel}/scripts/{direct}")


def calls_any(text, tokens):
    """Pure. True when a line of `text` that is not a `#` comment contains a token."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if any(token in stripped for token in tokens):
            return True
    return False


def unproven_hooks(wiki_rel, hooks_dir_is_wiki_hooks, hook_texts, parent_hook_texts, manager_texts):
    """Pure. G3: the HOOK_NAMES not proven to run the wiki's checks (spec 5.3).
    `hook_texts`: {hook: text} for each hook file in the effective hooks dir that exists
    and is executable; `parent_hook_texts`: the same-named files one level up when that
    dir is husky's `_`; `manager_texts`: the texts of the MANAGER_CONFIG_FILES present at
    the repository root."""
    missing = []
    for hook in HOOK_NAMES:
        if hooks_dir_is_wiki_hooks and hook in hook_texts:
            continue
        tokens = proof_tokens(wiki_rel, hook)
        texts = [hook_texts.get(hook), parent_hook_texts.get(hook), *manager_texts]
        if any(text is not None and calls_any(text, tokens) for text in texts):
            continue
        missing.append(hook)
    return missing


def hooks_message(wiki_rel, repo_hooks_dir, missing):
    """Pure. The HOOKS finding text for an in-host or subfolder wiki. `repo_hooks_dir` is
    the repo's own hooks dir (relative to the top level) when it has one inside the work
    tree; then the fix is the merge, never the config, which would switch those hooks off."""
    names = " and ".join(missing)
    if repo_hooks_dir is None:
        fix = f"run: git config core.hooksPath {wiki_hooks_rel(wiki_rel)}"
    else:
        fix = ", ".join(f"add the line in {repo_hooks_dir}/{hook}.{SIDE_MARKER} to "
                        f"{repo_hooks_dir}/{hook}" for hook in missing)
    return f"the wiki's {names} check(s) do not run on commits - {fix}"
```

- [ ] **Step 4: Run the tests**

```bash
python3 -m unittest tests.test_repo_layout tests.test_genericity tests.test_build_release -q
```

Expected: `OK` (the genericity sweep and the payload test both cover the new `scripts/*.py`).

#### Verify

- **Goal:** the decisions behind G3 (hooks proof, S3 manager configs), D4 (`plan_hooks`), K11
  (`side_path`) and the layout model (spec §3) exist as tested pure functions.
- **Red:** `python3 -m unittest tests.test_repo_layout -q` → `ModuleNotFoundError: No module named 'repo_layout'`, exit 1.
- **Green:** `python3 -m unittest tests.test_repo_layout tests.test_genericity tests.test_build_release -q` → `OK`, exit 0.
- **Stub check:** a `classify_layout` that always returns `"standalone"`, an `unproven_hooks`
  that returns `[]`, or a `side_path` that returns its input each fail named tests above
  (`test_in_host`, `test_a_comment_proves_nothing`, `test_marker_goes_before_the_last_suffix`).

#### Done

```bash
python3 -m unittest tests.test_repo_layout -q
```

- [ ] **Step 5: Commit**

```bash
git add scripts/repo_layout.py tests/test_repo_layout.py docs/plans/wiki-in-host-repo.plan.md
git commit -m "feat(scripts): add repo_layout, the pure layout and hooks decisions" -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 4/26'
```

---

### Task 5: `init.scaffold_wiki` and the test fixtures that build wikis as repositories hold them

Extracts init's wiki-writing steps into one function (no behaviour change), adds
`tests/wiki_fixtures.py`, and moves every test that needs a standalone wiki off `init.py`
before Task 13 changes what `init` produces. Assertions in the moved tests do not change
(G9 Verify).

**Files**
- Modify: `init.py` (add `scaffold_wiki`; `main` calls it for steps 4–10)
- Create: `tests/wiki_fixtures.py`
- Create: `tests/test_wiki_fixtures.py`
- Modify: `tests/test_upgrade.py` (`_run_init` body only, and one import)
- Modify: `tests/test_gap_cli.py` (`test_add_from_a_parent_directory_writes_into_the_wiki`: the fixture lines only)
- Modify: `tests/test_lint_checks.py` (`test_markdown_link_in_a_recorded_question_does_not_block_lint`: the fixture lines only)

- [ ] **Step 1: Write the failing tests** — `tests/test_wiki_fixtures.py`:

```python
"""The fixtures that build wikis the way repositories hold them (tests/wiki_fixtures.py)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wiki_fixtures as wf  # noqa: E402


class StandaloneFixture(unittest.TestCase):
    def test_a_1x_consumer_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = wf.build_standalone_wiki(Path(tmp) / "consumer")
            self.assertEqual(wf.git(root, "config", "--get", "core.hooksPath").stdout.strip(), ".githooks")
            top = Path(wf.git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
            self.assertEqual(top, root.resolve())
            self.assertTrue((root / ".wiki-harness-manifest.json").is_file())
            self.assertIn("chore: scaffold from wiki-harness v",
                          wf.git(root, "log", "-1", "--format=%s").stdout)
            lint = subprocess.run([sys.executable, "scripts/lint.py"], cwd=root,
                                  capture_output=True, text=True, env=wf.git_env(), timeout=300)
            self.assertEqual(lint.returncode, 0, lint.stdout)


class InHostFixture(unittest.TestCase):
    def test_the_wiki_is_a_folder_of_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = wf.build_in_host_wiki(Path(tmp) / "host")
            self.assertTrue((root / "wiki" / ".wiki-harness-manifest.json").is_file())
            self.assertFalse((root / "wiki" / ".git").exists())
            self.assertTrue((root / "src" / "app.py").is_file())
            self.assertEqual(wf.git(root, "config", "--get", "core.hooksPath").stdout.strip(),
                             "wiki/.githooks")
            self.assertEqual(wf.git(root, "status", "--porcelain").stdout, "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_wiki_fixtures -q
```

Expected: `ModuleNotFoundError: No module named 'wiki_fixtures'`, exit 1.

- [ ] **Step 3: Add `scaffold_wiki` to `init.py`** — above `read_version`, and make `main` call
  it in place of its seven step-4-to-10 lines:

```python
def scaffold_wiki(library_root, wiki_root, values, origins):
    """Steps 4-10: write every wiki-folder file, then its manifest, into `wiki_root` (which
    must exist). Returns (scripts_paths, hooks_paths). The repository around the wiki,
    its config and its commit belong to the caller."""
    create_gitkeeps(wiki_root)                                       # step 4
    scripts_paths = copy_scripts(library_root, wiki_root)             # step 5
    hooks_paths = copy_hooks(library_root, wiki_root)                 # step 5
    render_root_templates(library_root, wiki_root, values)            # step 6
    copy_managed_agents(library_root, wiki_root)                      # step 7
    seed_starters(library_root, wiki_root, origins)                   # step 8
    seed_claude_stubs(library_root, wiki_root)                        # step 9
    write_manifest_file(library_root, wiki_root, values,              # step 10
                        scripts_paths, hooks_paths)
    return scripts_paths, hooks_paths
```

In `main`, steps 4–10 become `scaffold_wiki(library_root, target, values, origins)`. Add
`scaffold_wiki()` to the module docstring's list of impure edges.

- [ ] **Step 4: Write `tests/wiki_fixtures.py`**

```python
"""Test fixtures: wikis built the way real repositories hold them.

build_standalone_wiki() reproduces a 1.x consumer's shape -- the wiki root IS the
repository, core.hooksPath .githooks, the placeholder identity 1.x init wrote into the
repo config, one scaffold commit made through the wiki's own hooks. Since 2.0 init never
produces this shape (card D3), but every 1.x wiki still has it (D6), so the lint, upgrade
and hook tests that need it build it here instead of running init.py.

build_in_host_wiki() builds the 2.0 layout for script-level tests: a repository with code,
the wiki folder at wiki/, core.hooksPath wiki/.githooks, one commit.

Both write the wiki through the library's own init.scaffold_wiki(), so the wiki's files
are exactly what init writes. Impure by nature; every git call isolates host config and
is bounded.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALUES = {"wiki_title": "Sample Wiki", "org_name": "Sample Org",
          "content_language": "English", "repo_name": "sample-wiki"}
IDENTITY = {"GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}


def git_env(identity=True):
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if identity:
        env.update(IDENTITY)
    return env


def git(root, *args, identity=True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          env=git_env(identity), timeout=120)


def load_init(library_root=ROOT):
    path = Path(library_root) / "init.py"
    spec = importlib.util.spec_from_file_location(f"wiki_fixture_init_{abs(hash(str(path)))}", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_standalone_wiki(target, library_root=ROOT, values=None, origins=("session",)):
    """A 1.x consumer's standalone wiki at `target`."""
    target = Path(target)
    library_root = Path(library_root)
    init_mod = load_init(library_root)
    values = init_mod.apply_defaults(dict(values or VALUES), target.resolve().name)
    target.mkdir(parents=True, exist_ok=True)
    git(target, "init", "-q")
    git(target, "config", "user.email", "init@wiki-harness.invalid")
    git(target, "config", "user.name", "wiki-harness init")
    init_mod.scaffold_wiki(library_root, target, values, list(origins))
    git(target, "config", "core.hooksPath", ".githooks")
    git(target, "add", "-A")
    subject = f"chore: scaffold from wiki-harness v{init_mod.read_version(library_root)}"
    done = git(target, "commit", "-q", "-m", subject, identity=False)
    if done.returncode != 0:
        raise RuntimeError(f"standalone fixture commit failed: {done.stdout}{done.stderr}")
    return target


def build_in_host_wiki(root, library_root=ROOT, values=None, wire=True):
    """A repository with code and the wiki folder at wiki/."""
    root = Path(root)
    library_root = Path(library_root)
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "app.py").write_text('print("app")\n', encoding="utf-8")
    git(root, "add", "src/app.py")
    git(root, "commit", "-q", "-m", "feat: host code")
    init_mod = load_init(library_root)
    values = init_mod.apply_defaults(dict(values or VALUES), root.resolve().name)
    (root / "wiki").mkdir()
    init_mod.scaffold_wiki(library_root, root / "wiki", values, ["session"])
    if wire:
        git(root, "config", "core.hooksPath", "wiki/.githooks")
    git(root, "add", "wiki")
    done = git(root, "commit", "-q", "--no-verify", "-m", "chore: scaffold the wiki folder", "--", "wiki")
    if done.returncode != 0:
        raise RuntimeError(f"in-host fixture commit failed: {done.stdout}{done.stderr}")
    return root
```

- [ ] **Step 5: Move the standalone fixtures off `init.py`**

`tests/test_upgrade.py`: add `sys.path.insert(0, str(Path(__file__).resolve().parent))` and
`import wiki_fixtures  # noqa: E402` beside the existing imports, and replace the body of
`_run_init` (and only its body) with:

```python
def _run_init(library_root, target, answers=INIT_ANSWERS):
    """A standalone wiki exactly as a 1.x consumer has it (tests/wiki_fixtures.py); since
    2.0, init.py itself only produces the in-host layout."""
    try:
        wiki_fixtures.build_standalone_wiki(target, library_root, answers)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        return subprocess.CompletedProcess([], 1, "", str(exc))
    return subprocess.CompletedProcess([], 0, "", "")
```

`tests/test_gap_cli.py` `test_add_from_a_parent_directory_writes_into_the_wiki` and
`tests/test_lint_checks.py` `test_markdown_link_in_a_recorded_question_does_not_block_lint`:
replace the `init_result = subprocess.run([... init_py ...])` statement and its
`assertEqual(init_result.returncode, 0, …)` line with
`wiki_fixtures.build_standalone_wiki(target)` (plus the same two import lines). Every other line
of both tests stays as it is.

- [ ] **Step 6: Run the tests** (the `test_upgrade` run is long on a slow machine; run it in the
  background and wait)

```bash
python3 -m unittest tests.test_wiki_fixtures tests.test_gap_cli tests.test_lint_checks tests.test_init -q
python3 -m unittest tests.test_upgrade -q
```

Expected: both print `OK`.

#### Verify

- **Goal:** G9's precondition — every lint/upgrade/hook test that needs a standalone wiki gets
  the 1.x consumer's shape from a fixture, with unchanged assertions, before `init` changes
  (card "Known environment facts": "a test that needs a standalone wiki must build it the way a
  real 1.x consumer has it").
- **Red:** `python3 -m unittest tests.test_wiki_fixtures -q` → `ModuleNotFoundError: No module named 'wiki_fixtures'`, exit 1.
- **Green:** `python3 -m unittest tests.test_wiki_fixtures tests.test_gap_cli tests.test_lint_checks tests.test_init -q` → `OK`, exit 0; `python3 -m unittest tests.test_upgrade -q` → `OK`, exit 0; `git diff main -- tests/test_upgrade.py` touches only `_run_init` and the imports.
- **Stub check:** a `build_standalone_wiki` that skipped `scaffold_wiki` leaves no manifest and
  fails `test_a_1x_consumer_shape`; one that skipped the hooks config fails its
  `core.hooksPath` assertion; `test_upgrade`'s 58 tests exercise it for real.

#### Done

```bash
python3 -m unittest tests.test_wiki_fixtures tests.test_gap_cli -q
```

- [ ] **Step 7: Commit**

```bash
git add init.py tests/wiki_fixtures.py tests/test_wiki_fixtures.py tests/test_upgrade.py tests/test_gap_cli.py tests/test_lint_checks.py docs/plans/wiki-in-host-repo.plan.md
git commit -m "test(fixtures): build standalone and in-host wikis without init.py" -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 5/26'
```

---

### Task 6: Raw immutability in-host — `git diff --relative`

Fixes spec §1.2 (the card's Blocker). Standalone output is unchanged: `--relative` from the top
level is the identity.

**Files**
- Modify: `scripts/lint.py:490-492` (`git_changes`)
- Create: `tests/test_in_host_raw.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_in_host_raw.py`:

```python
"""RAW in the in-host layout, with the standalone control (spec 1.2)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))
import wiki_fixtures as wf  # noqa: E402
from lint import check_raw_immutability, git_changes  # noqa: E402


def _add_raw(repo, rel):
    path = Path(repo) / rel
    path.write_text("raw v1\n", encoding="utf-8")
    wf.git(repo, "add", rel)
    wf.git(repo, "commit", "-q", "--no-verify", "-m", "chore: raw")


class InHostRaw(unittest.TestCase):
    def test_a_staged_edit_is_seen_wiki_relative_and_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = wf.build_in_host_wiki(Path(tmp) / "host")
            _add_raw(root, "wiki/sources/raw/a.txt")
            (root / "wiki/sources/raw/a.txt").write_text("raw v2\n", encoding="utf-8")
            wf.git(root, "add", "wiki/sources/raw/a.txt")
            changes = git_changes(root / "wiki")
            self.assertEqual(changes, [("M", "sources/raw/a.txt")])
            self.assertEqual([f.code for f in check_raw_immutability(changes)], ["RAW"])

    def test_moving_a_raw_file_out_of_the_wiki_is_a_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = wf.build_in_host_wiki(Path(tmp) / "host")
            _add_raw(root, "wiki/sources/raw/a.txt")
            wf.git(root, "mv", "wiki/sources/raw/a.txt", "src/a.txt")
            self.assertEqual(git_changes(root / "wiki"), [("D", "sources/raw/a.txt")])

    def test_lint_from_the_repo_root_reports_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = wf.build_in_host_wiki(Path(tmp) / "host")
            _add_raw(root, "wiki/sources/raw/a.txt")
            (root / "wiki/sources/raw/a.txt").write_text("raw v2\n", encoding="utf-8")
            wf.git(root, "add", "wiki/sources/raw/a.txt")
            result = subprocess.run([sys.executable, "wiki/scripts/lint.py"], cwd=root,
                                    capture_output=True, text=True, env=wf.git_env(), timeout=300)
            self.assertIn("ERROR RAW sources/raw/a.txt: raw source changed (git status M)", result.stdout)


class StandaloneControl(unittest.TestCase):
    def test_the_standalone_report_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = wf.build_standalone_wiki(Path(tmp) / "consumer")
            _add_raw(root, "sources/raw/a.txt")
            (root / "sources/raw/a.txt").write_text("raw v2\n", encoding="utf-8")
            wf.git(root, "add", "sources/raw/a.txt")
            self.assertEqual(git_changes(root), [("M", "sources/raw/a.txt")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_in_host_raw -q
```

Expected: 3 failures, e.g. `[('M', 'wiki/sources/raw/a.txt')] != [('M', 'sources/raw/a.txt')]`;
`StandaloneControl` passes. Exit 1.

- [ ] **Step 3: Change `git_changes`** — the argv gains `--relative`, and the docstring says why:

```python
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-status", "--relative"],
        capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
```

Docstring addition: "`--relative` makes the paths relative to the wiki root and drops changes
outside it. Without it git prints top-level-relative paths, and in a repository that keeps the
wiki in a folder every `sources/raw/` change read as `wiki/sources/raw/…` and slipped past the
check (#46 7a)."

- [ ] **Step 4: Run the tests**

```bash
python3 -m unittest tests.test_in_host_raw tests.test_harness_e2e tests.test_lint_cli -q
python3 tools/e2e_in_host.py --only G2.1 --only G6.W1
```

Expected: `OK`; the ratchet lines stay FAIL until the gate (Task 10) lets a commit reach lint —
this task's proof is the unit test.

#### Verify

- **Goal:** G2 ("a staged edit, delete or rename of an existing raw file is refused" in-host) and
  H5 (the standalone RAW finding fires in-host on the equivalent input).
- **Red:** `python3 -m unittest tests.test_in_host_raw -q` → `FAILED (failures=3)`, first diff `[('M', 'wiki/sources/raw/a.txt')] != [('M', 'sources/raw/a.txt')]`.
- **Green:** `python3 -m unittest tests.test_in_host_raw tests.test_harness_e2e tests.test_lint_cli -q` → `OK`, exit 0.
- **Stub check:** without `--relative` the in-host tests fail exactly as in Red; dropping RAW
  findings would fail `test_lint_from_the_repo_root_reports_it`.

#### Done

```bash
python3 -m unittest tests.test_in_host_raw -q
```

- [ ] **Step 5: Commit**

```bash
git add scripts/lint.py tests/test_in_host_raw.py docs/plans/wiki-in-host-repo.plan.md
git commit -m "fix(lint): read staged changes relative to the wiki root" -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 6/26'
```

---

### Task 7: The gap ledger's append-only check in-host — `HEAD:./` and `:0:./`

Fixes spec §1.4 (found by E2 P7). Every revision path in `scripts/gap_lint.py` becomes
`./`-prefixed, which git resolves against `cwd=<wiki root>` in every layout.

**Files**
- Modify: `scripts/gap_lint.py` (`_path_in_head`, `_git_bytes`, `_path_staged`, `_staged_bytes`)
- Create: `tests/test_in_host_gap_lint.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_in_host_gap_lint.py`:

```python
"""The gap ledger stays append-only when the wiki is a folder of its repository (spec 1.4)."""
from __future__ import annotations

import datetime
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))
import wiki_fixtures as wf  # noqa: E402
import gap  # noqa: E402
import gap_lint  # noqa: E402

NOW = datetime.datetime(2026, 10, 5, 9, 0, tzinfo=datetime.timezone.utc)
ADD = ["add", "--no-commit", "--service", "acme", "--session", "s1", "--context", "c",
       "--prompt", "p", "--question", "what torque", "--wiki-answer", "none",
       "--answer-given", "none", "--topics", "widgets"]


def _wiki_with_a_committed_gap(tmp):
    root = wf.build_in_host_wiki(Path(tmp) / "host")
    assert gap.main(ADD, root=root / "wiki", now=NOW) == 0
    wf.git(root, "add", "wiki/gaps")
    wf.git(root, "commit", "-q", "--no-verify", "-m", "gap(gap-2026-10-05-001): record")
    return root


def _codes(findings):
    return sorted({f.code for f in findings})


class InHostLedger(unittest.TestCase):
    def test_an_unstaged_edit_of_a_committed_line_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _wiki_with_a_committed_gap(tmp)
            ledger = root / "wiki/gaps/knowledge-gaps.jsonl"
            ledger.write_text(ledger.read_text(encoding="utf-8").replace("what torque", "WHAT TORQUE"),
                              encoding="utf-8")
            findings = gap_lint.run(root / "wiki")
            self.assertTrue(any(f.code == "GAP_APPEND" and "diverges" in f.message for f in findings),
                            findings)

    def test_deleting_the_whole_gaps_folder_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _wiki_with_a_committed_gap(tmp)
            wf.git(root, "rm", "-q", "-r", "wiki/gaps")
            self.assertIn("GAP_APPEND", _codes(gap_lint.run(root / "wiki")))


class StandaloneControl(unittest.TestCase):
    def test_the_same_deletion_is_caught_standalone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = wf.build_standalone_wiki(Path(tmp) / "consumer")
            assert gap.main(ADD, root=root, now=NOW) == 0
            wf.git(root, "add", "gaps")
            wf.git(root, "commit", "-q", "--no-verify", "-m", "gap(gap-2026-10-05-001): record")
            wf.git(root, "rm", "-q", "-r", "gaps")
            self.assertIn("GAP_APPEND", _codes(gap_lint.run(root)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_in_host_gap_lint -q
```

Expected: both `InHostLedger` tests fail (no `GAP_APPEND`); the standalone control passes. Exit 1.

- [ ] **Step 3: Prefix the four revision paths** — in `scripts/gap_lint.py`:

```python
    result, error = _run_git(root, ["git", "cat-file", "-e", "HEAD:./{}".format(path)],
                             "git cat-file")
```
```python
    result, error = _run_git(root, ["git", "show", "HEAD:./{}".format(path)],
                             "git show")
```
```python
    result, error = _run_git(root, ["git", "cat-file", "-e", ":0:./{}".format(path)],
                             "git cat-file")
```
```python
    result, error = _run_git(root, ["git", "cat-file", "blob", ":0:./{}".format(path)],
                             "git cat-file")
```

and one sentence in `_git_bytes`'s docstring: "`HEAD:<path>` resolves from the repository's top
level, not the working directory; the `./` prefix resolves it from `cwd=root`, the wiki root,
so the same call reads the ledger whether the wiki is the repository or a folder of it."

- [ ] **Step 4: Run the tests**

```bash
python3 -m unittest tests.test_in_host_gap_lint tests.test_gap_lint -q
```

Expected: `OK`.

#### Verify

- **Goal:** H5 — the gap ledger's `GAP_APPEND` check fires in-host on the input that fires it on
  a standalone wiki (spec §1.4).
- **Red:** `python3 -m unittest tests.test_in_host_gap_lint -q` → `FAILED (failures=2)`.
- **Green:** `python3 -m unittest tests.test_in_host_gap_lint tests.test_gap_lint -q` → `OK`, exit 0.
- **Stub check:** leaving any one of the four lookups unprefixed keeps one of the two in-host
  tests red (the working-tree comparison needs `HEAD:./`, the deletion needs the `never_adopted`
  guard to see committed bytes).

#### Done

```bash
python3 -m unittest tests.test_in_host_gap_lint -q
```

- [ ] **Step 5: Commit**

```bash
git add scripts/gap_lint.py tests/test_in_host_gap_lint.py docs/plans/wiki-in-host-repo.plan.md
git commit -m "fix(gaps): resolve the ledger's committed and staged bytes from the wiki root" -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 7/26'
```

---

### Task 8: `check_commit_msg.py` finds the wiki from its own location (K2, G4)

**Files**
- Modify: `scripts/check_commit_msg.py` (`main`, module docstring)
- Create: `tests/test_commit_msg_root.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_commit_msg_root.py`:

```python
"""check_commit_msg.py gives the same verdict from any working directory (K2, G4)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _wiki(tmp):
    wiki = Path(tmp) / "repo" / "wiki"
    shutil.copytree(ROOT / "scripts", wiki / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    schema = json.loads((ROOT / "templates" / "card-schema.default.json").read_text(encoding="utf-8"))
    schema["keys"]["id"]["pattern"] = r"^doc-\d{3}$"
    (wiki / "sources" / "cards").mkdir(parents=True)
    (wiki / "sources" / "cards" / "card-schema.json").write_text(json.dumps(schema), encoding="utf-8")
    msg = Path(tmp) / "msg.txt"
    msg.write_text("ingest(doc-001): file a doc\n", encoding="utf-8")
    elsewhere = Path(tmp) / "elsewhere"
    elsewhere.mkdir()
    return wiki, msg, elsewhere


def _run(script, msg, cwd, *extra):
    return subprocess.run([sys.executable, str(script), *extra, str(msg)], cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


class RootFromOwnLocation(unittest.TestCase):
    def test_relative_script_paths_from_three_places(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki, msg, elsewhere = _wiki(tmp)
            for cwd in (wiki.parent, wiki, elsewhere):
                script = os.path.relpath(wiki / "scripts" / "check_commit_msg.py", cwd)
                result = _run(script, msg, cwd)
                self.assertEqual(result.returncode, 0, f"{cwd}: {result.stderr}")

    def test_absolute_script_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki, msg, elsewhere = _wiki(tmp)
            self.assertEqual(_run(wiki / "scripts" / "check_commit_msg.py", msg, elsewhere).returncode, 0)

    def test_an_explicit_root_still_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            wiki, msg, elsewhere = _wiki(tmp)
            result = _run(wiki / "scripts" / "check_commit_msg.py", msg, elsewhere, "--root", str(elsewhere))
            self.assertEqual(result.returncode, 1)


class FailsClosed(unittest.TestCase):
    def test_root_without_a_value_is_a_usage_error_not_a_traceback(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_commit_msg.py"), "--root"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and watch them fail**

```bash
python3 -m unittest tests.test_commit_msg_root -q
```

Expected: `FAILED (failures=3)` — the repo-root and elsewhere runs exit 1, the absolute run exits
1, and `--root` with no value prints an `IndexError` traceback.

- [ ] **Step 3: Rewrite the argument handling of `main`** (everything from `schema_file = …` down
  stays as it is; add `import argparse`):

```python
def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="check_commit_msg.py",
        description="Validate a commit message against the wiki's commit convention.")
    parser.add_argument("msg_file", help="the message file git hands the commit-msg hook")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent,
        help="wiki root (default: the wiki this script sits in)")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root
    msg_file = args.msg_file
    schema_file = root / SCHEMA_PATH
```

Module docstring: "the card schema's id.pattern (sources/cards/card-schema.json under --root,
default: the wiki this script sits in)" and the same for the gap schema. `parse_args` is an
impure-adjacent edge; list it beside `main`.

- [ ] **Step 4: Run the tests**

```bash
python3 -m unittest tests.test_commit_msg_root tests.test_commit_msg -q
python3 tools/e2e_in_host.py --only G4
```

Expected: `OK`; the ratchet prints `PASS G4.4 …` (now 4/4 on the hand-built shape).

#### Verify

- **Goal:** G4 ("every shipped script gives the same result from any working directory") and K2.
- **Red:** `python3 -m unittest tests.test_commit_msg_root -q` → `FAILED (failures=3)`.
- **Green:** `python3 -m unittest tests.test_commit_msg_root tests.test_commit_msg -q` → `OK`, exit 0; `python3 tools/e2e_in_host.py --only G4` → `TOTAL 4/4`, exit 0.
- **Stub check:** keeping `Path.cwd()` fails both relative-path tests from the repo root and
  elsewhere; a hand-rolled `--root` parser fails the usage test.

#### Done

```bash
python3 -m unittest tests.test_commit_msg_root -q
```

- [ ] **Step 5: Commit**

```bash
git add scripts/check_commit_msg.py tests/test_commit_msg_root.py docs/plans/wiki-in-host-repo.plan.md
git commit -m "fix(commit-msg): find the wiki from the script's own location" -m $'Tribe-Card: wiki-in-host-repo\nTribe-Task: 8/26'
```

---
