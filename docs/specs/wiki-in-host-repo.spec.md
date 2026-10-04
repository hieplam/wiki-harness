# Spec — wiki-in-host-repo: a wiki is a folder of its repo, with the agent at the repo root

| Field | Value |
| --- | --- |
| Card | `~/.tribe/-Users-home-repos-wiki-harness/cards/wiki-in-host-repo.md` (the contract — this spec never overrides it) |
| Source issue | hieplam/wiki-harness#46 |
| Base | `main` @ 203c4aa (v1.4.1) |
| Target release | 2.0.0 (MAJOR), one release, compatibility-policy §3 one-time exception (card D7) |
| Way of work | `tribe` (card "Way of work") |
| Plan | `docs/plans/wiki-in-host-repo.plan.md` |
| Planning experiments | E1–E4, recorded with commands and literal output in `~/.tribe/-Users-home-repos-wiki-harness/reports/wiki-in-host-repo-plan.md`; scripts in `~/.tribe/-Users-home-repos-wiki-harness/wiki-in-host-repo/experiments/` |

Terms (repo root, wiki folder, in-host layout, standalone layout, bridge, footprint) are the
card's, quoted in §2.1. Paths in this spec are relative to this library's checkout unless they
name a consumer path, which is written `<repo root>/…` or `wiki/…`.

---

## 1. The problem, grounded

The harness assumes the wiki root is the repository root. Every fact below was re-measured during
planning on `main` @ 203c4aa; the card's own "Today" list is confirmed, and E2 found one defect
the card did not list (1.4).

1.1 **`init` always nests a repo and writes the repo's identity.** `init.py:398-403`
(`git_init`) runs `git init` whenever `<target>/.git` is missing and writes `user.name` /
`user.email`; `init.py:563-568` writes `core.hooksPath .githooks`. A user who runs it inside an
existing repo gets a nested repo (a gitlink on `git add .`).

1.2 **Raw immutability is silently off in-host (Blocker).** `lint.py:490-492` runs
`git -C <wiki> diff --cached --name-status`; git prints top-level-relative paths
(E2 P4: `M	wiki/sources/raw/probe.txt`) while `lint.py:335-339` matches the prefix
`sources/raw/`. With `--relative` git prints `M	sources/raw/probe.txt` (E2 P4).

1.3 **The hooks cannot run in-host, and lint's HOOKS check can be satisfied while no hook runs.**
`githooks/pre-commit` and `githooks/commit-msg` call `$(git rev-parse --show-toplevel)/scripts/…`
— in-host that is `<repo root>/scripts/lint.py` and every wiki commit fails (E2 P5, P6:
`can't open file '…/bare/scripts/lint.py'`). `lint.py:498-513` (`hooks_finding`) compares only
the config string: `core.hooksPath .githooks` with no `.githooks/` folder lints clean (E2 P8:
`lint: 0 error(s), 1 warning(s)`), and its remedy text (`git config core.hooksPath .githooks`)
would disable a husky setup if followed.

1.4 **NEW (E2 P7): the gap ledger's append-only check is partly silent in-host.**
`scripts/gap_lint.py:207,260` ask git for `HEAD:gaps/knowledge-gaps.jsonl` and
`scripts/gap_lint.py:278,342` for `:0:gaps/knowledge-gaps.jsonl` with `cwd=<wiki>`. Git resolves
`HEAD:<path>` and `:0:<path>` from the top level, not the working directory, so in-host every
committed-bytes and staged-bytes read returns "never committed". Measured: from `cwd=wiki`,
`git cat-file -e HEAD:gaps/knowledge-gaps.jsonl` → `fatal: path … does not exist in 'HEAD'`
(rc 128), `HEAD:./gaps/knowledge-gaps.jsonl` → rc 0. A staged deletion of the whole `wiki/gaps/`
folder gives no `GAP_*` finding in-host and `ERROR GAP_APPEND` ×3 + `ERROR GAP_SCHEMA` on a
standalone wiki (E2 P7b). Only the `--numstat` mechanism (a cwd-relative pathspec) still works.
This is an H5 breach and is fixed by this card.

1.5 **`check_commit_msg.py` depends on the working directory.** `check_commit_msg.py:60` defaults
`--root` to `Path.cwd()`; from the repo root it silently falls back to the default card-id
pattern (E2 P3: `ingest(doc-001): …` with a `^doc-\d{3}$` schema → rc 1 from the root and from
an unrelated directory, rc 0 from `wiki/`). It also parses `--root` by hand
(`args[i + 1]`), so `--root` with no value is an `IndexError` traceback (fail-closed rule 1).

1.6 **`upgrade` is whole-repo.** `upgrade.py:813` (`git_status_porcelain`) checks the whole repo,
so any unrelated dirty or staged file blocks an in-host upgrade (E1: rc 2, `Dirty paths:` lists
`src/app.py`, `src/staged.py`). When the repo is clean the upgrade works (E1b), but
`git_add_all` (`upgrade.py:1160`) stages the whole repo (E1b demonstrated it staging
`src/app.py`, `src/extra.py`, `src/staged.py` from inside `wiki/`), `git_reset_index`
(`upgrade.py:1136`) resets the whole index, and `git_commit` commits the whole index. Its
dirty-tree remedy (`git checkout -- .`, `upgrade.py:223-226`) run from a repo root discards every
uncommitted change in the repo.

1.7 **The manual speaks to a session standing in the wrong place.**
`templates/AGENTS.root.md.tmpl:88,109,128` and `templates/gaps.AGENTS.md:18-24` write every
command as `python3 scripts/…` and never name their path base. E3 shows the consequence: a
headless session at a repo root answered correctly but cited `./wiki/gizmo-fastening.md` and
`./sources/cards/…` — wiki-relative paths that are wrong from where it stands.

1.8 **Default names come from the folder name.** `init.py:141-154` derives `repo_name` from the
target's basename and `org_name` from `wiki_title`; `init wiki --wiki-title wiki` yields a README
"The knowledge source of truth for wiki" (#46 gap 5).

1.9 **No bridge.** granado-espada hand-wrote `.claude/skills/ask-wiki/SKILL.md`,
`.claude/skills/ingest-wiki/SKILL.md`, a root `CLAUDE.md` with path rules, and root
`.githooks/{pre-commit,commit-msg}` that re-implement raw immutability and the
wiki-only commit-msg gate (read in `/Users/home/repos/granado-espada`). Cabal wrote another
`ask-wiki`.

What does work in-host today (E2): `lint.py`, `card_frontmatter_lint.py` and `gap.py` give the
same result from any working directory; `gap.py` commits are path-scoped and leave an unrelated
staged file staged (E2 Q6).

## 2. Contract

### 2.1 Governing text (quoted from the card, not paraphrased)

- Terms: "**Repo root** — the git top level of the repo that holds the wiki"; "**Wiki folder** —
  `<repo root>/wiki/`, holding every wiki folder"; "**Bridge** — the new files the harness writes
  outside the wiki folder so a session at the repo root knows the wiki exists and how to query,
  ingest and record gaps from there (D5): Claude skills, one agent-neutral instructions file, and
  hook side files (D4)"; "**Footprint** — the paths a harness command may write in a repo: the
  wiki folder plus the bridge files recorded in the manifest."
- D4: "when the repo has no hooks path, `init` wires the harness hooks. When the repo already has
  a hook, `init` leaves it untouched and writes the harness version beside it as a separate file
  whose name carries `wiki-harness` (pattern of `x.bak.y`); the repo owner merges it by hand;
  `upgrade` updates only that side file. Lint reports HOOKS until the wiki's checks really run
  (G3)."
- D5: "`init` writes only NEW files outside the wiki folder (Claude skills, one agent-neutral
  instructions file, D4 side files), records them with hashes in a new optional manifest section
  (an additive data shape), and `upgrade` maintains them. It never edits an existing repo file:
  for an existing root `CLAUDE.md` / `AGENTS.md` it prints the one link line to add, and lint
  warns until that line exists."
