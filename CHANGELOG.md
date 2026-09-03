# Changelog

All notable changes to `wiki-harness` are documented here. This file follows
the compatibility policy in `docs/compatibility-policy.md`, in particular
§8 (CHANGELOG requirement): every entry below states which of **PATCH**,
**MINOR**, or **MAJOR** the release is, and includes an explicit
**Compatibility** field describing what a consumer running `upgrade` into
that release needs to know before doing so.

## Entry template (for all future entries)

```
## [X.Y.Z] — YYYY-MM-DD

**Release type:** PATCH | MINOR | MAJOR

### Changed
- ...

### Compatibility
Describe, in prose, what a consumer running `upgrade` into this release
needs to know before doing so: any new or changed finding code (`lint.py`),
any MANAGED/TEMPLATE path added or — MAJOR only — removed, and any
manifest-schema or CLI (`init.py`/`upgrade.py`) change. An entry that omits
the release type or the Compatibility field is non-conformant with
`docs/compatibility-policy.md` §8.
```

## [1.1.0] — 2026-09-04

**Release type:** MINOR

Closes `HARDENING-BACKLOG.md` §A (A1–A9) — nine defects both extraction
campaigns found and deliberately left, because the extraction's premise was
byte-identical behaviour with `ogp-wiki`. That migration completed on
2026-09-03, so the freeze is over.

### Fixed
- **A1 — the RAW check read the wrong tree.** `git_changes()` ran
  `git diff HEAD` (worktree vs HEAD) where the commit that lands is the
  INDEX. Wrong in both directions: a staged tamper of a `sources/raw/` file
  whose worktree copy was then restored passed the check entirely, and an
  unstaged edit to a raw file blocked an otherwise unrelated commit. Now
  `git diff --cached`. This is the fix with a security shape — the RAW check
  exists to stop source tampering, and the staged path is the one that
  commits.
- **A2 — citations prefix-matched.** The scan pattern was the schema's
  `id.pattern` with its anchors stripped, i.e. a substring search, so
  `src-2026-08-06-001` matched inside `src-2026-08-06-0011` and any page
  mentioning the longer id silently counted as citing the shorter one. The
  body is now wrapped in zero-width id-character lookarounds. (`\b` cannot
  express this: a card id ends in a digit and the next character is also a
  digit, so no word boundary exists there.)
- **A3 — `list: true` keys skipped every value rule.** `_check_value()`
  returned `[]` for any list, so `enum`, `pattern`, `path`, `card_ref` and
  `matches_filename` declared on a list-valued key were never enforced. Each
  item is now checked as the scalar it is.
- **A4 — protocol-relative links were treated as repo paths.** `resolve()`
  read `//host/path` as a repo-relative path and produced a nonsense target;
  it is now reported as external.
- **A6 — rules files were matched by basename anywhere in the tree.** A
  genuine page such as `wiki/recipes.md` was silently skipped by every page
  check. A rules file now only counts as one at a container root it can
  actually govern, per filename.
- **A7 — the card-lint CLI read the schema without the fail-closed guard**
  the library path uses, so a malformed `card-schema.json` raised a
  traceback out of the hook instead of a finding.
- **A8 — `^` inside a character class was read as an anchor**, so the valid
  pattern `^src-[^/]+$` was rejected by the id.pattern contract check.
- **A9 — `--root` was parsed by hand** via `argv.index()`, so `lint.py
  --root` with no value raised `IndexError` — a traceback out of a git hook
  rather than a usage message. Now `argparse`.

### Changed
- **A5 — every `subprocess.run` in `scripts/` now passes `timeout=`**
  (`SUBPROCESS_TIMEOUT = 30`). An unbounded git call inside a pre-commit
  hook is an unbounded hang, which to the user is indistinguishable from a
  broken hook.

### Compatibility
**No new finding code, no MANAGED/TEMPLATE path added or removed, no
manifest-schema change, no flag removed or repurposed, no existing message
string changed.** `lint.py` gains a proper `--help`/usage surface via
argparse; `--root` keeps its meaning and default.

This is MINOR rather than PATCH because three fixes can make a check fire on
content that previously passed **silently** — exactly what §2's MINOR row
permits and its PATCH row forbids:

- A2 may surface `UNFILED`/`CITE` findings on a card whose only "citation"
  was a prefix match inside a longer id;
- A3 may surface `CARD_VALUE`/`CARD_REF` findings on list-valued keys whose
  rules were never enforced before;
- A6 may surface page findings on a page whose basename collides with a
  rules file (`wiki/recipes.md`).

**Measured against the real `ogp-wiki` tree before release: no change at
all.** `lint.py` 0 errors / 0 warnings before and after; every card's
`card_frontmatter_lint.py` output byte-identical; every line of the
commit-message corpus keeping its verdict. A1 changes *which* tree is
inspected, so a wiki that relied on the old worktree behaviour — staging a
raw-file change and expecting it to pass — will now correctly be blocked.

## [1.0.2] — 2026-09-03

**Release type:** PATCH

