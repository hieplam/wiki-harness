# wiki-harness

**A wiki your AI agent maintains, and a linter that keeps it honest.**

You point an agent at a source — a chat session, a policy PDF, a Jira ticket — and it files
what the source *claims* into a card, then writes the knowledge into wiki pages that cite
those cards. `wiki-harness` is the machinery that makes that repeatable: the lint, the git
hooks, the file layout, the agent instructions, and a versioned upgrade path so a wiki set up
today can pull next year's fixes without hand-merging anything.

You install one small command; it fetches the release it needs and copies the harness into
your wiki, recording every file it owns so later upgrades can tell your edits from its own.

---

## Quickstart — create a wiki

```bash
curl -fsSL https://raw.githubusercontent.com/hieplam/wiki-harness/main/install.sh | sh
```

That puts `wiki-harness` in `~/.local/bin`. Then, from anywhere:

```bash
wiki-harness init my-wiki --wiki-title 'My Wiki'
```

One flag. The command creates the directory, wires the git hooks, runs its own
linter against what it just wrote, and makes the first commit:

```
lint: 0 error(s), 0 warning(s)

Scaffolded my-wiki -- lint clean, .githooks wired, first commit a1b2c3d4e5f6.
Next: start ingesting -- see AGENTS.md's Workflow: Ingest.
```

Then set your own git identity — `init` stamps the scaffold commit with a placeholder
author and deliberately ignores your global git config, so runs are reproducible:

```bash
cd my-wiki
git config user.name  "Your Name"
git config user.email "you@example.com"
```

Now open the generated `AGENTS.md` and tell your agent to start ingesting.

### How the command finds a release

`wiki-harness` is a small launcher. It downloads the release it needs from GitHub,
verifies the checksum published beside it, caches it under
`~/.cache/wiki-harness/releases/<version>/`, and hands over to that release's own
`init.py` / `upgrade.py`.

| Command | Release it runs |
|---|---|
| `wiki-harness init …` | the newest published release |
| `wiki-harness upgrade … --to 1.3.0` | exactly `1.3.0` — naming a version is the point |
| `wiki-harness upgrade … --check` | the newest, since it names none |
| any command with `--harness-version X` | `X` |

A release already in the cache is reused with no network call at all. To update the
launcher itself, run `wiki-harness self-update` (it re-runs the installer).

```bash
wiki-harness versions     # what is cached, and what is newest
wiki-harness --version    # launcher version and cached releases
```

### The flags

Only `--wiki-title` is required. Everything else has a default you can change later.