- D6: "only a new `init` produces the in-host layout; every 1.x wiki keeps its structure; lint,
  hooks, scripts and `upgrade` keep supporting the standalone layout; `upgrade` never moves a
  wiki."
- D8: "the layout is exactly as drawn — repo root: agent instructions and skills; `wiki/`: every
  wiki folder; the pages folder stays `wiki/wiki/` (no rename)."
- K2 "Every shipped script resolves the wiki root from its own location"; K3 "The wiki's commit
  rules (lint, commit convention) apply only to commits that touch the wiki folder"; K6 "`init`
  and `upgrade` stage and commit only their footprint, on the repo's current branch"; K8 "The wiki
  folder is always `<git top level>/wiki/`. … A target inside a work tree that is not its top
  level is refused with a message naming the top level. A root that already has a `wiki/` path is
  refused"; K9 "A root `AGENTS.md` / `CLAUDE.md` that does not exist yet is a new file under D5, so
  `init` creates it with the link"; K11 "A bridge path that already exists as a repo-owned file is
  never overwritten; the harness version is written beside it with the D4 naming pattern".
- Guardrails H1–H6 apply verbatim (card "Guardrails").
- Oracle (dispatch brief): "under-checking (a raw-file change or a wiki-touching commit that slips
  through) is a bug; over-checking (refusing a commit that touches the wiki folder in an ambiguous
  way) is by design. … touching anything outside the footprint (H1–H4) is a bug, whatever the
  convenience."

### 2.2 Goals

The goal table is the card's G1–G11, unchanged. §7 maps every goal row to the ratchet checks
that prove it, and the plan's closing table maps every goal to its tasks.

## 3. Layout model

One pure function decides which shape a wiki is in, from two resolved absolute paths:

| `classify_layout(wiki_root, top_level)` | Condition | Who produces it |
| --- | --- | --- |
| `None` | `top_level is None` (not inside a work tree: upgrade's scratch copy, bare fixtures) | — |
| `"standalone"` | `wiki_root == top_level` | every 1.x `init`; also a nested-repo wiki (git says it is its own repo) |
| `"in-host"` | `wiki_root.parent == top_level` and `wiki_root.name == "wiki"` | every 2.0 `init`; granado-espada by hand |
| `"subfolder"` | anything else inside a work tree (e.g. `<root>/docs/kb`) | hand-made 1.x setups only |

The wiki folder's contents are identical in every layout: the same wiki-root-relative paths
(`index.md`, `scripts/*.py`, `.githooks/*`, `AGENTS.md`, `README.md`, `CLAUDE.md`, …). The
manifest's existing `files` map keeps wiki-root-relative keys in every layout. Only the bridge
is new, and only `"in-host"` gets one.

Rules every component follows:

- Correctness checks never branch on layout when a layout-neutral git form exists:
  `--relative`, `HEAD:./<path>`, `:0:./<path>` and cwd-relative pathspecs give the same answer
  in every layout (E2 Q4–Q7, and the 2026-10-05 probe: a raw file renamed out of `wiki/`
  shows as `D	sources/raw/a.txt` with `--relative`).
- Behaviour that differs by layout (the HOOKS proof, the BRIDGE check, footprint scoping,
  message wording) branches on `classify_layout` only, and the `"standalone"` branch is the 1.x
  behaviour with byte-identical messages (G9).
- `"subfolder"` gets the in-host correctness fixes (footprint scoping, layout-neutral checks,
  token-based HOOKS proof built from its own relative path) and no bridge (§5.9).

## 4. Pure core and edges (module map)

`~/.claude/rules/pure-core.md` and AGENTS.md hard rule 2 govern: every decision below is a pure
function over gathered data; every git call, file read/write, environment read and clock read is
in a named edge below the `# ---- impure edges ----` marker, listed in the module docstring.

| Module | Status | Pure core (new or changed) | Impure edges (new or changed) |
| --- | --- | --- | --- |
| `scripts/repo_layout.py` | NEW, vendored (MANAGED) | `classify_layout`, `side_path`, `plan_hooks`, `proof_tokens`, `unproven_hooks`, `hooks_message`, constants `WIKI_FOLDER`, `SIDE_MARKER`, `HOOK_NAMES`, `BRIDGE_LINK_TOKEN`, `BRIDGE_LINK_LINE`, `GATE_ENV` | none (pure module) |
| `scripts/commit_gate.py` | NEW, vendored (MANAGED) | `wiki_is_touched` | `git_facts`, `run_check`, `main` |
| `githooks/pre-commit`, `githooks/commit-msg` | changed (S0) | — | one `exec` line each, resolving `commit_gate.py` from `$0` |
| `scripts/lint.py` | changed (S0) | `check_hooks`, `check_bridge`, `check_harness` (checkout prefix) | `git_changes` (`--relative`), `hooks_facts`, `bridge_facts`, `read_harness_manifest` (bridge entries), `main` (reads `GATE_ENV`) |
| `scripts/gap_lint.py` | changed | — | `_path_in_head`, `_git_bytes`, `_path_staged`, `_staged_bytes` use `./`-prefixed revision paths |
| `scripts/check_commit_msg.py` | changed (S0) | `validate` unchanged | `main`: argparse, root from own location |
| `scripts/manifest.py` | changed | `compute_manifest(…, bridge=None)` | — |
| `init.py` | changed | `TargetFacts`, `init_refusal`, `default_names` (in `apply_defaults`), `plan_bridge`, `footprint_paths`, `lint_acceptable`, `summary_text` | `gather_target_facts`, `scaffold_wiki`, `render_bridge`, `write_bridge`, `ignored_paths`, `gather_hooks_facts`, `apply_hooks_plan`, `commit_footprint`, `main` |
| `upgrade.py` | changed | `format_drift_abort` / `format_dirty_tree` (checkout prefix), `bridge_drifts`, `merge_bridge_entries` | `detect_layout`, footprint-scoped `git_status_porcelain` / `git_add_all` / `git_commit` / rollback edges, `upgrade_bridge`, `run_upgrade`, `run_adopt` |
| `templates/bridge/*` | NEW | — | — |
| `tools/e2e_in_host.py` | NEW, repo-internal (never vendored) | check registry, result formatting, version bump | scenario builders, release builder, `main` |

`scripts/` gains two MANAGED files. `copy_scripts()` discovers `scripts/*.py` by glob
(`init.py:414-425`), `provided_source_paths()` mirrors it (`upgrade.py:933-936`), and
`tools/build_release.py`'s `PAYLOAD_PATHS` ships whole trees, so no list needs editing; the
payload test (`tests/test_build_release.py:119`) already asserts every `scripts/*.py` and every
template ships. `templates/bridge/` ships the same way.

## 5. Design

### 5.1 The commit gate (G2, K3, H5)

`githooks/pre-commit` becomes:

```sh
#!/bin/sh
# Runs the wiki's checks when this commit touches the wiki folder (scripts/commit_gate.py).
exec python3 "$(dirname "$0")/../scripts/commit_gate.py" pre-commit
```

and `githooks/commit-msg`:

```sh
#!/bin/sh
# Checks the commit message when this commit touches the wiki folder (scripts/commit_gate.py).
exec python3 "$(dirname "$0")/../scripts/commit_gate.py" commit-msg "$1"
```

`$0` is the path git (or a delegating hook) used; with `core.hooksPath wiki/.githooks` git runs
`wiki/.githooks/pre-commit` from the top level (E2 gate log: `$0=wiki/.githooks/pre-commit`
`cwd=<root>`), and a side-file delegator passes an absolute path (E2 husky gate log). Both
resolve.

`scripts/commit_gate.py` decides with one pure function:

```python
def wiki_is_touched(is_standalone, staged_wiki_paths, index_matches_head, head_wiki_paths):
    """Pure. True when the commit being made touches the wiki folder."""
    if is_standalone:
        return True        # the wiki IS the repository: every commit touches it (1.x behaviour)
    if staged_wiki_paths:
        return True
    # A reword (`git commit --amend` with nothing newly staged) replaces HEAD with the same
    # tree; when HEAD touched the wiki folder, the replacement does too (NEEDS_DIRECTION N1,
    # recommended option B).
    return index_matches_head and bool(head_wiki_paths)
```

Its edge gathers, from `git -C <wiki root>`: `rev-parse --show-toplevel` (standalone iff equal
to the wiki root, both resolved); `diff --cached --name-only --no-renames --relative`
(staged paths under the wiki folder); `diff --cached --quiet` (whole index vs HEAD — without a
pathspec it covers the whole repo even from a subdirectory, measured); and
`diff-tree --no-commit-id --name-only -r --root --relative HEAD` (HEAD's paths under the wiki
folder; an unborn HEAD reads as "no HEAD paths, index differs"). Every call is bounded
(`timeout=`), isolated from host git config only where a verdict could turn on it (the gate
reads repository state, not config, so it inherits `GIT_INDEX_FILE` and the environment git gave
the hook — E2 shows relative and absolute `GIT_INDEX_FILE` values both work). A git failure is
read as "touched" (fail closed: the checks run).

When touched, the gate runs `scripts/lint.py` (pre-commit) with `WIKI_HARNESS_GATE=pre-commit`
in its environment, or `scripts/check_commit_msg.py <msg file>` (commit-msg), as
`[sys.executable, <script>]` subprocesses with `timeout=600`, and exits with their code; a timeout
prints one line and exits 1. When not touched it exits 0 without output.

Consequences, each a ratchet check (§7): a host-only commit with a free-form subject passes and
runs no lint (K3); a commit touching `wiki/` and anything else is judged by the wiki's rules
(over-check by design); a standalone wiki's hooks behave exactly as in 1.x, including
`git commit --allow-empty` running lint (E4); `gap.py`'s path-scoped commits are judged (they
touch the wiki).

