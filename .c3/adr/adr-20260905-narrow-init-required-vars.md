---
id: adr-20260905-narrow-init-required-vars
c3-seal: 97aee6c4c087ec92d12aa5b651b2850c74a037a36719f624aaf63527505a336f
title: narrow-init-required-vars
type: adr
goal: |-
    Narrow `init.py`'s required-variable set to `--wiki-title` alone, deriving `org_name`,
    `content_language`, and `repo_name` when the caller leaves them empty, and record that
    narrowing in the `init` component's Contract so the fact stops describing a four-required-flag
    CLI that no longer exists. The same derivation applies to `upgrade.py --adopt`, which shares
    init's collection path.
status: accepted
date: "2026-09-05"
---

## Goal

Narrow `init.py`'s required-variable set to `--wiki-title` alone, deriving `org_name`,
`content_language`, and `repo_name` when the caller leaves them empty, and record that
narrowing in the `init` component's Contract so the fact stops describing a four-required-flag
CLI that no longer exists. The same derivation applies to `upgrade.py --adopt`, which shares
init's collection path.

## Context

`init.py` shipped requiring all four template variables. In `--non-interactive` mode — the
mode a person is told to copy-paste, and the only mode an agent can drive — omitting any of
them exited 2 with `missing required value(s) for --non-interactive mode`. The minimal working
command was therefore six flags long, and three of the four values were mechanically derivable:
`repo_name` is the target directory's own basename, `content_language` is `English` for every
wiki the harness has produced, and `org_name` had no derivation only because the templates
phrased it possessively.

The owner reported the flag count as the primary barrier to using the tool, alongside the
absence of any human- or agent-facing entry documentation (addressed in the same PR by a root
`README.md`, `AGENTS.md`, and a `CLAUDE.md` pointer — none of which are modeled facts, so they
carry no patch here).

Two constraints shaped the decision. First, `docs/compatibility-policy.md` §2 pinned the CLI
surface of `init.py` and `upgrade.py` jointly: no existing flag's default or exit code may
change outside a MAJOR. Second, `c3-210`'s Derived Materials row names plan-v3.md §3.1 as the
verbatim oracle for init's messages and step order — a contract written during the extraction,
when byte-identical behaviour against `ogp-wiki` was the whole premise.

## Decision

Add a pure `apply_defaults(values, target_name)` to `init.py` that fills only the variables the
caller left empty: `repo_name` from the target's resolved basename, `content_language` from
`English`, `org_name` from `wiki_title`. `REQUIRED_VARS` narrows to `("wiki_title",)`;
`TEMPLATE_VARS` keeps the full four for the answers-file and merge paths, which must still
accept and validate all of them. The basename is resolved at the edge (`main()`) and passed in,
because `.` has an empty basename and a trailing slash keeps one only after normalisation —
the pure function must not touch the filesystem to learn either.

Interactively, `--wiki-title` keeps re-prompting until answered; each derived variable is
offered as `Label [default]:` and an empty answer takes it. `upgrade.py`'s `run_adopt()` calls
the same `apply_defaults()` after its existing missing-var check, so adopt and init reach
identical `vars` for identical flags.

Release this as MINOR (v1.2.0) and amend `docs/compatibility-policy.md` §2 rather than cutting
a MAJOR: split the joint CLI row so `upgrade.py`'s surface stays pinned as hard as the finding
codes, while `init.py`'s MINOR column permits a required variable to become derived. The new
§2.1 carries the argument — `init.py` runs once, at first adoption, against a target with no
manifest, so no installed consumer's behaviour can change; a MAJOR would warn every consumer
that an upgrade is risky when `upgrade.py` was not touched at all. The reverse move — a derived
variable becoming required again, a flag removed or repurposed — stays a §3 removal.

Two template files are reworded in the same change because the derivation makes their existing
phrasing wrong: `$org_name's knowledge source of truth` reads as a duplication when `org_name`
defaults to `wiki_title`. Both become `the knowledge source of truth for $org_name`. There is
no conditional rendering in `string.Template`, so the text must read correctly for every value.

