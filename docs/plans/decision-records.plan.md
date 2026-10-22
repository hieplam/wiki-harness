# Decision pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `kind: decision` pages with an opt-in `DECISION` lint check, a `## Decisions` index section, and the template text that tells every wiki how to write and import them.

**Architecture:** A new pure module `scripts/decision_lint.py` exposes `check_decisions(files, strip_code, extract_links)`; `scripts/lint.py` imports it and calls it from `run()`, passing its own fence-stripping and link-extraction functions (no circular import, one fence parser). Template text goes into MANAGED/TEMPLATE files so it reaches existing wikis; SEEDED files change for new wikis only.

**Tech Stack:** Python 3.9 standard library, `unittest`, `./run_tests.sh`.

**Spec:** `docs/specs/decision-records.spec.md` (sections cited as §N below).

## Global Constraints

- Every `.py` file: Python 3.9, stdlib only, `from __future__ import annotations` as its first import (AGENTS.md hard rule 1).
- `decision_lint.py` is pure: no filesystem, subprocess, clock or environment access; its docstring lists its pure functions (hard rule 2).
- `lint.py` diff is the import line and the call in `run()` only (hard rule 4, gap-ledger precedent `cada8d8`).
- No consumer-specific name in `scripts/`, `githooks/`, `templates/` (hard rule 5); examples use `widget`.
- Finding code `DECISION`, severity `ERROR`, messages exactly as §4.4 (contract from 1.5.0).
- No `DECISION` finding, and no other change in output, for any page without `kind: decision` (§2 anti-goals).
- Tests drive `init.py` as a subprocess against temp directories, git isolated with `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` = `os.devnull`.
- `.c3/` is not touched (spec §6).

## Review Focus

1. A page saved with CRLF line endings: headings and the index section must still be found (`## Context\r`). Test in Task 1 and Task 3.
2. `supersedes:` with an empty value or `[]`: means "replaces nothing", no finding. Test in Task 1.
3. Duplicate values (`supersedes: [old, old]`): one finding per distinct problem, never two. Test in Task 2.
4. `index.md` with two `## Decisions` headings: both sections count as one list. Test in Task 3.
5. An indented index list line (`  - [x](./wiki/x.md) — decided`): still an entry. Test in Task 3.

---

### Task 1: Page-level checks in `scripts/decision_lint.py`

**Files:**
- Create: `scripts/decision_lint.py`
- Create: `tests/test_decision_lint.py`

**Interfaces:**
- Consumes: `card_frontmatter_lint.Finding`, `parse_frontmatter`; `lint._strip_code`, `lint.extract_links` (tests pass them in exactly as `run()` will).
- Produces: `check_decisions(files: dict[str, str], pages: list[str], strip_code: Callable[[str], str], extract_links: Callable[[str], list[str]]) -> list[Finding]`, where `pages` is `lint._wiki_pages(files)` (one definition of "wiki page", not two); constants `DECISION_STATUSES = ("proposed", "decided", "superseded")`, `REQUIRED_SECTIONS = ("Context", "Decision", "Rejected options", "Consequences")`.

- [ ] **Step 1: Write failing tests** in `tests/test_decision_lint.py` with a helper `_page(name, **meta, body=...)` that returns a `files` entry, and a helper `_run(files)` that calls `check_decisions(files, lint._wiki_pages(files), lint._strip_code, lint.extract_links)` and returns `sorted(findings)`. Every test asserts the **complete** list. Tests (one per §4.4 page-row, plus):
  - `test_no_decision_pages_no_findings` — sample fixture files → `[]`.
  - `test_other_kind_and_lookalike_keys_ignored` — `kind: runbook`, `status: draft`, `supersedes: x` → `[]`.
  - `test_kind_case_insensitive_and_list` — `kind: Decision` and `kind: [decision]` opt in (missing status reported).
  - `test_missing_status`, `test_bad_status` (`status: Decided` → `status 'Decided' is not one of: proposed, decided, superseded`), `test_bad_decided_date`, `test_decided_optional`.
  - `test_missing_sections_one_each_in_order` — page with only `## Context` → three findings.
  - `test_heading_variants_match` — `## Rejected Options`, `##  Rejected options  `, `## Rejected options ##` pass; `### Context` and `## Decisions` do not count.
  - `test_heading_in_fence_does_not_count`.
  - `test_crlf_page` (Review Focus 1).
  - `test_supersedes_value_shapes` — `old`, `[old]`, `[old, other]` pass shape; `old.md`, `./old.md`, `wiki/old.md`, `../wiki/old.md` → `supersedes value '<s>' is not a page name; write 'old'`; same for `superseded_by`.
  - `test_supersedes_empty_value` (Review Focus 2).
  - `test_supersedes_missing_page`, `test_supersedes_non_decision_page`, and the `superseded_by` twins.
  - The `files` helper always adds an `index.md` whose `## Decisions` section lists every decision page with its status, so the index rows of Task 3 never fire in Task 1 and Task 2 tests.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_decision_lint -q` — expect `ModuleNotFoundError: decision_lint`.
- [ ] **Step 3: Implement** the page-level rows of §4.4. Decision pages are the entries of `pages` whose frontmatter opts in (§4.1); page name = `PurePosixPath(path).stem`, and a name resolves to `wiki/<name>.md`. Normalise each of `supersedes`/`superseded_by` to a de-duplicated list (`""` → `[]`, `str` → `[str]`). Headings: run `strip_code(text)`, split on `"\n"`, match `^##(?!#)\s+(.*?)\s*#*\s*$` on each `rstrip("\r")`-ed line, collapse whitespace, `casefold()`.
- [ ] **Step 4: Run** the same command — PASS.
- [ ] **Step 5: Commit** `git add scripts/decision_lint.py tests/test_decision_lint.py && git commit -m "feat(lint): check decision page keys and sections"`