### 5.2 Wiring the hooks: D4

`plan_hooks` (pure, `scripts/repo_layout.py`) takes facts `init` (and `upgrade`'s first bridge
install, §5.8) gather with host config isolated:

| Facts | Plan | What is written |
| --- | --- | --- |
| no `core.hooksPath` in the repo's own config, and `$GIT_DIR/hooks` holds no `pre-commit` / `commit-msg` file | `wire` | `git config core.hooksPath wiki/.githooks` — `init` only (§5.7); `upgrade` never writes git config and prints this command instead |
| `core.hooksPath` set, resolving to a directory inside the work tree (not inside `.git`) | `side-files` | `<hooks dir>/pre-commit.wiki-harness` and `<hooks dir>/commit-msg.wiki-harness` (MANAGED bridge entries), never the hooks themselves; the directory is created if absent |
| anything else: real hooks in `$GIT_DIR/hooks`, or a `core.hooksPath` outside the work tree | `print-only` | nothing; the summary prints the two lines to add to the existing hooks (NEEDS_DIRECTION N2, recommended option A) |

The side file is a one-line delegator, MANAGED (verbatim from `templates/bridge/`):

```sh
#!/bin/sh
# wiki-harness: the wiki's pre-commit check. This repository already had its own pre-commit hook,
# so wiki-harness did not replace it. Add the last line of this file to that hook. Keep this file:
# `upgrade` keeps it current, and `lint` reports HOOKS until the line runs on every commit.
"$(git rev-parse --show-toplevel)/wiki/.githooks/pre-commit" || exit 1
```

(`commit-msg.wiki-harness` is the same with `commit-msg` and `"$1"`.) The logic lives in the
MANAGED `wiki/.githooks/*` and `commit_gate.py`, which `upgrade` keeps current; the line the
owner merges rarely changes, which is why D4's "update only that side file" stays cheap.

A global `core.hooksPath` is invisible to `init` (config isolation); setting the repo's local
value shadows it for that repo. Recorded as a known limitation in the README, not handled.

### 5.3 The HOOKS proof: G3

`lint.py`'s `hooks_finding` splits into an edge `hooks_facts(root)` and a pure `check_hooks`.

- Inside the gate (`WIKI_HARNESS_GATE=pre-commit`, read by `main`), HOOKS is not checked: the
  pre-commit gate is running, which proves it is wired. Without this, a correct side-file merge
  blocks every wiki commit with HOOKS (E2 husky prototype: `lint: 2 error(s)` after the merge).
  Setting the variable by hand silences only this one check; documented in the module docstring.
- `"standalone"`: the 1.x rule, byte-identical message — `core.hooksPath` must read exactly
  `.githooks` (`ERROR HOOKS .githooks: commit hook not active - run: git config core.hooksPath
  .githooks`) — plus the G3 fix: `.githooks/pre-commit` and `.githooks/commit-msg` must exist
  and be executable, else `ERROR HOOKS .githooks: core.hooksPath is .githooks but .githooks/<name>
  is missing or not executable - run: git checkout -- .githooks`. A real 1.x consumer has both
  (E4), so its findings are unchanged (G9).
- `"in-host"` / `"subfolder"`: the effective hooks directory is `git rev-parse --git-path hooks`
  (honours `core.hooksPath`; cwd-relative, resolved against the `-C` directory). A hook name is
  proven when either (a) the effective directory resolves to `<wiki root>/.githooks` and that
  hook file is executable, or (b) the effective hook file is executable and one of its lines
  that is not a `#` comment contains a proof token for that hook: `<rel>/.githooks/<name>`,
  `<rel>/scripts/commit_gate.py`, and `<rel>/scripts/lint.py` (pre-commit) or
  `<rel>/scripts/check_commit_msg.py` (commit-msg), where `<rel>` is the wiki folder relative to
  the top level (`wiki` in-host). Husky ≥ 9 keeps its stubs in `.husky/_/`; when the effective
  directory's name is `_`, the same-named file in its parent counts too. granado-espada's hooks
  (`python3 "$root/wiki/scripts/lint.py"`, `…/check_commit_msg.py`) are proven by (b) — G11.
  Any unproven hook gives one finding:
  `ERROR HOOKS .githooks: the wiki's <names> check(s) do not run on commits - run: git config core.hooksPath <rel>/.githooks, or add the line in <hooks dir>/<name>.wiki-harness to <hooks dir>/<name>`.
