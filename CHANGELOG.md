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
