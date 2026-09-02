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

## [1.0.0] — 2026-09-02

**Release type:** MAJOR (initial release)

### Added
- The initial public release of `wiki-harness`: `init.py` (first adoption
  into a consumer wiki) and `upgrade.py` (pulling a newer release into an
  already-adopted wiki), the vendored `scripts/lint.py`,
  `scripts/card_frontmatter_lint.py`, `scripts/check_commit_msg.py`, and
  `scripts/manifest.py`, plus the `.githooks/` commit-message hook and the
  wiki `templates/`.

### Compatibility
This is the first release of `wiki-harness`, so there is no prior version
of the library for a consumer to `upgrade` from — the notes below state the
baseline contract now in force, against which every future release's
Compatibility field will be measured (`docs/compatibility-policy.md` §2).

- **Finding codes.** `lint.py` emits the following codes today: `LINK`,
  `ORPHAN`, `CARD_SCHEMA`, `CITE`, `UNFILED`, `FM`, `INDEX`, `RAW`,
  `ENCODING`, `HOOKS`, and `HARNESS` (severities `ERROR`/`WARN`; see
  `Finding(severity, code, path, msg)` in `scripts/lint.py`).
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