- Not a work tree: no finding (unchanged).

Hook managers that keep the call in a config file (pre-commit framework, lefthook) cannot be
proven by (a) or (b): their commits work (the in-gate exemption), but a manual lint run stays red.
NEEDS_DIRECTION N3 asks whether that is acceptable.

`lint.py` keeps reading `core.hooksPath` without isolating host config: the question is what git
will actually run, and the host config is part of that answer. Tests isolate it themselves.

### 5.4 Other lint and script changes

- RAW (`git_changes`): add `--relative`. `parse_name_status` is unchanged; a rename out of the
  wiki folder arrives as `D` (measured) and is refused.
- Gap ledger (`gap_lint.py`): `HEAD:./{}` and `:0:./{}` in all four revision lookups. The `./`
  form resolves against `cwd=<wiki root>`, the same in every layout (E2 Q7, Q7b).
- HARNESS messages (`check_harness`): a pure `checkout_prefix` argument (`""` standalone, `wiki/`
  in-host) makes the remedy `git checkout -- wiki/<path>` in-host, so the command is safe to run
  from the repo root, where the agent stands; the standalone message stays byte-identical.
- BRIDGE (new code, WARN only, emitted only when the manifest carries a `bridge` section and the
  layout is `"in-host"`): (1) each of `<repo root>/AGENTS.md` and `<repo root>/CLAUDE.md` that
  exists and does not contain `@WIKI.md` → `WARN BRIDGE ../<file>: add this line so agents find
  the wiki: <BRIDGE_LINK_LINE>`; neither exists → one `WARN BRIDGE ../AGENTS.md: no root AGENTS.md
  or CLAUDE.md links WIKI.md; create one with: <BRIDGE_LINK_LINE>`; (2) each recorded bridge
  entry whose bytes differ → `WARN BRIDGE ../<path>: edited since wiki-harness wrote it; upgrade
  refuses until you restore it or run 'upgrade --adopt-drift <path>'`, missing → `WARN BRIDGE
  ../<path>: missing; upgrade refuses until you restore it`. Paths are shown relative to the wiki
  root (`../`) like every other finding path. WARN, not ERROR: the bridge is not one of the
  wiki's invariants, and an edit there must not block a wiki commit; `upgrade` is where consent is
  enforced (G7).
- `check_commit_msg.py`: argparse (`msg_file` positional, `--root` optional `Path`), root default
  `Path(__file__).resolve().parent.parent` (K2, G4); a missing `--root` value exits 2 with
  argparse's usage line instead of an `IndexError`.
- `card_frontmatter_lint.py` and `gap.py`: unchanged (already cwd-independent, E2 P2, Q6).

### 5.5 Manifest: the `bridge` section (D5)

`compute_manifest(hashes, vars, source_url, harness_version, source_ref, source_commit, *,
initialised_at, bridge=None)`. When `bridge` is a dict it is validated exactly like `hashes`
(roles from `VALID_ROLES`) and written as a last key `"bridge"`, sorted by path; when `None` the
manifest is byte-for-byte what 1.4.1 writes (standalone and subfolder wikis never get the key).

```json
"bridge": {
  ".claude/skills/ask-wiki/SKILL.md": {"role": "template", "sha256": "…"},
  ".claude/skills/ingest-wiki/SKILL.md": {"role": "template", "sha256": "…"},
  ".husky/commit-msg.wiki-harness": {"role": "managed", "sha256": "…"},
  ".husky/pre-commit.wiki-harness": {"role": "managed", "sha256": "…"},
  "WIKI.md": {"role": "template", "sha256": "…"}
}
```

Keys are POSIX paths relative to the repo root. `lint.py`'s `_manifest_shape_error` validates
`bridge` with the same rules as `files` (object entries, known string role, relative, no `..`)
when the key is present; `hash_tree(repo_root, …)` already refuses a symlink that resolves
outside its root (`scripts/manifest.py:141-149`), which is the containment proof for reads (H4).
Root `AGENTS.md` / `CLAUDE.md` created by K9 are SEEDED (§5.6) and never recorded. This is the
whole data-shape change: one optional key, additive (compatibility-policy §2 MINOR row), nothing
else in the manifest changes.

### 5.6 The bridge (D5, K9, K10, K11)

Logical bridge files, their canonical paths, roles and sources:

| Logical file | Canonical path (repo-root-relative) | Role | Source | When |
| --- | --- | --- | --- | --- |
| instructions | `WIKI.md` | template | `templates/bridge/WIKI.md.tmpl` | always (in-host) |
| ask skill | `.claude/skills/ask-wiki/SKILL.md` | template | `templates/bridge/ask-wiki.SKILL.md.tmpl` | always |
| ingest skill | `.claude/skills/ingest-wiki/SKILL.md` | template | `templates/bridge/ingest-wiki.SKILL.md.tmpl` | always |
| pre-commit side file | `<hooks dir>/pre-commit.wiki-harness` | managed | `templates/bridge/pre-commit.wiki-harness` | hooks plan `side-files` |
| commit-msg side file | `<hooks dir>/commit-msg.wiki-harness` | managed | `templates/bridge/commit-msg.wiki-harness` | hooks plan `side-files` |
| root link (SEEDED) | `AGENTS.md`, `CLAUDE.md` | seeded, not recorded | `templates/bridge/root-link.md.tmpl` | `init` only, each only when absent (K9) |

Skill names `ask-wiki` / `ingest-wiki` match granado-espada's, which is what makes G11's fixture
collide by construction. `WIKI.md` is the "one agent-neutral instructions file": a plain file
Copilot, Codex and Claude can all read, linked from the root files by the link line.

`BRIDGE_LINK_LINE` (one line, works in both root files: Claude Code expands `@WIKI.md` as an
import anywhere in a line; other agents read it as "read WIKI.md"):

```text
Wiki: before you answer a question about this project's domain or change anything under `wiki/`, read @WIKI.md.
```

`plan_bridge(recorded, present, hooks_plan)` (pure) returns one `BridgeWrite(logical, path, role,
source)` per logical file:

1. a logical file already recorded in the manifest stays at its recorded path (sticky — a side
   path never moves back);
2. else its canonical path when nothing exists there;
3. else `side_path(canonical)` (K11: `SKILL.md` → `SKILL.wiki-harness.md`, `WIKI.md` →
   `WIKI.wiki-harness.md`) when nothing exists there;
4. else a refusal naming both paths (never clobber, H3).

`side_path` inserts `.wiki-harness` before the last suffix, or appends it when there is none
(`pre-commit` → `pre-commit.wiki-harness`). A side `SKILL.wiki-harness.md` is inert to Claude
Code (only `SKILL.md` loads), which is the point: the owner's skill keeps working.