### Fixed
- `init.py`'s step-16 scaffold summary named a hardcoded release instead of
  the running one. `BYPASS_WARNING` was a module constant embedding the
  literal `wiki-harness v1.0.0`, so every wiki scaffolded from a later
  release was told it came from v1.0.0 — inside the one message that warns
  that commits authored through the GitHub API or a cloud coding agent
  structurally bypass every local hook. A wiki initialised from v1.0.1 was
  therefore given a false statement about which release shipped no
  mitigation for that class of commit. The constant is now the template
  `BYPASS_WARNING_TEMPLATE`, `bypass_warning(version)` interpolates it, and
  `summary_text()` takes `version` the way `commit_subject(version)`
  already did. `read_version()` remains the sole impure edge supplying it,
  so the value always comes from the library's own `VERSION` file.

### Compatibility
No finding code added or changed, no MANAGED/TEMPLATE path added or
removed, no manifest-schema change, no flag or exit code changed.

One message string does change, which deserves stating plainly against
`docs/compatibility-policy.md` §2's PATCH row ("no existing message string
changes"): the summary's final line now reads `wiki-harness v<running
version>` where it previously read `wiki-harness v1.0.0` regardless of the
running version. This is judged a defect fix rather than a contract break,
because the constant never expressed a contract — it expressed a bug. The
line's *documented* meaning has always been "name the release that ships no
mitigation"; before this fix it named the wrong one from v1.0.1 onward. A
consumer script grepping the literal `v1.0.0` in this line was matching the
defect, not an interface. Consumers who parse the summary should match
`wiki-harness v` and read the version that follows.

## [1.0.1] — 2026-09-02

**Release type:** PATCH

### Fixed
- `init.py`'s `dry_run_hooks` (step 13) exec'd both git hooks with a
  target-relative program path while also passing `cwd=target`. When
  `target` was a relative path (the most natural invocation shape, e.g.
  `cd /tmp && python3 init.py my-wiki ...`), the child process resolved the
  program path relative to its own `cwd` — which was that same relative
  target — doubling the target name and crashing with an unhandled
  `FileNotFoundError`. Both hook program paths are now resolved to
  absolute before being exec'd; `cwd=target` is unchanged. A target passed
  as an absolute path was never affected and remains byte-identical.

### Compatibility
This is a defect fix only: no finding code added, no managed/template path
added or removed, no manifest-schema change, and no documented CLI flag,
exit code, or message string changed — a crash is not a documented exit
code, so making a previously-crashing invocation succeed does not breach
the "CLI surface fixed" row (`docs/compatibility-policy.md` §2). A
consumer running `upgrade` into this release needs to take no action.

## [1.0.0] — 2026-09-02

**Release type:** MAJOR (initial release)

### Added
- The initial public release of `wiki-harness`: `init.py` (first adoption
  into a consumer wiki) and `upgrade.py` (pulling a newer release into an
  already-adopted wiki), the vendored `scripts/lint.py`,
  `scripts/card_frontmatter_lint.py`, `scripts/check_commit_msg.py`, and
  `scripts/manifest.py`, plus the `githooks/` hook scripts (commit-message and pre-commit) and the
  wiki `templates/`.

### Compatibility
This is the first release of `wiki-harness`, so there is no prior version
of the library for a consumer to `upgrade` from — the notes below state the
baseline contract now in force, against which every future release's
Compatibility field will be measured (`docs/compatibility-policy.md` §2).

- **Finding codes.** The harness lint emits these codes (severities
  `ERROR`/`WARN`): `LINK`, `ORPHAN`, `CITE`, `UNFILED`, `FM`, `INDEX`,
  `RAW`, `ENCODING`, `HOOKS`, `HARNESS`, `CARD_SCHEMA`, `CARD_FM`,
  `CARD_KEY`, `CARD_REF`, `CARD_VALUE`. They are defined as
  `Finding(severity, code, path, msg)` in `scripts/lint.py` and
  `scripts/card_frontmatter_lint.py`, which together are the authoritative
  source of this set.
- **MANAGED/TEMPLATE paths.** As shipped, `init`/`--adopt` record the
  vendored `scripts/*.py` (including `scripts/manifest.py`) and the
  `.githooks/*` hook scripts as `managed`, plus
  `sources/AGENTS.md`, `wiki/AGENTS.md`, `sources/cards/AGENTS.md`,
  `CLAUDE.md`, `sources/CLAUDE.md`, `sources/cards/CLAUDE.md`, and
  `wiki/CLAUDE.md` (each `@AGENTS.md`, MANAGED per standing rule 6) as
  `managed`, and `AGENTS.md` and `README.md` as `template` — the exact set
  `.wiki-harness-manifest.json` records after `init` runs.
- **CLI surface.** `init.py` and `upgrade.py` ship with the flags and exit
  codes described in `docs/compatibility-policy.md` (downgrade refusal,
  the removed-managed-path abort, and `--check`'s manifest precondition).
- **No independent/CI verification ships in v1.0.0.** See
  `docs/compatibility-policy.md` §9: there is no CI workflow, no
  `ci_verify.py`, no `--ci` flag, and no independent, external-copy
  verification anywhere in this release. The only integrity check is
  `lint.py`'s `HARNESS` finding, a self-consistency check against the
  wiki's own recorded manifest hashes.