| Flag | Default | What it does |
|---|---|---|
| `--wiki-title` | **required** | The wiki's human name, e.g. `'my Wiki'` |
| `--org-name` | the wiki title | Who the wiki belongs to — a person, a team, a company |
| `--repo-name` | the target directory's name | The repo's own name |
| `--content-language` | `English` | The language pages are written in, whatever language you chat in |
| `--origins` | `session` | The allowed `origin:` values for cards — see [Cards](#cards-where-facts-come-from) |
| `--non-interactive` | off | Never prompt; take the flags and the defaults as given |
| `--answers-file` | — | A JSON file supplying the same values (individual flags win over it) |
| `--force` | off | Scaffold into a directory that is not empty (it never deletes anything) |

Run it with no flags beyond the title and it prompts, offering each default in
brackets — press Enter to accept:

```
$ wiki-harness init my-wiki
Wiki title: my Wiki
Organisation name [my Wiki]:
Content language [English]:
Repository name [my-wiki]:
```

`--non-interactive` is for scripts and agents: it turns the prompts off, so a missing
`--wiki-title` becomes a clean exit-2 refusal instead of a hang.

### Installing without the one-liner

Read [install.sh](./install.sh) first if you would rather not pipe a script to a
shell — it is short, writes only under `$HOME`, and never needs `sudo`. Or set where
it goes and which release it installs:

```bash
WIKI_HARNESS_BIN_DIR=~/bin WIKI_HARNESS_VERSION=1.2.1 sh install.sh
```

You can also skip the CLI entirely and run a clone directly; see
[Working on the harness itself](#working-on-the-harness-itself).

---

## What you get

```
Your-wiki/
├── AGENTS.md              ← the operating manual your agent reads first
├── CLAUDE.md              ← @AGENTS.md, so Claude Code reads the same file
├── README.md              ← your wiki's own readme
├── VISION.md              ← deferred work, one line per postponed decision
├── index.md               ← catalog of every page, grouped by topic
├── sources/
│   ├── raw/               ← original artifacts, write-once, never edited
│   └── cards/             ← one card per source: where it came from + its claims
│       ├── card-schema.json   ← THE definition of card frontmatter
│       └── recipes.md         ← what to extract, per kind of source
├── wiki/                  ← the knowledge pages themselves
├── scripts/               ← lint.py and friends, copied from this library
├── .githooks/             ← pre-commit + commit-msg, wired to core.hooksPath
└── .wiki-harness-manifest.json   ← which files the harness owns, and their hashes
```

Nothing here is a suggestion. `scripts/lint.py` runs on every commit through `.githooks/`,
and a wiki that violates its own rules cannot be committed.

---

## The model in three ideas

### Cards: where facts come from

Nothing goes on a wiki page unless a **card** says where it came from. A card is the envelope
for exactly one source:

```markdown
---
id: src-2026-09-05-001
date: 2026-09-05
origin: session
trust: stated
topics: [visa-timelines]
---
## Claims
- One atomic, filing-ready fact per bullet.

## Notes
Context that isn't a claim (optional).
```

`origin` is **what kind of source system** this came from; `trust` is **how much to believe
it**. They are independent axes, and both are closed enums the linter enforces.

- `trust` is fixed at `verified-in-code` / `stated` / `hearsay`. Contradictions resolve by
  higher trust first, then newer `date` — which is why `date` is when the source *asserted*
  the claim, not when you filed it.
- `origin` is yours to define. `--origins` seeds it at init time; after that it lives in
  `sources/cards/card-schema.json`, and you widen it by editing that file and committing with
  op `schema:`. A wiki about your might use
  `--origins 'official-doc,gov-form,caseworker,forum,session'`; a wiki about a codebase might
  use the shipped default, `session`.

Adding an origin later is safe. Removing one orphans every card already using it, so guess
wide — unused values cost nothing.

`card-schema.json` defines the **entire** card key set, not just origin, and the key set is
closed: an undeclared key is an `ERROR CARD_KEY` and the commit is blocked. That is deliberate
— it is what stops the documented schema and the enforced schema from drifting apart.

### Ownership: who may change what

Every path belongs to exactly one class, recorded in `.wiki-harness-manifest.json` with its
hash, so a hand-edit is detected as *drift* instead of being silently overwritten on upgrade.

| Class | Meaning | Examples |
|---|---|---|
| **MANAGED** | Copied byte-for-byte on every `init`/`upgrade`; hand-edits are drift | `scripts/*.py`, `.githooks/*`, the nested `AGENTS.md`/`CLAUDE.md` files |
| **TEMPLATE** | Rendered from a library template plus your variables; re-rendered on upgrade | root `AGENTS.md`, root `README.md` |
| **SEEDED** | Written once at setup, then 100% yours forever | `VISION.md`, `index.md`, `card-schema.json`, `recipes.md`, `.gitignore` |
| **INSTANCE** | The library never touches these, ever | everything under `sources/raw/`, `sources/cards/src-*.md`, `wiki/*.md` |

### Progressive disclosure: rules live next to what they govern

The root `AGENTS.md` is onboarding only. Format rules for a folder live in that folder's own
`AGENTS.md` — `sources/`, `sources/cards/`, `wiki/` — so an agent reads the rules for the
place it is about to write, and never infers a convention from surrounding files.

---

## Upgrading a wiki

Pull a newer harness release into an existing wiki:

```bash
wiki-harness upgrade ~/repo/my-wiki --check
wiki-harness upgrade ~/repo/my-wiki --to 1.3.0 --apply --commit
```

The launcher fetches the release you named and hands it its own payload as
`--library-path`, so nothing ever checks out a tag inside a clone you are using.

Upgrade refuses before writing anything if the tree is dirty or a MANAGED file has drifted; it
stages the whole change in a scratch copy, lints it there, and only then promotes it — with a
`git checkout -- .` rollback if promotion fails. `--adopt` brings a wiki that predates the
harness under management for the first time.

What may change between releases is governed by
[docs/compatibility-policy.md](./docs/compatibility-policy.md), and every release states its
type and its consumer impact in [CHANGELOG.md](./CHANGELOG.md).

---

## Working on the harness itself

```bash
./run_tests.sh          # the full suite: python3 -m unittest discover -s tests -q
```

Contributor and agent instructions are in [AGENTS.md](./AGENTS.md). Architecture facts live
in `.c3/` and are read through the C3 CLI, never by opening the files.

| Document | What it covers |
|---|---|
| [AGENTS.md](./AGENTS.md) | How to work in this repo — layout, rules, release process |
| [docs/compatibility-policy.md](./docs/compatibility-policy.md) | What may change across PATCH / MINOR / MAJOR |
| [docs/known-limitations.md](./docs/known-limitations.md) | What the harness deliberately does not do |
| [CHANGELOG.md](./CHANGELOG.md) | Every release, its type, and its compatibility notes |
| [docs/PLAN.md](./docs/PLAN.md) | The extraction campaign that produced this library |

Requires Python 3.9+ and git. No third-party dependencies, by rule.