Template rendering uses `string.Template` with the four existing variables only (no new manifest
`vars` key, D5). Bridge templates contain no other `$`; the side-file hooks are copied verbatim,
never rendered (they contain shell `$`). K10: the skills' `description` names `${wiki_title}` and
`${org_name}`; with no flags both default to the repo name (§5.7, G8). E3 proved a headless
session at the root discovers `.claude/skills/<name>/SKILL.md` and invokes it; G6 is the oracle
for trigger quality with the real templates.

Writes (edge `write_bridge`): every path is `PurePosixPath`, relative, without `..`, and its
resolved parent is proven inside the resolved repo root before the write (H4,
fail-closed rule 4); a path under `.git/` is refused. Before anything is written, `ignored_paths`
runs `git check-ignore --no-index -- <paths>`; an ignored bridge path refuses the whole command
with the matching rule (`git check-ignore -v` output) — a bridge that does not travel with the
clone breaks G6 for every other clone, and force-adding past the owner's ignore rules would
override repo policy. The refusal says to add a negation such as `!.claude/skills/` and re-run.

The `WIKI.md` and skill texts are written out in full in the plan (Task 13). Their content
requirements, each traceable to #46 or granado-espada's bridge:

- path base: the wiki's manuals write paths relative to `wiki/`; from the root, prefix `wiki/`;
  the pages folder is `wiki/wiki/`; a table of the four common mappings (granado workaround 5);