### Task 2: Replacement rows R1–R3, P1–P3, C1

**Files:**
- Modify: `scripts/decision_lint.py`
- Modify: `tests/test_decision_lint.py`

**Interfaces:**
- Consumes/Produces: `check_decisions` from Task 1 (same signature).

- [ ] **Step 1: Write failing tests**, complete-list assertions, one per row of the §4.4 replacement table, plus:
  - `test_consistent_pair_no_findings` — new `decided` `supersedes: old`; old `superseded`, `superseded_by: new`.
  - `test_proposed_supersedes_leaves_old_untouched` — new `proposed` `supersedes: old`; old `decided`, no `superseded_by` → `[]`.
  - `test_invalid_status_gives_only_status_finding` — old `status: done`, new `decided` `supersedes: old` → only the `status 'done'` finding.
  - `test_wrong_name_reported_on_both_pages` — P2 on old and P3 on the named page.
  - `test_cycle_two_pages` and `test_self_loop` — C1 message `supersedes chain loops back to this page: a -> b -> a` / `a -> a`.
  - `test_duplicate_values_one_finding` (Review Focus 3).
- [ ] **Step 2: Run** `python3 -m unittest tests.test_decision_lint -q` — new tests FAIL.
- [ ] **Step 3: Implement** the rows. Only values that passed the shape/existence rows take part. Cycle walk: DFS along `superseded_by` in sorted order; the reported path is the first one found from `<p>`.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(lint): check that decision replacements name each other"` (stage the two files by path).

### Task 3: The `## Decisions` index checks

**Files:**
- Modify: `scripts/decision_lint.py`
- Modify: `tests/test_decision_lint.py`

- [ ] **Step 1: Write failing tests** for the four `index.md` rows of §4.4, plus: `test_index_status_case_insensitive` (`Decided` counts), `test_status_inside_link_text_does_not_count` (title `[We decided X](…)` on a `proposed` page without the word outside → finding), `test_second_link_is_a_reference` (superseded line linking the new page lists only the old page), `test_entry_for_missing_page_left_to_INDEX` (no `DECISION`), `test_crlf_index`, `test_two_decisions_sections` (Review Focus 4), `test_indented_list_line` (Review Focus 5), `test_no_decision_pages_no_section_needed`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement**: `strip_code(index)`, split lines, `rstrip("\r")`; a section opens at a line matching `^##(?!#)\s+decisions\s*#*\s*$` (case-insensitive) and closes at the next `^#{1,2}(?!#)\s`. For each line in a section, `extract_links(line)`; the first link resolved from `index.md` (`card_frontmatter_lint.resolve`) is the entry. Status test: remove every `\[[^\]]*\]\([^)]*\)` from the line, then search `\b<status>\b` with `re.IGNORECASE`.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(lint): check the Decisions section of the index"`.

### Task 4: Wire into `lint.py` and prove it end to end

**Files:**
- Modify: `scripts/lint.py` (import block near line 23; `run()` at lines 409-427)
- Create: `tests/test_decision_e2e.py`

