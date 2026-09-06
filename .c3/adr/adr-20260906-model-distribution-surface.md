---
id: adr-20260906-model-distribution-surface
c3-seal: 0846cca34d6eddef809862f4fec437eb323048ad1b67c1044c1f654d45d217eb
title: model-distribution-surface
type: adr
goal: |-
    Model the distribution surface the library grew across v1.2.1-v1.3.1 -- an installed
    `wiki-harness` command, a `curl | sh` installer, a release payload, and the release automation
    that publishes it -- and reconcile the two lifecycle facts whose stated behaviour the same work
    changed. The architecture model currently describes a library that is only ever run out of a git
    checkout; that has not been the primary way it runs since v1.3.0.
status: accepted
date: "2026-09-06"
---

## Goal

Model the distribution surface the library grew across v1.2.1-v1.3.1 -- an installed
`wiki-harness` command, a `curl | sh` installer, a release payload, and the release automation
that publishes it -- and reconcile the two lifecycle facts whose stated behaviour the same work
changed. The architecture model currently describes a library that is only ever run out of a git
checkout; that has not been the primary way it runs since v1.3.0.

## Context

Through v1.2.1 a consumer cloned this repository at a tag and ran `python3 <clone>/init.py`. The
source tree was the runtime. `c3-2` (lifecycle) and its components model exactly that, and
`c3-211`'s Contract quotes `python3 wiki-harness/upgrade.py ...` as its CLI surface.

