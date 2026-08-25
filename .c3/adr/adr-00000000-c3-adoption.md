---
id: adr-00000000-c3-adoption
c3-seal: 41586d70f0d12cc019d4cba5a21b851e85b15189142c6f34e3fbd0ad134a9104
title: C3 Architecture Documentation Adoption
type: adr
goal: |-
    Onboard `/Users/hip/repo/wiki-harness` onto the C3 architecture model — the only C3 onboarding
    this whole wiki-harness-extraction engagement performs (ogp-wiki itself is never onboarded, D7) —
    modeling the four containers plan-v3.md §2.1 names (scripts, lifecycle, templates, tests) as real,
    frozen C3 facts before any of Phase 1-3's code exists, so the extraction has a checked
    architectural reference to build against instead of inventing structure ad hoc per task.
status: done
affects:
    - c3-0
---

## Goal

Onboard `/Users/hip/repo/wiki-harness` onto the C3 architecture model — the only C3 onboarding
this whole wiki-harness-extraction engagement performs (ogp-wiki itself is never onboarded, D7) —
modeling the four containers plan-v3.md §2.1 names (scripts, lifecycle, templates, tests) as real,
frozen C3 facts before any of Phase 1-3's code exists, so the extraction has a checked
architectural reference to build against instead of inventing structure ad hoc per task.

## Context

