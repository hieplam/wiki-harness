# wiki-harness — Working Manual

This file is the entry point for any agent working **on this library**. Read it before you
touch anything. (`CLAUDE.md` is a one-line pointer to this file; Claude Code, Codex, Copilot
and anything else all get the same instructions from here.)

Do not confuse the two audiences:

- **This repo** is the *library* — the harness's own source, tests, and governance.
- **A wiki instance** is what `init.py` produces. Its agent instructions are the
  `templates/AGENTS.root.md.tmpl` and the nested `templates/*.AGENTS.md` files, rendered into
  the consumer's repo. Editing those changes *every* wiki on the next upgrade.

## What this library is

A versioned lint/hook/rules harness for LLM-maintained wikis, extracted from `ogp-wiki`.
Consumers do not `pip install` it: they clone this repo at a release tag and run `init.py`
(first adoption) or `upgrade.py` (pull a newer release) against their own working tree. The
harness copies itself into the consumer and records every file it owns, with hashes, in the
consumer's `.wiki-harness-manifest.json`.

See [README.md](./README.md) for the consumer-facing story (what a wiki looks like, what
cards/origin/trust mean, how to run `init`). Do not duplicate that here — link to it.

## Layout

| Path | What it is |
|---|---|
| `init.py` | First adoption: 16 ordered, fail-closed steps. Runs **once** per wiki, ever. |
| `upgrade.py` | Every subsequent release move, plus `--adopt` for a pre-harness wiki. |
| `scripts/lint.py` | The linter a consumer runs. Emits `Finding(severity, code, path, msg)`. |
| `scripts/card_frontmatter_lint.py` | Card frontmatter validation, driven entirely by the consumer's `card-schema.json`. |
| `scripts/check_commit_msg.py` | Commit-subject validation. |
| `scripts/manifest.py` | Pure `compute_manifest`/`diff_manifest` — the drift oracle. |
| `githooks/` | `pre-commit` + `commit-msg`, copied into a consumer's `.githooks/`. |
| `templates/` | Every MANAGED / TEMPLATE / SEEDED source `init` places into a consumer. |
| `tests/` | The library's own suite. `./run_tests.sh` runs all of it. |
| `docs/` | Compatibility policy, known limitations, the extraction plan and its records. |
| `.c3/` | Architecture facts. Read them through the C3 CLI — **never** open the files. |

## Hard rules

These are enforced, not advisory. A change that breaks one gets rejected.

1. **Python 3.9, standard library only.** Every `.py` module targets 3.9, imports only the
   stdlib, and opens with `from __future__ import annotations` as its first import. A consumer
   wiki has no package-manager step; one third-party import breaks `python3 scripts/lint.py`
   on a bare interpreter. (`rule-stdlib-only-py39`)
2. **Pure core, impure edges.** Every calculation, decision, and flow-control step is a pure
   function over already-collected data. Filesystem writes, subprocess/git calls, the clock,
   and interactive prompts live in named edge functions below the `# ---- impure edges ----`
   marker, and are injected as seams where a test needs to drive them. Each module's docstring
   lists which functions are which — keep that list accurate when you add one.
   (`rule-pure-core-impure-edge`)
3. **Edges fail closed.** Catch the *specific* exception external input can raise
   (`json.JSONDecodeError`, `UnicodeDecodeError`, `OSError`) and convert it into a typed
   refusal with an exit code. Never `except Exception`, and never let a traceback escape into a
   git hook or a CLI — to a user a traceback is a crash, not a verdict. Every
   `subprocess.run` carries `timeout=`, and every `git` call sets `GIT_CONFIG_GLOBAL` and
   `GIT_CONFIG_SYSTEM` to `os.devnull` so a host's config can never change a result.
4. **`scripts/` and `githooks/` are a verbatim port.** They were forked byte-for-byte from
   `ogp-wiki` HEAD `f8b43fb`. Change them only for a defect this library itself introduced.
   A defect inherited from the source repo is recorded as a hardening candidate, never fixed
   freehand. (`ref-verbatim-port`)
