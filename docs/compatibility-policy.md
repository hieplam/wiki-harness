# wiki-harness compatibility policy

## 1. Scope

`wiki-harness` is consumed by clone + vendor: a consumer wiki (for example
`ogp-wiki`) clones this repository at a tagged release and runs `init.py`
(first adoption) or `upgrade.py` (pulling a newer release) against its own
working tree. Because the consumer does not install the harness as a
package, its only contract with the library is:

- the semantics of `lint.py`'s findings (which codes exist, what severity
  they carry, what triggers them),
- the set of paths the harness manages (the MANAGED/TEMPLATE files listed
  in `.wiki-harness-manifest.json`) and the manifest's own schema,
- the CLI surface of `init.py`/`upgrade.py` (flags, exit codes, printed
  messages a script or a human might depend on).

This document states what may change across a PATCH, MINOR, or MAJOR
release of `wiki-harness`, and the specific behavioural policies
(deprecation, downgrade, managed-path removal, migration scope, and the
current state of independent/CI verification) that keep an `upgrade` safe
for a consumer to run without reading the library's source first.

Versions are plain semantic versions, `X.Y.Z` (see the repository's
`VERSION` file). This policy governs the v1.0.0 release line going
forward.

## 2. PATCH / MINOR / MAJOR

| Change | PATCH (`X.Y.Z+1`) | MINOR (`X.Y+1.0`) | MAJOR (`X+1.0.0`) |
|---|---|---|---|
| Findings on unchanged content | Must be byte-identical: the same lint findings (code, severity, path, message) as before, run against an unmodified wiki tree. No finding may appear, disappear, or change severity/message. | May add new finding codes and new checks that fire on content that previously passed silently (a wiki may see new WARN/ERROR output it did not see before). May not change the meaning or wording of an existing code's message for content that already triggered it. | May remove or fundamentally redefine an existing finding code (subject to the deprecate-before-remove convention, §3). |
| MANAGED/TEMPLATE path set | Fixed. No path is added, removed, or reassigned between `managed`/`template`/`instance-fork`/`removed`. | May add new MANAGED/TEMPLATE paths (new files an `upgrade` will start writing). May not remove a path a consumer's manifest already records as `managed`/`template` (that is a removed-managed-path event, §6, and is MAJOR only). | May remove a MANAGED/TEMPLATE path (§6) or reassign an existing path's role, subject to the deprecate-before-remove convention (§3). |
| `.wiki-harness-manifest.json` schema | Fixed: existing keys keep their type and meaning. | Additive only: new optional keys may be introduced; every existing key keeps its shape. `VALID_ROLES` (`scripts/manifest.py`) may gain new enum members but never drops one. | May change or remove an existing manifest key, or change the meaning of an existing `VALID_ROLES` member. |
| CLI surface (`init.py`/`upgrade.py`: flags, exit codes, stdout/stderr message text) | Fixed. A script that greps a message string or checks an exit code today keeps working unchanged. | Additive only: new optional flags, new informational output. No existing flag's meaning, default, or exit code changes; no existing message string changes. | May remove or repurpose a flag, or change an exit code's meaning, subject to §3. |

The intent of this table is the same one the harness enforces on itself for
`ogp-wiki`'s real content today (the extraction's own byte-identical-
behaviour rule): a PATCH must never surprise a consumer who changed
nothing.

## 3. Deprecate-before-remove

No PATCH or MINOR release removes anything a consumer may be relying on —
a finding code, a MANAGED/TEMPLATE path, a manifest key, a CLI flag, or a
message string. Removal is always a MAJOR event, and it is always preceded
by a deprecation period:

1. A MINOR release marks the thing deprecated (documented in that release's
   CHANGELOG entry, §8, and, where mechanically possible, flagged at
   runtime — e.g. a WARN-severity finding, or a printed notice) while
   keeping its old behaviour fully intact.
2. The next MAJOR release is the earliest point the deprecated thing may
   actually be removed or redefined.