`wiki-harness` is a brand-new repo, currently just P0.1's empty skeleton (`README.md`, `VERSION`,
`docs/PLAN.md`, `.gitignore` — no `scripts/`, no `templates/`, no lifecycle code, no tests yet).
plan-v3.md §2.1 already specifies the target repo layout in detail: three vendored linters forked
byte-identical from ogp-wiki plus two git hooks (`scripts` container), `init.py`/`upgrade.py`/
`manifest.py` (`lifecycle` container), every MANAGED/TEMPLATE/SEEDED file class a wiki instance is
stamped with (`templates` container), and the library's own test suite — the only place any
harness test lives, per A6 (`tests` container). The owner's global rule ("Always use the C3 skill,
no exceptions unless Project scope say NO") applies to this new code repository; D7 explicitly
scopes C3 onboarding to `wiki-harness` only, never `ogp-wiki` (which, post-migration, is content
plus vendored harness files, not a codebase this engagement's C3 mandate covers).

Because no code exists yet, every component's future `.c3/eval/<fact>.yaml` `code:` glob binding
will show 0-file drift through the whole of Phases 1-3 — expected, acknowledged in advance by
plan-v3.md's Verification dispositions table (executability optional #7), and not a hard failure,
since the wrapper's `eval` operation exits success regardless of verdict. A final `eval`/`audit`
pass once Phase 3 lands real code is recommended but out of scope for every task in this plan,
including this one.

## Decision

Onboard with the wrapper's `init` operation, then walk top-down through one genesis-ADR
change-unit: the system (`c3-0`, Goal + 4 Abstract Constraints), the four containers plan-v3.md
§2.1 names verbatim (scripts/lifecycle/templates/tests), and inside them the 13 components the
plan's own file tree already implies — the three linters plus git-hooks wiring under `scripts`
(`c3-101`/`c3-102`/`c3-103`/`c3-110`), manifest/init/upgrade under `lifecycle` (`c3-201`/`c3-210`/
`c3-211`), the three ownership classes (TEMPLATE/MANAGED/SEEDED) under `templates` (`c3-301`/
`c3-302`/`c3-303`), and the fixture plus the two test-module groupings under `tests` (`c3-401`/
`c3-410`/`c3-411`) — each wired to two new refs (`ref-verbatim-port`, `ref-ownership-classes`) and
two new rules (`rule-pure-core-impure-edge`, `rule-stdlib-only-py39`) that plan-v3.md and the
owner's global pure-core rule already make load-bearing for this library.

This is the *intended* architecture as scaffolding, not a description of code that exists yet — it
wins over waiting until Phase 1-3 land real files because the owner's onboarding mandate names
P0.2, before any code, as the one and only C3-onboarding task in the whole engagement (D7), and
because a frozen reference model gives every Phase 1-3 hunter a checked target to build against
instead of ad hoc, task-by-task structure.

## Affected Topology

| Entity | Type | Why affected | Evidence | Governance review |
| --- | --- | --- | --- | --- |
| c3-0 | system | Genesis system fact for the whole wiki-harness repo: Goal, the 4-container membership (tool-synthesized), and 4 Abstract Constraints, all authored in this ADR | c3-0#n474@v2:sha256:f244b33f0a7420ef7c7d4eea824fc38bb91ce00ffb655d4c026099e0908bd128 | Confirm Goal states the library's purpose and Abstract Constraints match plan-v3.md's D2 (Py3.9/stdlib), byte-identical-behaviour, A6 (no tests/ in a wiki instance), and A3/A4 (no marker/--resume/--ci) constraints |
| c3-1 | container | New scripts container, created to hold the 3 vendored linters plus git-hooks wiring, per plan-v3.md §2.1 | c3-1#n490@v2:sha256:a03dbb27299030a765a0859e42a59419bdbb417fcd44aed08fb2ed5751183f0a | Confirm Goal/Responsibilities match plan-v3.md §2.1's scripts description; confirm membership table synthesizes c3-101/c3-102/c3-103/c3-110 |
| c3-2 | container | New lifecycle container, created to hold init.py/upgrade.py/manifest.py, per plan-v3.md §2.1 | c3-2#n503@v2:sha256:c3760fb59bd053e56cf8f3f7d67a9dd4ca5a999cfee95e4fcbb1c4e3ecf32eed | Confirm Goal/Responsibilities match plan-v3.md §2.1's lifecycle description; confirm membership table synthesizes c3-201/c3-210/c3-211 |
| c3-3 | container | New templates container, created to hold every MANAGED/TEMPLATE/SEEDED source file, per plan-v3.md §2.1 | c3-3#n515@v2:sha256:cb995469328d622c43c74cb8e18caa8302dc43afa5885e6f5b3506d0c3c15139 | Confirm Goal/Responsibilities match plan-v3.md §2.1's templates description; confirm membership table synthesizes c3-301/c3-302/c3-303 |
| c3-4 | container | New tests container, created to hold the library's own suite, per plan-v3.md §2.1 and A6 | c3-4#n527@v2:sha256:9670222ab66606630dd548543961abe45f1fd20b5ce60215f6f24a475f04c258 | Confirm Goal/Responsibilities match plan-v3.md §2.1's tests description and A6's "only place any harness test lives"; confirm membership table synthesizes c3-401/c3-410/c3-411 |
| c3-101 | component | New Foundation component: scripts/lint.py's pure check_*/run() plus its scan()/git_changes()/hooks_finding() edges | c3-101#n110@v1:sha256:633523ed677c89602627f44aa55865b3f45d0b1c060837521cb0a7e990f47faa | Confirm Governance cites rule-pure-core-impure-edge, rule-stdlib-only-py39, ref-verbatim-port, all authored in this same ADR |
| c3-102 | component | New Foundation component: scripts/card_frontmatter_lint.py's card-schema validation | c3-102#n138@v1:sha256:c539f9ea1e1e70023000452635d67e75be016a2882f178e6d7aeedecdbd8d565 | Confirm Governance cites rule-pure-core-impure-edge, rule-stdlib-only-py39, ref-verbatim-port |
| c3-103 | component | New Foundation component: scripts/check_commit_msg.py's commit-message validation | c3-103#n164@v1:sha256:1be14b74304152dffc73f12dd9b7fca2e2b4295d4354108d576d957ca1b659eb | Confirm Governance cites rule-pure-core-impure-edge, rule-stdlib-only-py39, ref-verbatim-port |
| c3-110 | component | New Feature component: githooks/pre-commit/githooks/commit-msg, wiring c3-101/c3-103 into every commit | c3-110#n190@v1:sha256:f272daf75c592f7490fefe7424eeadaf932c5986e1d4cad0a6475a856525dde4 | Confirm Governance cites ref-verbatim-port; confirm Parent Fit names c3-101/c3-103 as dependencies |
| c3-201 | component | New Foundation component: manifest.py's pure compute_manifest/diff_manifest plus its I/O edge | c3-201#n224@v1:sha256:5647debd2277602cdd057ce61f6e31fbd919d0ff026ecc58ff7b4e8305369b98 | Confirm Governance cites rule-pure-core-impure-edge, rule-stdlib-only-py39, ref-ownership-classes |
| c3-210 | component | New Feature component: init.py's 16 ordered steps, stamping a brand-new wiki instance | c3-210#n252@v1:sha256:2cba2aceeb3d79bfbe10c89f08553587d67a3389f8bc0baadec83cf19d768a4c | Confirm Governance cites rule-pure-core-impure-edge, rule-stdlib-only-py39, ref-ownership-classes; confirm Contract cites plan-v3.md §3.1 |
| c3-211 | component | New Feature component: upgrade.py's --check mode plus its 13 ordered --apply/dry-run steps | c3-211#n280@v1:sha256:d5fad8f079f65d5d320ffdad1df8cc079eac795bbad727248fa4856e795b94ff | Confirm Governance cites rule-pure-core-impure-edge, rule-stdlib-only-py39, ref-ownership-classes; confirm Contract cites plan-v3.md §3.2 |
| c3-301 | component | New Foundation component: the 2 TEMPLATE-class sources (AGENTS.root.md.tmpl, README.md.tmpl) | c3-301#n317@v1:sha256:bad70989a99b798f082cf9f728985a743d9618a2b30b2c292221625fed61a728 | Confirm Governance cites ref-ownership-classes; confirm this is one of the 3 components splitting c3-3 along the ref's classes |
| c3-302 | component | New Foundation component: the 5 MANAGED-class sources (3 AGENTS.md files + 2 CLAUDE.md templates) | c3-302#n342@v1:sha256:52a67845e8cd8b834bfcbcde8156e5aa98ffe8c19be19eeb502600f899f7c009 | Confirm Governance cites ref-ownership-classes |
| c3-303 | component | New Foundation component: the 5 SEEDED-class sources (recipes.md, card-schema.default.json, VISION.skeleton.md, index.md.header.tmpl, gitignore.snippet) | c3-303#n366@v1:sha256:82eaf191a17263024b1fb33cc934599b125dea7fd98a018987b43eedc18e7ed7 | Confirm Governance cites ref-ownership-classes |
| c3-401 | component | New Foundation component: tests/fixtures/sample-wiki/, the one synthetic fixture every test in c3-4 depends on | c3-401#n399@v1:sha256:6e24022a0799f9cc3909a180b40c2a4e20610447c6f43000193afbafda078bed | Confirm Parent Fit names c3-410/c3-411 as dependents; confirm fixture is never ogp-wiki content |
| c3-410 | component | New Feature component: tests/test_lint_*.py + tests/test_genericity.py, proving c3-1's behaviour | c3-410#n423@v1:sha256:4bf5c52eea921ec91006890d4f516b9629e000ced8acaf40dd4355e9ec0f3b9a | Confirm Governance cites rule-stdlib-only-py39, ref-verbatim-port |
| c3-411 | component | New Feature component: tests/test_init.py/test_upgrade.py/test_harness_integrity.py, proving c3-2's behaviour | c3-411#n448@v1:sha256:9ff58214d7e79dab8108b474089b6f597fb3831c2686ed3df31cc07935efdf7a | Confirm Governance cites rule-stdlib-only-py39, ref-ownership-classes |

## Compliance Refs

| Ref | Why required | Evidence | Action |
| --- | --- | --- | --- |
| ref-verbatim-port | Cited by c3-101/c3-102/c3-103/c3-110/c3-301/c3-410's Governance tables to justify porting scripts/*.py and the git hooks byte-identical rather than rewriting them | ref-verbatim-port#n51@v1:sha256:778170f09e69afb039352f0e1093d74e229485636100b624135dc8b3f08ccc7c | create-ref |
| ref-ownership-classes | Cited by c3-201/c3-210/c3-211/c3-301/c3-302/c3-303/c3-411's Governance tables to justify the TEMPLATE/MANAGED/SEEDED/INSTANCE split that drives what upgrade may silently overwrite | ref-ownership-classes#n59@v1:sha256:57cd694d44239fb8322235a153ec5af3083afcf8ebc5cebf53e76c49e85bc100 | create-ref |

## Compliance Rules

| Rule | Why required | Evidence | Action |
| --- | --- | --- | --- |
| rule-pure-core-impure-edge | Cited by c3-101/c3-102/c3-103/c3-110/c3-201/c3-210/c3-211's Governance tables to enforce the owner's global pure-core rule across every scripts/lifecycle module | rule-pure-core-impure-edge#n67@v1:sha256:399ea3761ff0b0ef1c3475a7de6d93821e7e2fc98da7cc08bd1f048789ce8d08 | create-rule |
| rule-stdlib-only-py39 | Cited by c3-101/c3-102/c3-103/c3-201/c3-210/c3-211/c3-410/c3-411's Governance tables to enforce the Python 3.9/stdlib-only floor (D2) across every module this ADR creates room for | rule-stdlib-only-py39#n84@v1:sha256:73c38cb86710504178722cecdfa01ab2c6b88aad384a6c516bc3edb8a1342c16 | create-rule |

## Verification

| Check | Result |
| --- | --- |
| test -d /Users/hip/repo/wiki-harness/.c3 | Exit 0 |
| C3X_MODE=agent bash <skill-dir>/bin/c3x.sh list | 1 system + 4 containers + 13 components + 2 refs + 2 rules, all status: active/materialized, no status: proposed/staged entities remaining |
| C3X_MODE=agent bash <skill-dir>/bin/c3x.sh change status adr-00000000-c3-adoption | Every one of the 21 patches shows applied |
| C3X_MODE=agent bash <skill-dir>/bin/c3x.sh check | 0 findings against the 21 non-ADR facts |
| C3X_MODE=agent bash <skill-dir>/bin/c3x.sh check --include-adr --fix | adr-00000000-c3-adoption latches accepted -> done once every Affected Topology row's Evidence cell is a fresh cite handle |