## Affected Topology

| Entity | Type | Why affected | Evidence | Governance review |
| --- | --- | --- | --- | --- |
| c3-210 | component | Owns init.py. Its Contract row quotes the CLI surface with all four variable flags undifferentiated, its Purpose says step 2 collects "the 4 template variables", and its Derived Materials row names plan-v3.md §3.1 as a verbatim oracle that this change deliberately departs from | c3-210#n362@v1:sha256:add09a21150d90f87f38e6b09ca047d8612c2cbe5fb8ee46d63ed4bf6a3ec883 "python3 wiki-harness/init.py <target-dir> [--wiki-title ...] [--org-name ...] [--content-language ...] [--repo-name ...] [--origins a,b,c] [--non-interactive] [" | Contract, Purpose, and Derived Materials rows re-authored in this unit |
| c3-211 | component | run_adopt() gains the same apply_defaults() call, but the fact's Contract surface documents only --adopt-drift and never enumerated adopt's variable flags, so no cell it states becomes false | c3-211#n371@v1:sha256:d5fad8f079f65d5d320ffdad1df8cc079eac795bbad727248fa4856e795b94ff "Bring an existing wiki instance forward to a newer (or, with --allow-downgrade, older) harness" | Reviewed, no patch — nothing in the fact names the required-variable set |
| c3-301 | component | Holds the two TEMPLATE-class .tmpl sources whose wording changed. The fact governs which files are var-substituted, not their prose | c3-301#n411@v1:sha256:bad70989a99b798f082cf9f728985a743d9618a2b30b2c292221625fed61a728 "Hold the two var-substituted (TEMPLATE-class) source files a wiki instance's root gets rendered" | Reviewed, no patch — the TEMPLATE class membership and variable set are unchanged |

## Compliance Rules

| Rule | Why required | Evidence | Action |
| --- | --- | --- | --- |
| rule-pure-core-impure-edge | The derivation is a decision over collected data and must be pure; the basename resolution and the prompt are filesystem/stdin edges that feed it | rule-pure-core-impure-edge#n589@v1:sha256:399ea3761ff0b0ef1c3475a7de6d93821e7e2fc98da7cc08bd1f048789ce8d08 "Keep every non-trivial computation across the library — the lint checks, the manifest diff, the" | Comply — apply_defaults() is pure and takes target_name as an argument; main() resolves the path, _ask() owns the prompt |
| rule-stdlib-only-py39 | New code in init.py and upgrade.py | rule-stdlib-only-py39#n606@v1:sha256:73c38cb86710504178722cecdfa01ab2c6b88aad384a6c516bc3edb8a1342c16 "Guarantee every wiki-harness Python module runs on the oldest interpreter a consuming wiki might" | Comply — no new imports of any kind |

## Work Breakdown

| Area | Detail | Evidence |
| --- | --- | --- |
| init.py | TEMPLATE_VARS/REQUIRED_VARS/DEFAULTED_VARS split, DEFAULT_CONTENT_LANGUAGE, pure apply_defaults(), target_name threaded through collect_vars(), main() resolves the basename and applies the derivation after the missing-var check | init.py |
| init.py | _ask() edge converts EOFError into a typed NoInputError refusal (exit 2) — an unhandled traceback on closed stdin, present since v1.0.0, was reachable the moment a non-tty caller omitted a flag that now prompts | init.py, tests/test_init.py::PromptWithNoInputRefusesCleanly |
| upgrade.py | run_adopt() applies the same derivation after its missing-var check | upgrade.py |
| templates | README.md.tmpl and AGENTS.root.md.tmpl reworded off the possessive $org_name's | templates/*.tmpl |
| docs | docs/compatibility-policy.md §2 CLI row split + new §2.1; CHANGELOG.md v1.2.0 entry with its Compatibility field; VERSION → 1.2.0 | docs/compatibility-policy.md, CHANGELOG.md |
| docs | Root README.md (human quickstart), AGENTS.md (agent working manual), CLAUDE.md (@AGENTS.md) — library-repo documentation, no modeled fact | README.md, AGENTS.md, CLAUDE.md |

