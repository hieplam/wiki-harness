---
id: c3-502
c3-seal: 05c70713a6f418b22d5509b6f09262b56be19adea4aaadc3f76612aeddf4afd5
title: release-build
type: component
category: foundation
parent: c3-5
goal: |-
    Turn a merged pull request into a published, checksummed release payload without a human
    bumping a version or writing a changelog entry -- so what a consumer installs is always an
    artifact that was built from a tag and proved against the full test suite.
uses:
    - ref-ownership-classes
    - rule-pure-core-impure-edge
    - rule-stdlib-only-py39
---

## Goal

Turn a merged pull request into a published, checksummed release payload without a human
bumping a version or writing a changelog entry -- so what a consumer installs is always an
artifact that was built from a tag and proved against the full test suite.

## Parent Fit

| Field | Value |
| --- | --- |
| Container | c3-5 (distribution) |
| Category | Foundation -- c3-501 (launcher) can only install what this component publishes |
| Depends on | c3-4 (tests): the assets job re-runs the whole suite against the tag before building anything. c3-1/c3-2/c3-3 as CONTENT -- PAYLOAD_PATHS names the trees it copies, but it imports none of them |
| Depended on by | c3-501 (launcher) and install.sh, which download the asset and the .sha256 this component uploads |

## Purpose

Own `tools/build_release.py` and the two workflows in `.github/workflows/`. The build copies
`PAYLOAD_PATHS` into a single top-level directory, writes `RELEASE.json` beside them, and
produces a byte-reproducible `.tar.gz` plus a `.sha256`. `release-please.yml` computes the next
version from Conventional Commit types, opens a release PR, and on merge tags, releases,
re-runs the suite against that tag, builds the payload and uploads it. `test.yml` runs the
suite on every pull request and on main.

`RELEASE.json` exists because an unpacked payload has no `.git`: without it `init.py`'s
`read_source_url`/`read_source_ref`/`read_source_commit` degrade to a local path, `"unknown"`
and forty zeros, and `source_url` is the value `upgrade --check` later feeds to `git
ls-remote`.

Non-goal: this component decides nothing about what a release MEANS. Which of PATCH, MINOR or
MAJOR a change is comes from the commit type the author chose, graded against
`docs/compatibility-policy.md` §2; the automation only computes and publishes.

Non-goal: it never verifies a wiki. The suite it runs is the library's own.

## Governance

| Reference | Type | Governs | Precedence | Notes |
| --- | --- | --- | --- | --- |
| rule-pure-core-impure-edge | rule | The version/tag agreement check, the archive name, RELEASE.json's content and the tar member normalisation are pure; the git reads, the copy and the archive write are named edges | Hard | Same split every module in the library follows |
| rule-stdlib-only-py39 | rule | tools/build_release.py imports only the standard library, and the assets job pins Python 3.9 -- the floor the payload promises consumers | Hard | The build must not need anything a consumer's interpreter lacks |
| ref-ownership-classes | ref | PAYLOAD_PATHS must carry every path init/upgrade place into a wiki under any ownership class, or a release scaffolds a broken one | Hard | The payload is the union of what the three library-owned classes need on disk |

## Contract

| Surface | Direction | Contract | Boundary | Evidence |
| --- | --- | --- | --- | --- |
| python3 tools/build_release.py --tag vX.Y.Z --out-dir <dir> | IN/OUT | Refuses with exit 2 when the tag and VERSION disagree, or when a PAYLOAD_PATHS entry is missing -- an incomplete payload is never written. On success writes exactly the archive and its .sha256 | CLI process boundary | tests/test_build_release.py |
| Payload contents | OUT | Every scripts/.py, every githooks/ and every templates/* present in the repository ships, plus init.py, upgrade.py, bin/, VERSION and RELEASE.json. tests/, docs/, .c3/ and tools/ never do | Filesystem output contract | tests/test_build_release.py::BuiltPayloadIsUsable |
| Reproducibility | OUT | Two builds of one tag are byte-identical: member mtime/uid/gid are zeroed and the gzip header is pinned. The dispatch recovery path can therefore re-upload a tag someone already installed without publishing different bytes under the same name | Filesystem output contract | tests/test_build_release.py::test_the_build_is_reproducible |
| RELEASE.json | OUT | Records version, tag, commit and a fetchable https source_url, so a .git-less payload writes an honest manifest rather than a cache path, "unknown" and forty zeros | Filesystem output contract | tests/test_init.py::ReleasePayloadProvenance |
| Release automation | OUT | A release is cut only from main, only by merging the release PR, and its payload is uploaded only after the full suite passes against the tag. A failed upload is retried by workflow_dispatch, never by re-running on push -- release-please reports release_created: false once the release exists | GitHub Actions boundary | tests/test_release_config.py |

## Derived Materials

| Material | Must derive from | Allowed variance | Evidence |
| --- | --- | --- | --- |
| tools/build_release.py | This component's Contract surfaces. PAYLOAD_PATHS is the contract for what a consumer receives | Staging mechanics may change; refusing an incomplete payload and byte-reproducibility may not | tests/test_build_release.py |
| .github/workflows/release-please.yml | This component's release-automation Contract row, plus release-please-config.json and .release-please-manifest.json | Runner images and action versions may change; running the suite before upload, and the dispatch recovery path, may not | tests/test_release_config.py |
| .github/workflows/test.yml | This component's release-automation Contract row -- the clause that a payload is uploaded only after the full suite passes -- applied to every pull request and to main, across the 3.9 floor and a current Python | The version matrix may grow; dropping 3.9 would break the floor rule-stdlib-only-py39 states | tests/test_release_config.py |

## Change Safety

| Risk | Trigger | Detection | Required Verification |
| --- | --- | --- | --- |
| A new top-level path a wiki needs is not in the payload | Adding a file or directory init/upgrade place into a wiki | The payload test enumerates the repository's real scripts/ and templates/ and asserts each one ships | tests/test_build_release.py::test_every_scripts_py_and_template_ships |
| The manifest and VERSION drift, so releases skip or repeat a version | A hand edit to either file | release-please computes the next version from the manifest, not VERSION | tests/test_release_config.py::ManifestTracksTheVersionFile |
| A release is tagged but has no installable asset | An upload failure after the tag exists | install.sh refuses and names the reason; the workflow keeps a tag-dispatch path to re-upload | tests/test_install_sh.py; workflow_dispatch with the tag |
