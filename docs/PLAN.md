# wiki-harness extraction — task plan

Source of truth: `/Users/hip/repo/wiki-harness-analysis/plan/plan-v3.md` (the contract) and `tasks-v3.json`.
Each task's hunter ticks its own box in the SAME commit as the code (tribe crash-safety invariant).

## P0 — Library repo bootstrap

- [x] P0.1 — Bootstrap the wiki-harness repo skeleton
- [x] P0.2 — Run C3 onboarding on wiki-harness
- [x] P0.3 — Add the library's own test runner wrapper

## P1 — Extract code (library-only, verbatim port + minimal tested fixes)

- [x] T01 — Fork scripts/.githooks/tests verbatim from ogp-wiki HEAD f8b43fb
- [x] T02 — Synthetic-fixture test suite + test_genericity.py
- [x] T03 — Prose/code fixes 1-4: genericize examples, byte-match CARD_KEY, fix raw: example, remove dangling spec ref
- [x] T04 — Schema-driven card-id mechanism (delete hardcoded CARD_ID_RE)
- [x] T05 — git_changes()/HOOKS-positive-path E2E tests in the library suite
- [x] T06 — Golden ERROR-before-WARN sort-order test
- [x] T07 — Close CARD_VALUE/ENCODING/fixup-squash coverage gaps
- [x] T08 — RULES_FILES generalization in lint.py (A1 blocker fix)
- [x] T08b — RULES_FILES parity in the card-lint CLI discovery (card_frontmatter_lint.py main())
- [x] C3-1 — C3 change-unit: amend ref-verbatim-port to name T08b and bound audit-driven fixes

## P2 — Templates / init

- [x] T09 — manifest.py: pure compute_manifest/diff_manifest + source_url + reserved removed role
- [x] T10 — Split sources/cards/AGENTS.md into managed mechanism + templates/recipes.md
- [x] T11 — Add HARNESS finding to lint.py as an eighth impure edge (no marker branch)
- [x] T12 — Author remaining templates (AGENTS.root, README, CLAUDE.root/nested MANAGED, gitignore, etc.)
- [x] T12b — lint.py: links inside code (fenced blocks, inline spans) are not links (A10)
- [x] T13 — Write init.py full flow (no --ci; CLAUDE.md tracked MANAGED)
- [ ] T14 — init.py --non-interactive/--answers-file/--origins flags
- [ ] T15 — upgrade --check standalone mode

## P3 — upgrade

- [ ] T16 — upgrade.py step 1: refuse-before-write drift check incl. missing-path drift
- [ ] T16B — Core apply pipeline: fetch target, scratch-copy, overwrite, lint scratch, bare promote-copy, write manifest (steps 5-6,8-9-10-11-12; inserted by verification fix, see Verification dispositions)
- [ ] T17 — Downgrade guard
- [ ] T18 — --adopt-drift mechanism, extended for a missing path
- [ ] T19 — MAJOR-removal guard
- [ ] T20 — --apply vs. dry-run split
- [ ] T21 — Atomic promote via try/except -> git checkout -- . (no marker, no --resume — A3)
- [ ] T22 — Idempotency fast path
- [ ] T23 — --commit + auto git checkout -- . on failed post-write self-check
- [ ] T24 — CLI polish: finalize argparse + exact message strings (no --resume, no --ci)
- [ ] T25 — Write docs/compatibility-policy.md (no CI-is-sole-backstop framing — A4)

## P4 — Migrate ogp-wiki

- [ ] T26 — Cut wiki-harness v1.0.0: tag, changelog, full suite green
- [ ] T27 — Run --adopt migration on a disposable ogp-wiki clone (explicit flags, no back-parser)
- [ ] T28 — Delete tests/ entirely from the ogp-wiki clone (A6)
- [ ] T29 — Run the baseline oracle against the migrated clone; diff vs before/ per the 3 named deltas
- [ ] T30 — PR review + merge migration to the real ogp-wiki repo

## P5 — Second-wiki smoke

- [ ] T31 — init a throwaway synthetic ai-wiki fixture; run full E2E incl. customized id.pattern
- [ ] T32 — OPTIONAL, owner-timed: real kept ai-wiki repo (NOT part of DONE, D8)