- [ ] **Step 1: Write failing tests** in `tests/test_decision_e2e.py`:
  - `test_run_on_sample_fixture_has_no_decision_finding` — `lint.run(lint.scan(FIXTURE)[0], [])` contains no `DECISION` code.
  - `test_fresh_wiki_decision_lifecycle` — `init.py <tmp>/wiki --wiki-title T --non-interactive` (subprocess, isolated git, **relative** target via `cwd=tmp`); assert `scripts/decision_lint.py` exists in the wiki. Write a card, a knowledge page linking both decisions, an old page (`superseded`) and a new page (`decided`, `supersedes`), topic lines and both `## Decisions` lines; run the **vendored** `python3 scripts/lint.py` (cwd = wiki): rc 0, no `DECISION`. Delete `## Consequences` from the new page: rc 1, the `missing required section '## Consequences'` line. Restore it and point `supersedes` at `ghost`: rc 1, `supersedes names 'ghost', but wiki/ghost.md does not exist`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_decision_e2e -q` — the lifecycle test FAILS (no `DECISION` finding appears).
- [ ] **Step 3: Implement**: `import decision_lint  # noqa: E402` beside `import gap_lint`; in `run()`, after the `check_index_sync` loop: `findings += decision_lint.check_decisions(files, _wiki_pages(files), _strip_code, extract_links)`. Add `decision_lint.check_decisions` to the module docstring's list only if `lint.py`'s docstring lists checks (it does not today: leave it).
- [ ] **Step 4: Run** `./run_tests.sh` — all PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(lint): run the decision checks in lint.py"`.

### Task 5: Template text, recipes, README, and upgrade proof

**Files:**
- Modify: `templates/wiki.AGENTS.md`, `templates/AGENTS.root.md.tmpl`, `templates/recipes.md`, `templates/index.md.header.tmpl`, `README.md:129`
- Modify: `tests/test_templates.py:100-108` (the `PER_ORIGIN_TABLE` pin changes with the table, on purpose — spec §5.6)
- Modify: `tests/test_upgrade.py` (new test beside `test_apply_completes_and_updates_every_managed_template_path`)

- [ ] **Step 1: Write failing tests**:
  - `tests/test_templates.py`: `test_wiki_agents_defines_decision_pages` — `wiki.AGENTS.md` contains `kind: decision`, each of the four `## <section>` names, `## Decisions`, `supersedes`, `superseded_by`, `Importing an ADR`, `origin: adr`. `test_root_agents_names_decision_pages` — rendered `AGENTS.root.md.tmpl` mentions `## Decisions` in the Ingest and Query workflows. Update `PER_ORIGIN_TABLE` to the new `session` row and the new `adr` row.
  - `tests/test_upgrade.py`: `test_upgrade_brings_decision_lint_to_a_wiki_without_it` — v1.0.0 fixture library = `_make_library` then delete `scripts/decision_lint.py` and remove the two wiring lines from its `scripts/lint.py` (assert both strings are present before removing them, so a moved line fails loudly); init a wiki from it; v1.1.0 = this checkout's sources (`_make_library` at 1.1.0); upgrade `--apply`: rc 0, `scripts/decision_lint.py` exists in the wiki and is in the manifest as `managed`, `wiki/AGENTS.md` equals the template, vendored lint rc 0.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_templates tests.test_upgrade -q` — new tests FAIL.
- [ ] **Step 3: Write the template text** of spec §4.6, in the existing voice of each file. Generic `widget` example only. In `recipes.md`, refer to `wiki/AGENTS.md` in plain text, not a link.
- [ ] **Step 4: Run** `./run_tests.sh` — all PASS (including `tests/test_genericity.py`).
- [ ] **Step 5: Commit** `git commit -m "feat(wiki): document decision pages, the Decisions index and ADR import"`.

### Task 6: Evidence, spec, PR

- [ ] **Step 1: Cross-version check (spec §5.4).** Copy into scratch, outside any git repo: `tests/fixtures/sample-wiki`, a fresh `init.py` wiki without `.git`, and a copy of one real consumer wiki without `.git`. For each, run `$SCRATCH/v141/scripts/lint.py --root <tree>` and this branch's `scripts/lint.py --root <tree>`; `diff` the two outputs. Expected: empty diff for all three. Record the commands and the result in the PR body (generic tree names only).
- [ ] **Step 2: Neutrality.** grep `git diff main` and the two docs for every term that `tests/test_genericity.py` forbids → no output; run `tools/neutrality_review.sh` (advisory).
- [ ] **Step 3: Commit the spec and plan** `git add docs/specs/decision-records.spec.md docs/plans/decision-records.plan.md && git commit -m "docs(plan): spec and plan for decision pages (#51)"`.
- [ ] **Step 4: Push and open the PR** titled `feat(wiki): add decision pages with status and supersedes checks`, body per `~/.claude/rules/writing-voice.md` shape: Description (≤3 sentences), Design choices (≤3 bullets: opt-in by `kind: decision`; MINOR per policy §2 with the MANAGED/TEMPLATE/SEEDED reach; `.c3/` not updated because of #49), the evidence of Step 1, `Closes #51`.