## Enforcement Surfaces

| Surface | Behavior | Evidence |
| --- | --- | --- |
| tests/test_init.py::DefaultedVarsPureCore | Pins the derivation itself: each default, and that a supplied value is never overridden | 3 tests |
| tests/test_init.py::DefaultedVarsTargetShapes | Drives main() with every target spelling a person types — absolute, relative, trailing slash, . — because repo_name now depends on the basename and Path('.').name is empty | 4 tests |
| tests/test_init.py::MinimalNonInteractiveInvocation | Runs the one-flag command as a real subprocess and asserts a lint-clean scaffold with the derived values rendered into AGENTS.md | 1 test |
| tests/test_init.py::InteractivePromptsOfferTheDefault | Pins that the prompt shows [default], that an empty answer takes it, and that --wiki-title re-prompts | 2 tests |
| tests/test_init.py::PromptWithNoInputRefusesCleanly | Pins exit 2 and no traceback when stdin is closed | 2 tests |
| tests/test_upgrade.py::TestAdopt | --wiki-title alone drives adopt and lands the derived values in the manifest; omitting it still refuses before any write | 2 tests |

## Alternatives Considered

| Alternative | Rejected because |
| --- | --- |
| Cut v2.0.0 and leave the policy as written | upgrade.py is untouched, so a MAJOR would tell every consumer their upgrade is risky about the one program that did not change — the version number would carry a false warning |
| Keep the exit-2 refusal under --non-interactive and default only the interactive prompts | Fully MINOR-safe with no policy edit, but leaves the reported problem exactly in place: the copy-pasteable non-interactive command still needs four flags |
| Default org_name from the host's global git user.name | init sets GIT_CONFIG_GLOBAL/GIT_CONFIG_SYSTEM to os.devnull precisely so a host cannot change its output; reading the host identity would punch a hole in that guarantee for one cosmetic string |
| Leave the templates' possessive phrasing alone | Immigration Wiki's knowledge source of truth — Immigration Wiki renders in every wiki that takes the org_name default, into a TEMPLATE-class file a consumer cannot hand-fix without registering drift |

## Risks

| Risk | Mitigation | Verification |
| --- | --- | --- |
| A consumer script depends on the exit-2 refusal for a now-derived flag | Named explicitly in the CHANGELOG's Compatibility field, with the instruction to pass the values explicitly; --wiki-title still refuses | CHANGELOG.md v1.2.0 Compatibility |
| The two reworded TEMPLATE files rewrite a consumer's AGENTS.md/README.md on their next upgrade | TEMPLATE class already re-renders on every upgrade; upgrade --check shows the diff before any write, and the CHANGELOG states it | CHANGELOG.md v1.2.0 Compatibility |
| repo_name derives from a basename, so an odd target spelling produces an odd name | Four target shapes are tested through main(), including the two (., trailing slash) where a naive basename is wrong | tests/test_init.py::DefaultedVarsTargetShapes |

## Verification

| Check | Result |
| --- | --- |
| ./run_tests.sh | 298 tests, OK (was 295 before this change; 11 added, 1 rewritten to the new intent) |
| cd /tmp && python3 ~/repo/wiki-harness/init.py im-check --wiki-title 'Immigration Wiki' --non-interactive | exit 0, lint: 0 error(s), 0 warning(s), scaffold committed |
| printf 'Immigration Wiki\n\n\n\n' | python3 init.py im3 | Prompts read Organisation name [Immigration Wiki]:, Content language [English]:, Repository name [im3]:; empty answers accepted; exit 0 |
| python3 init.py im2 --wiki-title 'Immigration Wiki' </dev/null | exit 2, one-line refusal naming --non-interactive, no traceback |
| C3X_MODE=agent c3x check | passes after change apply |