3. A removal of a MANAGED/TEMPLATE path specifically also goes through the
   removed-managed-path guard described in §6 — `upgrade` refuses to
   silently drop a path out from under an installed wiki even at a MAJOR
   boundary; it aborts and requires the operator to acknowledge the loss.

There is no "skip the warning" fast path: something is never removed in
the same release that first announces its removal.

## 4. Finding-code namespace: the `X_` prefix reservation

Every finding `lint.py` produces today is a short, uppercase code — for
example `LINK`, `ORPHAN`, `CARD_SCHEMA`, `CITE`, `UNFILED`, `FM`, `INDEX`,
`RAW`, `HARNESS` (severities `ERROR`/`WARN`; see `Finding(severity, code,
path, msg)` in `scripts/lint.py`) — assigned by the harness itself. No
externally-authored or plugin-authored check exists in v1.0.0 (see
"Not-now item 2" in the plan history: a plugin/entry-point system for
custom lint checks was rejected for v1 as a trust-boundary problem).

The prefix `X_` on a finding code is nonetheless reserved now, ahead of any
check that uses it. In v1.0.0 this reservation is purely nominal: **no
code in this repository emits a code beginning with `X_`, and there is no
execution mechanism — plugin loader, config hook, or otherwise — that
could produce one.** The reservation exists solely so that a future MINOR
release can introduce new experimental/provisional checks under the `X_`
namespace without a naming collision with a stable code, and so that a
consumer's own tooling (dashboards, suppress-lists, CI greps) can safely
treat any code starting with `X_` as experimental and subject to change
outside the normal PATCH/MINOR stability guarantees in §2 — again, moot
until such a check actually ships.

## 5. Downgrade policy

`upgrade.py --to <version>` compares the requested target version against
the version recorded in the installed wiki's manifest
(`harness_version`), using `parse_semver()`/`compare_semver()`
(`is_downgrade()` in `upgrade.py`).

- **By default, a downgrade is refused.** If `--to` names a version older
  than the manifest's recorded `harness_version`, `upgrade` exits with
  status 2 and prints, verbatim (`format_downgrade_refusal()`):

  ```
  `--to v<target>` is older than the installed v<installed>; downgrade is
  not supported -- pass `--allow-downgrade` if you specifically intend
  this.
  ```

  Nothing is written to the target wiki when this refusal fires.

- **`--allow-downgrade` opts in explicitly.** Passing this flag lets the
  downgrade proceed, but `upgrade` first prints a loud, unmissable banner
  (`format_downgrade_banner()`) before the write pipeline runs, warning
  that MANAGED and TEMPLATE files are about to be overwritten with the
  *older* release's content:

  ```
  ============================================================
  DOWNGRADE: content is moving BACKWARD from v<installed> to v<target>.
  Managed and template files will be overwritten with the OLDER
  release's content. Proceeding because --allow-downgrade was passed.
  ============================================================
  ```

There is no partial/selective downgrade: `--allow-downgrade` accepts the
full consequence of moving every MANAGED/TEMPLATE path backward, not a
per-file choice.

## 6. Removed-managed-path policy (MAJOR-removal guard)

A MANAGED or TEMPLATE path is never silently dropped by an `upgrade`. When
the resolved target version's own checkout no longer provides a *source*
for a path the installed manifest still records with role `managed` or
`template` (`removed_managed_paths()` in `upgrade.py`, comparing the old
manifest's managed/template paths against the paths the target version's
checkout actually still ships), `upgrade` treats this as a MAJOR removal
event and aborts before writing anything to the target wiki. It prints,
per removed path (`format_removal_abort()`):

```
upgrade: refusing to proceed -- v<target> no longer provides a source for
the following managed/template path(s); this is a MAJOR removal and the
target wiki was left unchanged (nothing was written to it):
  <path>: no longer provided by v<target>.
```

This is a **fail-loud guard, not a recovery mechanism**: it stops the
upgrade and names the affected paths so the operator can decide by hand
what to do (accept the loss, pin to an older version, or otherwise migrate
that content manually). It does not reconcile, archive, or auto-migrate
the removed paths itself — the manifest's `removed` role value is reserved
in `VALID_ROLES` (`scripts/manifest.py`) for a future, more complete
path-removal mechanism, but no caller in v1.0.0 assigns it yet.

