---
id: c3-501
c3-seal: d029957fa45c655eb23ca3729ab415349a5dd9ab61708d729016f3e42058cb6b
title: launcher
type: component
category: foundation
parent: c3-5
goal: |-
    Resolve which wiki-harness release a command needs, make that release present on disk, prove
    it is what it claims to be, and hand over to its own entry points -- so `wiki-harness init
    my-wiki --wiki-title 'My Wiki'` works from any directory with no clone anywhere.
uses:
    - ref-ownership-classes
    - rule-pure-core-impure-edge
    - rule-stdlib-only-py39
---

## Goal

Resolve which wiki-harness release a command needs, make that release present on disk, prove
it is what it claims to be, and hand over to its own entry points -- so `wiki-harness init
my-wiki --wiki-title 'My Wiki'` works from any directory with no clone anywhere.

## Parent Fit

| Field | Value |
| --- | --- |
| Container | c3-5 (distribution) |
| Category | Feature -- the user-facing half of distribution: the command on PATH and the script that puts it there |
| Depends on | c3-502 (release-build) for the payload and checksum it downloads; a published GitHub Release for both. Nothing inside c3-2, which it invokes as a child process rather than importing |
| Depended on by | Nothing in this repository. Its dependents are users' shells and the agents that drive them |

## Purpose

Own `bin/wiki-harness` and `install.sh`. The launcher decides the release (newest for `init`,
exactly `--to X` for `upgrade`, newest for `upgrade --check` since it names none, and
`--harness-version X` overriding all three), downloads and verifies it, caches it under
`~/.cache/wiki-harness/releases/<version>/`, and execs that release's own `init.py` or
`upgrade.py`. Everything after the subcommand is passed through untouched, so a new payload
flag needs no change here.

Non-goal: the launcher contains no harness logic of any kind -- no lint, no manifest, no
template rendering. It never reads or writes a wiki. If a behaviour can be described in terms
of a wiki's contents, it belongs in `c3-2`, not here.

Non-goal: it does not manage the cache beyond creating entries. There is no eviction, no TTL
on a downloaded payload, and no repair of a corrupted cache entry -- a release directory
either has an `init.py` or is treated as absent.

## Governance

| Reference | Type | Governs | Precedence | Notes |
| --- | --- | --- | --- | --- |
| rule-pure-core-impure-edge | rule | Version selection, URL construction, archive-member safety and checksum comparison are pure functions over data; every network call, extraction and process spawn is a named edge with an injectable seam | Hard | This is what lets all but one launcher test run with no network |
| rule-stdlib-only-py39 | rule | bin/wiki-harness imports urllib, tarfile, hashlib, json and subprocess only, and opens with from future import annotations | Hard | It runs on whatever interpreter the user has, before any harness code exists locally; install.sh refuses below 3.9 |
| ref-ownership-classes | ref | N.A - nothing this component produces enters a wiki, so no path it touches has an ownership class | Hard | The absence is the point: it is why tools/ and bin/ are not scripts/ |

## Contract

| Surface | Direction | Contract | Boundary | Evidence |
| --- | --- | --- | --- | --- |
| wiki-harness <init\|upgrade\|versions\|self-update> [--harness-version X] [payload flags] | IN/OUT | Everything after the subcommand reaches the payload verbatim; --harness-version is consumed here and never passed on. Every failure exits non-zero with one line -- no traceback ever escapes a command on PATH | CLI process boundary | tests/test_launcher.py |
| Release resolution | OUT | init and upgrade --check take the newest published release; upgrade --to X takes exactly X; --harness-version overrides both. A release already cached is used with no network call at all | Network + filesystem edge | tests/test_launcher.py::VersionSelection |
| Payload integrity | OUT | A payload is unpacked only after its bytes hash to the .sha256 published beside it. An unreadable or empty checksum is a refusal, never a pass; a failed verification leaves no cache entry for the next run to trust | Impure edge -- download + hash | tests/test_launcher.py::ChecksumVerification |
| Archive containment | OUT | No archive member is written outside the cache directory: absolute paths, .. components and link members are each refused and abort the unpack | Impure edge -- tarfile extraction | tests/test_launcher.py::ArchiveSafety |
| curl -fsSL .../install.sh \| sh | IN/OUT | Installs the launcher under $HOME only, never sudo and never a system directory; verifies the checksum before installing; renames into place so an interrupt cannot leave a truncated executable on PATH; refuses a release with no bin/wiki-harness | Shell process boundary | tests/test_install_sh.py |

## Derived Materials

| Material | Must derive from | Allowed variance | Evidence |
| --- | --- | --- | --- |
| bin/wiki-harness | This component's Contract surfaces. The passthrough rule is absolute: a payload flag must never require a change here | Cache layout and message wording may change; the resolution rule and the refusal-before-unpack ordering may not | tests/test_launcher.py |
| install.sh | This component's installer Contract row. POSIX sh only -- it runs under dash and under macOS /bin/sh | Where it installs (WIKI_HARNESS_BIN_DIR) and which release (WIKI_HARNESS_VERSION) are caller-controlled; writing outside $HOME is not | tests/test_install_sh.py |
| tests/test_launcher.py, tests/test_install_sh.py | This component's Contract's failure surfaces, exercised against a real payload and a real local HTTP server | Test framing may vary; the offline-cache-hit and tampered-payload assertions may not | ./run_tests.sh |

## Change Safety

| Risk | Trigger | Detection | Required Verification |
| --- | --- | --- | --- |
| A seam-injected test passes while the real network call is broken | Any change to http_get or the headers it sends | The v1.3.1 defect: every test injected a fetch seam, so a 415 from the JSON API reached users instead of CI | tests/test_launcher.py::RequestHeaders captures the real urllib Request, not a seam |
| The launcher and payload disagree about a flag | A flag added to init.py/upgrade.py that the launcher intercepts | Passthrough is asserted argument-for-argument | tests/test_launcher.py::CommandLineParsing |
| A published release cannot be installed at all | A payload built without bin/, or an asset that failed to upload | install.sh refuses with the reason named | tests/test_install_sh.py; a real curl-pipe-sh run against the published release |