- run scripts by path from the root (`python3 wiki/scripts/gap.py …`); never `cd wiki`
  (granado workaround 4, #46 comment 1);
- language precedence: everything written into `wiki/` is in `${content_language}`; answer the
  user in their language; `--prompt` stays verbatim (#46 gap 6);
- commits: wiki-touching commits follow the wiki convention; others are free; stage and commit
  only `wiki/` paths for wiki operations (`git commit -- wiki`); `gap.py` commits only its two
  files;
- K4: branch and merge policy are the repository's own rules; if it forbids committing to its
  default branch, switch branches before recording a gap or ingesting (granado workaround 6
  becomes a rule the bridge names, not a hand-made workaround);
- citations from the root: cite `wiki/wiki/<page>.md` and `wiki/sources/cards/<id>.md`, with the
  card's `trust` (E3's wiki-relative citations are the failure this prevents);
- setup after clone: run `python3 wiki/scripts/lint.py`; on `HOOKS`, do what the message says.

### 5.7 `init` 2.0 (G1, G3, G8, K5, K6, K8, K9, H1–H4)

CLI: `init.py <target> [--wiki-title] [--org-name] [--content-language] [--repo-name]
[--origins] [--answers-file] [--non-interactive] [--force]` — the same flags. `<target>` is the
repository root. `--wiki-title` stops being required (G8, compatibility-policy §2.1's "required
may become derived").

Refusals (all decided by the pure `init_refusal(facts)` before any write; exit 2; facts gathered
by `gather_target_facts` with host config isolated). In order:

1. target exists and is not a directory → the 1.x message (`REFUSAL_MESSAGE`), unchanged;
2. target (or its nearest existing ancestor) is inside a work tree whose top level is not the
   target → `init takes the repository root as its target: <target> is inside the git work tree
   at <top level>; run: init <top level>` (K8; this is also what a 1.x habit `init wiki` from a
   repo root gets);
3. target is a bare repository → `<target> is a bare git repository; init needs a work tree`;
4. `<target>/wiki` exists in any form, including a broken symlink → `<target>/wiki already exists;
   init never writes into an existing wiki/ path` (K8);
5. target is a non-empty directory that is not a git top level and `--force` was not given →
   the 1.x message, unchanged (`--force` keeps its meaning: scaffold into a non-empty directory —
   now by making it a repository);
6. a merge, rebase, cherry-pick or revert is in progress (`MERGE_HEAD`, `rebase-merge/`,
   `rebase-apply/`, `CHERRY_PICK_HEAD`, `REVERT_HEAD` under the git dir) → `a <operation> is in
   progress in <top level>; finish or abort it, then re-run init` (a path-scoped commit is
   refused mid-merge);
7. after the names are collected and the bridge planned: an ignored bridge path (§5.6) or a
   bridge refusal from `plan_bridge`.

Flow:

1. resolve target (`.`, relative, trailing slash and absolute all resolve first — the v1.0.0
   relative-path crash is the precedent); refuse per above;
2. collect names: `repo_name` defaults to the repo root's basename, `wiki_title` to `repo_name`,
   `org_name` to `wiki_title`, `content_language` to `English` (K5, G8); interactive prompts offer
   these defaults; `missing_required_vars` returns `[]` for every input (no variable is required);
3. `git init -q` only when the target is not already a top level (new/empty directory, or
   `--force`); never writes `user.name` / `user.email` (H2);
4. `scaffold_wiki(library_root, <root>/wiki, values, origins)` — steps 4–10 of 1.x unchanged,
   against the wiki folder (refactored out of `main`, Task 9);
5. hooks: gather facts, `plan_hooks`; `wire` sets `core.hooksPath wiki/.githooks` and reads it
   back; `side-files` adds the two side files to the bridge plan;
6. bridge: render, plan, write; root `AGENTS.md` / `CLAUDE.md` created from
   `root-link.md.tmpl` only when absent; record every non-seeded bridge write in the manifest's
   `bridge` section (rewrite the manifest written in step 4 with the section added);
7. lint the wiki folder; accept exit 0, or — only when the hooks plan is not `wire` — an output
   whose every `ERROR` line is an `ERROR HOOKS` line (`lint_acceptable`, pure);
8. dry-run both wiki hooks directly (1.x step 13; the gate sets `WIKI_HARNESS_GATE`, so HOOKS is
   not checked inside it), after staging the footprint with `git add -- <footprint>`;
9. commit the footprint only: `git add -- <paths>` then `git commit -m <subject> -- <paths>`,
   on the current branch (K6), authored by the placeholder identity passed through
   `GIT_AUTHOR_NAME/EMAIL` and `GIT_COMMITTER_NAME/EMAIL` in the commit's environment only —
   never config (H2). Whatever hooks the repo has run (the wiki gate when wired, the owner's own
   hooks otherwise); a rejection leaves the scaffold on disk, uncommitted, exit 1 (1.x
   behaviour). Unrelated staged changes stay staged and uncommitted (measured: a path-scoped root
   commit keeps another staged file staged);
10. verify: HEAD's subject equals the subject, and every path HEAD changed is inside the
    footprint (`git diff-tree --no-commit-id --name-only -r --root HEAD`);
11. summary (pure `summary_text`): the scaffold line, the hooks line (wired / the two merge lines
    for `side-files` and `print-only`), one link line instruction per existing root file that
    did not get the link, and the 1.x bypass warning.

The footprint for steps 8–10 is `wiki/` plus every bridge path written in step 6, including the
seeded root files `init` created.

### 5.8 `upgrade` 2.0 (G5, G7, G9, G11, H1, H3)

`detect_layout(target)` (edge) resolves the top level with host config isolated and calls
`classify_layout`.

- `"standalone"`: every git call and message is exactly 1.x's (G9). No bridge.
- `"in-host"` / `"subfolder"`: every git operation is scoped to the footprint, run from the top
  level with explicit pathspecs:
  - clean precondition: `git status --porcelain -- <footprint>`; unrelated dirty, staged and
    untracked paths no longer block (G5); the message lists only footprint paths and its remedy
    becomes `git checkout -- <wiki folder>` (never `.`);
  - `--commit`: `git add -A -- <footprint>`, `git commit -m <subject> -- <footprint>`;
  - rollback on a rejected commit: `git reset -q -- <footprint>`, `git checkout -- <tracked
    footprint paths>`, `git clean -fd -- <footprint>` (untracked paths there can only be this
    run's writes: the footprint was proven clean first);
  - promote rollback (`git_checkout_dot`): scoped to the wiki folder, as today (it already runs
    `-C <wiki>` with pathspec `.`, which is cwd-relative), plus the bridge paths written so far.
- Drift (G7): the step-1 drift check also covers recorded `bridge` entries with role managed or
  template; a drifted or missing one blocks unless `--adopt-drift <repo-relative path>` names it
  (the existing consent flag; manifest `files` keys and `bridge` keys never collide — every
  bridge path is either `WIKI.md`, under `.claude/`, or ends in `.wiki-harness`, none of which a
  wiki-relative MANAGED/TEMPLATE path is, asserted by a test). An adopted bridge entry flips to
  `instance-fork` with its old hash and is never rewritten again (same semantics as `files`).
  Drift lines print the checkout command relative to the top level
  (`git checkout -- wiki/AGENTS.md`, `git checkout -- .claude/skills/ask-wiki/SKILL.md`) and the
  `--adopt-drift` argument as recorded.
- Bridge maintenance (`"in-host"` only): render the TARGET release's bridge through its own
  init module (the single source of truth for layout mapping, as `overwrite_scratch` already
  does), `plan_bridge(recorded, present, hooks_plan)`, write changed or new entries after the
  wiki promote succeeds, record them in the new manifest's `bridge` section. A recorded side file
  is updated in place; the owner's own hook and any repo-owned file are never written (H3).
  `upgrade` never writes git config: on a first bridge install (no `bridge` section yet — every
  1.x in-host wiki, G11) the hooks plan is computed; `side-files` writes side files; `wire`
  prints the `git config core.hooksPath wiki/.githooks` command; `print-only` prints the lines.
  Root `AGENTS.md` / `CLAUDE.md` are never created by `upgrade` (SEEDED paths are `init`-only, as
  for every seeded path today); the link line is printed for each existing root file lacking it.
- `"subfolder"`: footprint-scoped git, no bridge, one printed note that the bridge is only
  installed for a wiki at `<top level>/wiki/`.
- Dry run (`--report`): the pending list includes bridge paths, repo-relative.
- `--check`: unchanged.

### 5.9 `upgrade --adopt` in a host repo

`run_adopt` today calls `set_hooks_path(target)` unconditionally (`upgrade.py:1353-1356`), which
in-host would write `core.hooksPath .githooks` into the host's config — an H2 breach. In 2.0 it
calls the same hooks plan as `init` (`wire` writes `core.hooksPath wiki/.githooks`), and for an
`"in-host"` layout installs the bridge exactly like `upgrade`'s first install. Standalone adopt is
unchanged.

### 5.10 The wiki's own manual (templates)

- `templates/AGENTS.root.md.tmpl` (TEMPLATE): a "Where you stand" paragraph right after the
  first one: every path and command in this wiki's manuals is relative to the folder holding this
  file; if the session runs elsewhere (for example at the root of a repository that keeps this
  wiki in `wiki/`, which `WIKI.md` there explains), prefix every path with that folder; scripts
  find the wiki from their own location, so run them by path from anywhere. The first sentence
  stops saying "This repository (`$repo_name`) is …" and says "This wiki, in repository
  `$repo_name`, is …". The `.githooks/` layout row and the README's "Setup after clone" line stop
  naming `git config core.hooksPath .githooks` and say "run `python3 scripts/lint.py`; if it
  reports HOOKS, follow its message" — correct in both layouts because lint's message is
  layout-specific (§5.3).
- `templates/README.md.tmpl` (TEMPLATE): the same setup line; title and org default from the
  repo (G8).
- `templates/gaps.AGENTS.md` (MANAGED): one sentence above the command block: commands are
  relative to the wiki folder; from elsewhere run them by path.

Every standalone wiki receives these texts on its next `upgrade` (TEMPLATE re-render, MANAGED
overwrite) — a content change, not a structure change (G9), named in the release's
`BREAKING CHANGE:` footer per AGENTS.md "Changing a template".

### 5.11 Docs and release (G10, D7)

- `docs/compatibility-policy.md`: new §3.1 "One-time exception: 2.0.0", stating D7's reason —
  "`init` changes what an existing invocation produces, and no installed wiki loses anything (D6),
  so a deprecation release would protect nobody" — and that it is not a precedent. §2's manifest
  row gains a sentence naming the optional `bridge` key; §4 names the new `BRIDGE` code.
- `README.md` (G10): the quickstart becomes `wiki-harness init my-project` (a repo root) and
  shows the in-host tree; a section "Where the wiki lives" with the layout drawing (D8), what
  happens to 1.x standalone wikis (they keep working and keep their structure; `upgrade` never
  moves them, D6), and why a nested repo and a submodule are not supported (a nested repo has no
  remote and is skipped by host-wide search and clone, #46 gap 4; a submodule needs a separate
  remote and splits the journal); the identity paragraph says `init` authors its one commit as
  `wiki-harness init` through environment variables and never writes your git config.
- The release commit: the PR is squash-merged (this repo refuses merge commits:
  `allow_merge_commit: false`, `squash_merge_commit_message: PR_BODY`), title
  `feat(init)!: init scaffolds the wiki as a folder of its repository, with a bridge for the agent at the root`,
  and the squash body is given explicitly with `gh pr merge --squash --subject … --body-file …`
  so its last paragraph is the `BREAKING CHANGE:` footer (the PR description itself still ends
  with the attribution line). Footer text is in the plan (Task 23).

### 5.12 C3

The facts `c3-210` (init) and `c3-211` (upgrade) quote the CLI surface; `c3-101` (lint),
`c3-110` (hooks), `c3-201` (manifest) and the template facts describe behaviour this card
changes. The model cannot be validated or changed with the installed tooling (c3x 11.0.0 and
9.9.1 both report broken seals and `repair` / `migrate` / `import --force` refuse before
resealing — report "C3 probe"). NEEDS_DIRECTION N4; the plan's governance task (Task 24) is
written for the recommended option.

## 6. Scope fence

From the card, unchanged: no rename of the pages folder or any existing MANAGED/TEMPLATE path;
no move, conversion or migration of any 1.x wiki; nested repo and submodule documented as
unsupported, not supported; branch and merge policy not enforced; Python 3.9 stdlib only; no
change to granado-espada or Cabal.

Also out, by this spec: no `--host`/`--no-git`/layout flag on `init` (there is one layout); no
upgrade path that converts standalone to in-host; no support for hook managers' config files in
the HOOKS proof (N3); no change to `bin/wiki-harness` or `install.sh` (they pass arguments
through; `wiki-harness init <target>` still reads correctly).

## 7. Testing strategy and the ratchet

### 7.1 The ratchet tool

`tools/e2e_in_host.py` (repo-internal, Python 3.9 stdlib, never vendored) is the card's "ONE
committed end-to-end scenario". It builds real repos in a temp directory, runs the harness exactly
as a user types it (subprocesses, `cwd` set, relative and absolute targets), and prints one line
per check — `PASS <id> <text>` or `FAIL <id> <text> — <reason>` — then `TOTAL <passed>/<total>`;
exit 0 only when every selected check passes. `--only <prefix>` selects checks by id prefix
(`--only G2`, `--only G5.2`). `--library <path>` names the checkout under test (default: this
checkout). Releases for G5/G7/G9/G11 are built by the tool itself: R1 = the library under test
with `VERSION` set to `2.0.0`, R2 = R1 plus a one-line change to every bridge template and to
`templates/wiki.AGENTS.md` with `VERSION` `2.0.1`, both built with `tools/build_release.py` from
throwaway git repos whose `origin` is a local bare repo carrying the tags (so `upgrade --check`
works offline); V1 = v1.4.1 built from this repository's `v1.4.1` tag with `origin` set to
`https://github.com/hieplam/wiki-harness`, verified against the published sha256
`3519f9e00eb0aa2c7c3cf2eef2e9095f2bf66d307eb3df981a21b33830a0ef99` (E4: byte-identical). Host
git config is isolated (`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` = devnull) and the tool's own
commits carry identity through environment variables. A check that cannot run because its setup
failed reports `FAIL … — setup: <error>`; the tool never crashes on a red baseline.

Checks (ids are stable; the plan's tasks name them):

| Goal | Checks |
| --- | --- |
| G1 | for each of {codebase, empty} × {relative, absolute} (`cd <parent> && init <name>`, `init <abs>`, and `cd <root> && init .` for the codebase): G1.1 exit 0; G1.2 `<root>/wiki/index.md` exists, `<root>/wiki/.git` does not; G1.3 no mode-160000 entry in `git ls-files -s`; G1.4 every non-footprint path byte-identical in worktree and index (the codebase has an unrelated dirty file and an unrelated staged file); G1.5 `git config --local --list` differs only by `core.hookspath=wiki/.githooks`; G1.6 the init commit changes only footprint paths; G1.7 one init through the built R1 payload (no `.git` in the library) |
| G2 | in-host, wired: G2.1 staged edit of an existing raw file refused with `ERROR RAW sources/raw/`; G2.2 staged delete refused; G2.3 rename of a raw file out of `wiki/` refused; G2.4 wiki-touching commit with a free-form subject refused; G2.5 same with `lint: …` subject accepted; G2.6 host-only commit with a free-form subject accepted and no lint output; G2.7 standalone control (raw edit refused); G2.8 a reword amend of a wiki commit to a free-form subject refused (N1) |
| G3 | G3.1 in-host with `core.hooksPath` unset: lint exit 1 with `ERROR HOOKS`; G3.2 wired: lint exit 0; G3.3 `core.hooksPath` naming a missing folder: `ERROR HOOKS`; G3.4 husky codebase: `.husky/pre-commit` byte-identical, both side files present, `ERROR HOOKS`; G3.5 husky after merging the side-file lines: lint exit 0 and a raw edit commit refused |
| G4 | each of `lint.py`, `card_frontmatter_lint.py <card>`, `gap.py list`, `check_commit_msg.py <msg>` run from the root, `wiki/` and an unrelated directory with a relative script path: identical stdout, stderr and exit code (G4.1–G4.4) |
| G5 | in-host from R1 with an unrelated dirty file and an unrelated staged file: G5.1 `upgrade --check` names v2.0.1; G5.2 `upgrade wiki --to v2.0.1 --apply --commit --library-path <R2>` exit 0; G5.3 non-footprint worktree and index byte-identical; G5.4 the upgrade commit changes only footprint paths and the unrelated staged file is still staged; G5.5 `wiki/wiki/AGENTS.md` carries R2's change and the manifest says 2.0.1 |
| G6 | mechanical, one per granado workaround the harness owns: G6.W1 = G2.1; G6.W2 = G3.2; G6.W3 = G2.6; G6.W4 = G4; G6.W5 `WIKI.md` and both skills exist, are committed, and `WIKI.md` maps `wiki/wiki/`; G6.W6 `WIKI.md` names branch policy as the repository's rule. The headless agent run (`--agent`, opt-in) is §7.3 |
| G7 | from R1 to R2, in-host: G7.1 an untouched `ask-wiki` skill gets R2's text; G7.2 an owner-edited skill blocks the upgrade (exit 1, file untouched); G7.3 with `--adopt-drift .claude/skills/ask-wiki/SKILL.md` it proceeds and the owner's bytes survive; G7.4 husky: `.husky/pre-commit.wiki-harness` gets R2's text, `.husky/pre-commit` byte-identical |
| G8 | `init` with no name flags at `acme-widgets/`: G8.1 `wiki/README.md` and `wiki/AGENTS.md` name `acme-widgets`, neither contains `source of truth for wiki` |
| G9 | V1 standalone (published payload shape) upgraded to R1: G9.1 lint output identical on unchanged content; G9.2 every V1 tracked path still exists at the same place, no `WIKI.md`, no `.claude/`, wiki root still the top level; G9.3 hooks behave the same (raw edit refused, free-form subject refused, `--allow-empty` runs lint); G9.4 manifest has no `bridge` key |
| G11 | granado-shaped fixture (V1 init into `<root>/wiki`, `.git` removed, root `.githooks/` with granado's two hooks, `core.hooksPath .githooks`, hand-written `.claude/skills/ask-wiki/SKILL.md`, root `CLAUDE.md`) upgraded to R1: G11.1 exit 0; G11.2 the hand-written skill byte-identical and `SKILL.wiki-harness.md` beside it; G11.3 `.claude/skills/ingest-wiki/SKILL.md` and `WIKI.md` created; G11.4 `.githooks/pre-commit` byte-identical and `.githooks/pre-commit.wiki-harness` present; G11.5 the manifest's `bridge` lists them; G11.6 root `CLAUDE.md` byte-identical, the link line printed, lint WARNs `BRIDGE`; G11.7 lint has no `ERROR HOOKS` (granado's hooks call `wiki/scripts/lint.py`) |

Baseline: the plan's Tasks 1–3 build the tool; Task 3 commits its full output on the unchanged
library as `docs/evidence/in-host-e2e-baseline.txt` before any build task. Every build task's
Green names the check ids it turns from FAIL to PASS. Task 25 commits
`docs/evidence/in-host-e2e-after.txt`; the done claim is `TOTAL n/n` there against the baseline
total, and no check may go PASS → FAIL between them.

### 7.2 Unit and integration tests

TDD per task, `python3 -m unittest`, every git call in tests isolated from host config and every
`subprocess.run` with `timeout=`. Rules from AGENTS.md "Testing" and
`fixtures-mirror-reality.md`: every new entry point is exercised with a relative and an absolute
target; lifecycle code is exercised against an empty directory and against a repo that already
has code and hooks.

Fixtures. Once `init` produces only the in-host layout, every existing test that needs a
standalone wiki builds it through `tests/fixtures/standalone_wiki.py:build_standalone_wiki`
(Task 9), which reproduces a 1.x consumer's shape — wiki root = repo root, `core.hooksPath
.githooks`, the library's own `scaffold_wiki` output, one commit — instead of calling
`init.py`. Those tests' assertions stay unchanged (G9 Verify: "the existing suite's
lint/upgrade/hook assertions stay unchanged"). `tests/test_init.py` asserts `init`'s own
contract, which this MAJOR release changes; its tests are rewritten to the in-host contract with
the same intents, and the plan lists every changed assertion and its reason (brief-contracts
rule 2: fence by intent).

The full suite took 2h00m wall-clock / 590 s CPU on the planning machine (exit 0). Task Done
commands therefore run targeted modules; the whole suite runs once in the background before the
PR, and in CI.

### 7.3 The G6 oracle: a headless agent session

`tools/e2e_agent_session.py` (Task 22) builds a fresh scenario repo (code + `init` from the
library under test + seeded wiki content with a fabricated fact, as in E3), then runs three
`claude -p` sessions at the root with `< /dev/null`, `--setting-sources project`,
`--strict-mcp-config`, `--no-session-persistence`, `--output-format stream-json --verbose`,
`--model sonnet`, `--max-budget-usd 1.50` each, and an allowlist
(`Read,Grep,Glob,Skill,Write,Edit,Bash(python3 wiki/scripts/:*),Bash(git add:*),Bash(git commit:*),Bash(git status:*),Bash(git log:*),Bash(git switch:*)`):
(1) a question the wiki answers — PASS when the transcript shows the `ask-wiki` skill invoked
and the answer contains the fact and the root-relative citation `wiki/wiki/<page>.md`;
(2) a question it cannot answer — PASS when exactly one new commit `gap(gap-…)` touching only
`wiki/gaps/knowledge-gaps.jsonl` and `wiki/gaps/KNOWLEDGE_GAP.md` exists;
(3) "ingest this source" with a source file — PASS when an `ingest(<card-id>)` commit exists,
touches only `wiki/`, and `python3 wiki/scripts/lint.py` exits 0. It writes the three transcripts
and a verdict file to a directory it prints. It is evidence, run once at delivery (it costs money
and is not deterministic); its transcripts go into the PR evidence.

## 8. Evidence plan

- Before/after: `docs/evidence/in-host-e2e-baseline.txt` (Task 3) and
  `docs/evidence/in-host-e2e-after.txt` (Task 25), both produced by `tools/e2e_in_host.py` on the
  same machine; the PR body embeds the per-goal counts before → after and links both files at
  the PR head commit (same-origin `raw` links, verified to resolve).
- G6: the three transcripts and the verdict file from `tools/e2e_agent_session.py`, committed
  under `docs/evidence/g6-agent-session/` and linked.
- G9: the E2E's G9 lines (V1 baseline lint output vs. after) inline in the PR body.
- G10: the README diff; the owner reads it next to #46.
- After merge: a comment on #46 with the before → after numbers (card "Ledger").

## 9. Risks and rollback

| Risk | Mitigation |
| --- | --- |
| A host's own hooks reject `init`'s scaffold commit | `init` exits 1 with the scaffold on disk, uncommitted, inside the footprint only (1.x failure shape); the summary says how to commit by hand |
| The HOOKS proof misses a valid wiring shape (false red) | over-check by design (G3); in-gate exemption keeps commits working; N3 |
| The amend rule over-checks `--allow-empty` right after a wiki commit | accepted over-check (Oracle) |
| `upgrade` loads the target release's `init` module while `repo_layout` / `manifest` are already imported from the running release (Python's module cache) | pre-existing pattern for `manifest`; both modules keep backward-compatible signatures; noted in `upgrade.py`'s docstring |
| Host `.gitignore` ignores `.claude/` | refused before any write, with the rule and the negation to add (§5.6) |
| Squash merge loses the `BREAKING CHANGE:` footer | `feat(init)!` title alone forces MAJOR; the squash body is passed explicitly and checked after merge (Task 23) |

Rollback: the release is one squash commit; reverting it on `main` restores 1.4.1 behaviour for
new `init`s. Wikis initialised by 2.0 keep working with 2.0 scripts (vendored); a 1.x `upgrade`
cannot downgrade them without `--allow-downgrade` (compatibility-policy §5).

## 10. How-level decisions taken here (the Shaman may veto any)

1. One pure layout classifier; correctness checks use layout-neutral git forms; only messages,
   HOOKS proof, BRIDGE and footprint scoping branch on layout (§3).
2. A wiki in a subfolder other than `<top>/wiki` gets footprint-scoped upgrades and no bridge
   (§5.8) — nothing about such a 1.x wiki's structure or files changes beyond what `upgrade`
   already does.
3. Root `AGENTS.md` / `CLAUDE.md` created by K9 are SEEDED: written once by `init`, never hashed,
   never touched again; `upgrade` never creates them (§5.6, §5.8).
4. Bridge drift is a lint WARN; `upgrade` is where consent is enforced (§5.4).
5. Bridge paths are sticky: once recorded at a side path, a logical file stays there (§5.6).
6. `upgrade` never writes git config, in-host included; `adopt` follows `init`'s hooks plan (§5.8,
   §5.9).
7. `init` authors its commit with the placeholder identity through environment variables only
   (§5.7); the README's identity paragraph is updated.
8. An ignored bridge path refuses `init`/`upgrade` before any write (§5.6).
9. `--wiki-title` becomes optional; `wiki_title` and `org_name` default to the repo name (G8).
10. The PR merges by squash with an explicit squash body (§5.11); the tribe block's
    `gh pr merge --merge` is refused by this repository.

## 11. Open questions (NEEDS_DIRECTION, one per item; full text in the planner's report)

- **N1** — the commit gate cannot see a reword (`git commit --amend` with nothing staged). The
  plan builds the recommended option B (§5.1); option A drops `index_matches_head` and accepts the
  hole; the residual hole under B (an amend that adds only non-wiki changes to a wiki commit and
  rewrites its message) is documented in `docs/known-limitations.md`.
- **N2** — D4 when the repo's hooks live outside the work tree (`$GIT_DIR/hooks` with real hooks,
  or an absolute `core.hooksPath`): the plan builds option A, `print-only`.
- **N3** — hook managers lint cannot read (pre-commit framework, lefthook): the plan builds the
  recommended option (ERROR stays; commits work through the in-gate exemption; documented).
- **N4** — the C3 model cannot be restored with the installed c3x: the plan's Task 24 is written
  for the recommended option (land the 2.0 fact deltas as a pending record in
  `docs/known-limitations.md` and a follow-up card; no `.c3/` edits in this card).

## 12. Experiments this spec rests on

E1 (in-host upgrade baseline), E2 (empty-fixture and husky-fixture run of the planned layout,
with a prototype of §5.1–§5.4), E3 (headless skill discovery: positive), E4 (published v1.4.1
standalone baseline, offline byte-identical rebuild) and the C3 probe — commands and literal
output in the planner's report.