5. **Never name OGP.** `scripts/**/*.py`, `githooks/*`, and `templates/**/*` must contain no
   OGP-, Prospa-, or ogp-wiki-content-specific string. `tests/test_genericity.py` enforces it.
   This file and `README.md` may name ogp-wiki as the library's origin — they are not shipped
   into a consumer.
6. **The compatibility policy binds every change.** Before touching a finding code, a
   MANAGED/TEMPLATE path, the manifest schema, or a CLI surface, read
   [docs/compatibility-policy.md](./docs/compatibility-policy.md) §2 and decide the release
   type it forces. That decision goes in the CHANGELOG entry.

## Testing

```bash
./run_tests.sh                              # the whole suite
python3 -m unittest tests.test_init -q      # one module
```

Write the failing test first, watch it fail, then make it pass. Beyond that:

- **A fixture must mirror how a real caller invokes the thing.** An entry point that takes a
  user-supplied path needs a test that types a *relative* one, not only an absolute
  `TemporaryDirectory` path — that exact gap shipped a crash in v1.0.0 past 248 green tests.
  Cover the shapes a person actually types: absolute, relative, trailing slash, `.`.
- **Exercise lifecycle code against an empty tree.** `init`/`upgrade` defects of the "only
  visible on a real or bare target" class do not surface in unit tests of the parts.
- Tests drive `init.py`/`upgrade.py` as real subprocesses against throwaway temp directories,
  never against this checkout. Isolate git in tests exactly as the tool does.

## Changing a template

`templates/` files land in *every* consumer wiki. A TEMPLATE-class file (`AGENTS.root.md.tmpl`,
`README.md.tmpl`) is re-rendered on the consumer's next `upgrade`, so a wording change there
rewrites their file; a MANAGED file is overwritten byte-for-byte. Both are hashed in the
consumer's manifest, so both show as a diff on upgrade. Say so in the CHANGELOG entry.

`${var}` placeholders are filled by `string.Template` from the four template variables
(`wiki_title`, `org_name`, `content_language`, `repo_name`). There is no conditional
rendering — write text that reads correctly for every value, including when `org_name`
defaults to the same string as `wiki_title`.

## Commit convention

`<type>(<scope>): <summary>` — e.g. `fix(upgrade): refuse a missing --to and name dirty paths`.
This repo's own history is the reference. (The `<op>(<ref>): <summary>` convention enforced by
`githooks/commit-msg` governs *consumer wikis*, not this library.)

**Never add an agent as a commit co-author.**

## Cutting a release

1. Land the change with its tests green.
2. Decide PATCH / MINOR / MAJOR against
   [docs/compatibility-policy.md](./docs/compatibility-policy.md) §2 — the table is mechanical;
   apply it to what actually changed.
3. Bump `VERSION`.
4. Add a `CHANGELOG.md` entry using the template at the top of that file. It **must** state
   the release type and carry a **Compatibility** field describing what a consumer running
   `upgrade` into this release needs to know: new or changed finding codes, MANAGED/TEMPLATE
   paths added or removed, manifest-schema changes, CLI changes. An entry missing either is
   non-conformant with §8 of the policy.
5. Open a PR, get CI green, merge, then tag the merge commit `vX.Y.Z` and push the tag.
   Consumers clone by tag — an untagged release does not exist.

## Architecture facts (C3)

Architecture is modeled in `.c3/` and is **frozen**: facts change only through a change-unit
(an ADR plus its patch folder), never by editing a file. Use the `c3` skill; query with
`search`/`lookup`/`read`, and when a code change makes a fact stale, land the fact edit in the
same PR through `change new` → patches → `change accept` → `change apply`.

The facts most likely to go stale: `c3-210` (init) and `c3-211` (upgrade) both carry a
Contract row that quotes the CLI surface verbatim. Change a flag, and that row is now wrong.