Per §3, dropping a MANAGED/TEMPLATE path this way is only ever legitimate
at a MAJOR version boundary, and only after that path was marked
deprecated in a prior MINOR release.

## 7. Future fix()-scope restriction (MANAGED/TEMPLATE only)

v1.0.0 ships no migrations engine at all (no `migrations/` directory, no
per-version `report()`/`fix()` scripts, no `--fix`/`--force` modes) — this
is deferred, not built speculatively. If and when a future release
introduces one to perform a real data migration a plain schema/content
commit cannot express, the following restriction is binding from the
first version that ships it:

**A migration's `fix()` may only read or write paths whose manifest role
is `managed` or `template`. It may never touch a path recorded with role
`instance-fork` — the wiki author's own content — under any circumstance.**

An instance-fork path is, by definition, content the wiki author has
knowingly diverged from the library's own copy; a migration mutating it
would silently overwrite hand-authored work outside any diff or review the
author controls. This restriction must be structurally enforced (hash-
checked against the manifest's own role map before any write, not merely
documented) once such an engine exists, exactly as `upgrade.py`'s existing
drift/removal guards (§5, §6) already refuse to write outside their
declared scope today.

## 8. CHANGELOG requirement

`wiki-harness` does not yet have a `CHANGELOG.md` — that file is created by
a later task in this same phase, not by this document. This policy binds
whoever authors it:

**Every `CHANGELOG.md` entry must state which of PATCH, MINOR, or MAJOR the
release is, and must include an explicit "Compatibility" field** describing,
in prose, what a consumer running `upgrade` into that release needs to know
before doing so (new/changed finding codes, any MANAGED/TEMPLATE path
added or — MAJOR only — removed, any manifest or CLI change). A release
entry that only lists changes without stating its PATCH/MINOR/MAJOR
category and a Compatibility field is incomplete under this policy.

## 9. Independent verification / CI: nothing is shipped in v1.0.0

Earlier design notes for this project described an opt-in, default-off CI
workflow (a GitHub Actions job independently re-fetching upstream and
diffing a wiki's managed content against it) as the backstop against a
tampered local manifest. **That framing is retired as of this release.**

**No CI-based independent verification is shipped in v1.0.0 at all** — not
merely turned off by default. There is no CI workflow file, no
`ci_verify.py`, no `--ci` flag, and no test suite for any of the above,
anywhere in this repository or in what `init`/`upgrade` write into a
consumer wiki. The only integrity check that exists is `lint.py`'s
`HARNESS` finding, which re-hashes MANAGED/TEMPLATE files against the
values recorded in the wiki's own `.wiki-harness-manifest.json` — a
**self-consistency** check only. It cannot detect a committer (or a
process acting as one) who edits both a managed file and its own recorded
manifest hash together; nothing in v1.0.0 re-fetches or diffs against an
independent, external copy of the release.

Concretely, this leaves the risk this repository's own risk register names
as **risk #3** — commits authored via the GitHub API, or a cloud coding
agent's sandbox, structurally cannot go through `.githooks/*` at all,
independent of any local `core.hooksPath` setup — **unmitigated**. No
mechanism in this release defends against it. This is stated here plainly,
not softened, and it replaces the earlier "CI is the sole backstop"
framing entirely: as of v1.0.0, the honest statement is that nothing is
the backstop.

The condition under which this changes is recorded in the project's
Not-now list, and is reproduced here verbatim so this document stays the
single place a consumer needs to check:

> "Status: deferred -- not built at all for v1.0.0, not merely made opt-in and default-off... Unblocks when: a second committer or a cloud coding agent authors commits against this repo or any wiki built on this library."

Until that condition is met, `upgrade`'s and `lint`'s guarantees are
exactly what §2's table states and no more: internal self-consistency of
whatever is on disk, not independent proof that what is on disk matches
what an upstream release actually shipped.
