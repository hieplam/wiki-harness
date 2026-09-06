---
id: c3-5
c3-seal: ba44b2406714db3b0969bbdc30bf71b92c13ee26743b2c350440c361a28dfa3d
title: distribution
type: container
boundary: service
parent: c3-0
goal: |-
    Put the harness on a user's machine and keep it current, so adopting a wiki is one command
    rather than a clone, a tag checkout, and a path to a file inside it -- and so the artifact a
    user runs is a published, checksummed release rather than whatever a working copy happens to
    contain.
---

## Goal

Put the harness on a user's machine and keep it current, so adopting a wiki is one command
rather than a clone, a tag checkout, and a path to a file inside it -- and so the artifact a
user runs is a published, checksummed release rather than whatever a working copy happens to
contain.

## Components

| ID | Name | Category | Status | Goal Contribution |
| --- | --- | --- | --- | --- |
| c3-501 | launcher | foundation | active | Resolve which wiki-harness release a command needs, make that release present on disk, prove |
| c3-502 | release-build | foundation | active | Turn a merged pull request into a published, checksummed release payload without a human |

## Responsibilities

Accountable for everything between a published GitHub Release and the moment a consumer's
`init`/`upgrade` starts running: resolving which release a command needs, fetching it,
proving it is the release it claims to be, caching it, and handing over.

Accountable for the other end too -- building the payload that gets published, and the
automation that cuts the release it is attached to.

**Explicitly not accountable for anything a wiki instance contains.** Nothing in this
container is ever copied into a consumer's wiki, appears in its manifest, or is governed by
`ref-ownership-classes`. That is the boundary between this container and `c3-2` (lifecycle),
whose code is vendored into every wiki and runs there. It is why `tools/build_release.py`
lives in `tools/` and not `scripts/`: `init.py`'s `copy_scripts()` vendors every
`scripts/*.py` into each wiki, so a build tool there would ship into every wiki and change
every consumer's manifest hash.

## Complexity Assessment

The risk here is not algorithmic, it is that every failure happens on someone else's machine,
before any harness code has been fetched, with no stack trace anyone will read. Both
components are therefore almost entirely impure edges -- network, filesystem, subprocess,
archive extraction -- and the discipline is to keep the decisions (which version, which URL,
is this archive member safe, does this checksum match) pure and separately testable, so that
the untestable part is only the I/O.

Two failure modes are singled out because they are silent rather than loud: a payload that
verifies against a checksum published from the same release it came from proves integrity
against a corrupt download and nothing more (`docs/compatibility-policy.md` §9.1), and an
archive whose member names are trusted can write anywhere the user can.