Three releases changed it. v1.3.0 added `bin/wiki-harness` (a launcher that resolves a release,
verifies its published checksum, caches it, and hands over to that release's own entry points),
`install.sh`, `tools/build_release.py`, and two GitHub workflows that cut releases with
release-please and upload the payload. v1.2.1 taught `init.py` to read provenance from a
payload's `RELEASE.json` when there is no `.git`. v1.3.1 fixed the launcher's Accept header.

Four modelled facts are now stale or absent:

1. There is no fact for the launcher, the installer, or the release build. `c3x lookup
bin/wiki-harness` returns nothing, so nothing governs the code a user's `curl | sh` executes.
2. `c3-211`'s Purpose describes `resolve_library_checkout` implicitly through "fetch"; that step
now either takes a supplied payload path or fails closed, where before it ignored both git
return codes and could build a scaffold from the wrong release.
3. `c3-211` has no Contract row for the bytecode exclusion, a defect that shipped from v1.0.0
and copied `scripts/__pycache__/*.pyc` into consumers' wikis on every Linux upgrade.
4. `c3-210`'s Contract does not say that a scaffold can be built from a `.git`-less payload, or
what the manifest records when it is.

## Decision

Add a fifth container, `c3-5` (distribution), as a sibling of scripts/lifecycle/templates/tests,
holding two components: `c3-501` (launcher -- `bin/wiki-harness` plus `install.sh`) and `c3-502`
(release-build -- `tools/build_release.py` plus the two workflows). A container rather than
components under `c3-2` (lifecycle), because the boundary is real: lifecycle code runs INSIDE a
consumer's wiki and is vendored into it; distribution code never enters a wiki at all, and
`tools/` is deliberately not `scripts/` for exactly that reason.

Patch `c3-211` (Purpose, plus one new Contract row) and `c3-210` (one new Contract row) to state
the behaviour the code now has. Both are additive: no existing Contract row's meaning changes,
because the CLI surfaces those rows quote are unchanged -- the launcher wraps them, it does not
replace them.

## Affected Topology

| Entity | Type | Why affected | Evidence | Governance review |
| --- | --- | --- | --- | --- |
| c3-0 | system | Gains a fifth container; its Containers membership row is synthesized from the new child's parent link | c3-0#n696@v2:sha256:f244b33f0a7420ef7c7d4eea824fc38bb91ce00ffb655d4c026099e0908bd128 "Provide a versioned, standalone Python library that stamps a lint/hook/rules harness onto any" | Membership synthesized by the tool, not hand-authored |
| c3-5 | container | New. Nothing modelled the launcher, the installer, or the release build, so nothing governed the code a curl | sh runs | c3-5#n805@v3:sha256:416af92bbd5f1c7927b553455c1f0ff03fdf859dfd855ddccdf06fd1400ba6b3 "Put the harness on a user's machine and keep it current, so adopting a wiki is one command" | Created with c3-501 and c3-502 before this ADR, per the unguarded-create path |
| c3-211 | component | Its Purpose describes a fetch step that now either uses a supplied payload path or fails closed, and it has no Contract row for the bytecode exclusion that stopped upgrade copying .pyc files into consumers' wikis | c3-211#n380@v1:sha256:51a09922122097394d00f9a9f35b0b27ab223a467c2d597d196e20518d22bea4 "Own upgrade.py's standalone --check mode plus its 13 ordered --apply/dry-run steps" | Purpose re-authored, one Contract row inserted |
| c3-210 | component | Its Contract does not state that init can run from a .git-less release payload, nor what provenance the manifest then records | c3-210#n362@v1:sha256:393b7fd4fb6458e1f51a1961dc698ecd01f854800c2ab1700fa6c17ec22792f7 "python3 wiki-harness/init.py <target-dir> --wiki-title <title>" | One Contract row inserted |

## Compliance Rules

| Rule | Why required | Evidence | Action |
| --- | --- | --- | --- |
| rule-pure-core-impure-edge | The launcher is almost entirely edges -- network, filesystem, subprocess -- so the split has to be explicit or there is nothing left to test without a network | rule-pure-core-impure-edge#n589@v1:sha256:399ea3761ff0b0ef1c3475a7de6d93821e7e2fc98da7cc08bd1f048789ce8d08 "Keep every non-trivial computation across the library — the lint checks, the manifest diff, the" | Comply -- version selection, URL construction, member safety and checksum comparison are pure; every test but one runs with no network |
| rule-stdlib-only-py39 | bin/wiki-harness runs on whatever interpreter the user has, before any harness code is fetched | rule-stdlib-only-py39#n606@v1:sha256:73c38cb86710504178722cecdfa01ab2c6b88aad384a6c516bc3edb8a1342c16 "Guarantee every wiki-harness Python module runs on the oldest interpreter a consuming wiki might" | Comply -- urllib/tarfile/hashlib/json only; install.sh checks for >= 3.9 before installing |

## Work Breakdown

| Area | Detail | Evidence |
| --- | --- | --- |
| c3-5 | New container: distribution. Two components, both outside every consumer wiki | .c3/changes/<unit>/01 |
| c3-501 | launcher: bin/wiki-harness + install.sh | .c3/changes/<unit>/02 |
| c3-502 | release-build: tools/build_release.py + .github/workflows/* | .c3/changes/<unit>/03 |
| c3-211 | Purpose re-authored for the fail-closed library resolution; Contract row for the bytecode exclusion | .c3/changes/<unit>/04, 05 |
| c3-210 | Contract row for scaffolding from a release payload | .c3/changes/<unit>/06 |

## Enforcement Surfaces

| Surface | Behavior | Evidence |
| --- | --- | --- |
| tests/test_launcher.py | 35 tests: version selection, URL construction, tar member safety, checksum refusal, cache-hit-does-no-network, and the real urllib Request headers | ./run_tests.sh |
| tests/test_install_sh.py | Drives the real install.sh through sh against a real payload on a real local HTTP server | ./run_tests.sh |
| tests/test_build_release.py | Asserts payload CONTENTS and byte-reproducibility, not just that a tarball appeared | ./run_tests.sh |
| tests/test_release_config.py | Pins .release-please-manifest.json against VERSION, and the workflows' load-bearing parts | ./run_tests.sh |
| c3x check | The model itself stays valid and complete to its rung | c3x check |

## Alternatives Considered

| Alternative | Rejected because |
| --- | --- |
| Put the launcher under c3-2 (lifecycle) | Lifecycle code is vendored INTO a consumer wiki and runs there; distribution code never enters one. Collapsing them would make the ownership-class boundary that keeps tools/ out of scripts/ invisible in the model |
| One distribution component instead of two | The installer/launcher runs on a user's machine against the network; the release build runs in CI against a tag. Different failure modes, different tests, different blast radius |
| Leave c3-210/c3-211 alone and only add the new container | Their Contract rows would keep describing behaviour the code no longer has -- the exact staleness that makes the next reviewer file a finding against correct code |

## Risks

| Risk | Mitigation | Verification |
| --- | --- | --- |
| The model describes a launcher version that drifts from bin/wiki-harness as it changes | c3-501's Derived Materials names the file and its test module, so a change with no fact update is visible in review | c3x check; tests/test_launcher.py |
| A future release forgets to ship a new top-level path in the payload | c3-502's Contract states PAYLOAD_PATHS is the contract, and the payload test asserts every scripts/*.py and every template ships | tests/test_build_release.py |

## Verification

| Check | Result |
| --- | --- |
| ./run_tests.sh | 377 tests OK at the commit this unit reconciles |
| c3x check | ok, after apply |
| c3x read c3-5 --full | container with both components in its synthesized membership table |
| curl -fsSL .../install.sh | sh && wiki-harness init ... | verified against published v1.3.1: lint clean, manifest records v1.3.1 and an https source_url |
