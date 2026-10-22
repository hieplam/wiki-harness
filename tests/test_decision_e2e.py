from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_PY = ROOT / "init.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"

sys.path.insert(0, str(ROOT / "scripts"))
import lint  # noqa: E402

CARD = """---
id: src-2024-03-01-001
date: 2024-03-01
origin: session
trust: stated
topics: [widgets]
---
## Claims
- Widgets ship in batches of ten, because single shipments cost too much.
"""

KNOWLEDGE = """---
title: Widget shipping
topics: [widgets]
---
Widgets ship in batches of ten
[src-2024-03-01-001](../sources/cards/src-2024-03-01-001.md). The rule and its
history: [batches of ten](./widgets-ship-in-batches.md),
[the old rule](./widgets-ship-singly.md).
"""

NEW = """---
title: Widgets ship in batches of ten
topics: [widgets]
kind: decision
status: decided
decided: 2024-03-01
supersedes: {supersedes}
---
Widgets ship in batches of ten
[src-2024-03-01-001](../sources/cards/src-2024-03-01-001.md). See
[widget shipping](./widget-shipping.md).

## Context
Single shipments cost too much.

## Decision
Ship in batches of ten.

## Rejected options
Batches of a hundred: too slow to fill.
{consequences}"""

CONSEQUENCES = """
## Consequences
A single urgent widget waits for its batch.
"""

OLD = """---
title: Widgets ship singly
topics: [widgets]
kind: decision
status: superseded
decided: 2023-11-02
superseded_by: widgets-ship-in-batches
---
Replaced by [batches of ten](./widgets-ship-in-batches.md).

## Context
Every order was urgent.

## Decision
Ship each widget alone.

## Rejected options
None considered.

## Consequences
High shipping cost.
"""

INDEX_LINES = """
## widgets

- [Widget shipping](./wiki/widget-shipping.md) — how widgets ship
- [Widgets ship in batches of ten](./wiki/widgets-ship-in-batches.md) — the batch size
- [Widgets ship singly](./wiki/widgets-ship-singly.md) — the old rule

## Decisions

- [Widgets ship in batches of ten](./wiki/widgets-ship-in-batches.md) — decided 2024-03-01
- [Widgets ship singly](./wiki/widgets-ship-singly.md) — superseded by [batches of ten](./wiki/widgets-ship-in-batches.md)
"""


def _isolated_env():
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class ExistingContent(unittest.TestCase):
    def test_run_on_sample_fixture_has_no_decision_finding(self):
        files, _ = lint.scan(FIXTURE)
        codes = {f.code for f in lint.run(files, [])}
        self.assertNotIn("DECISION", codes)


class FreshWikiLifecycle(unittest.TestCase):
    """init a wiki the way a person types it (a relative target), write a
    decision and the decision it replaced, and run the lint.py that init
    vendored into the wiki -- not this checkout's copy."""

    def _lint(self, wiki):
        return subprocess.run([sys.executable, "scripts/lint.py"], cwd=wiki,
                              capture_output=True, text=True, env=_isolated_env(),
                              timeout=120)

    def _write(self, wiki, supersedes="widgets-ship-singly",
               consequences=CONSEQUENCES):
        (wiki / "sources" / "cards" / "src-2024-03-01-001.md").write_text(
            CARD, encoding="utf-8")
        (wiki / "wiki" / "widget-shipping.md").write_text(KNOWLEDGE, encoding="utf-8")
        (wiki / "wiki" / "widgets-ship-in-batches.md").write_text(
            NEW.format(supersedes=supersedes, consequences=consequences),
            encoding="utf-8")
        (wiki / "wiki" / "widgets-ship-singly.md").write_text(OLD, encoding="utf-8")

    def test_fresh_wiki_decision_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            init = subprocess.run(
                [sys.executable, str(INIT_PY), "wiki", "--wiki-title", "Widgets",
                 "--non-interactive"],
                cwd=tmp, capture_output=True, text=True, env=_isolated_env(),
                timeout=120)
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
            wiki = Path(tmp) / "wiki"
            self.assertTrue((wiki / "scripts" / "decision_lint.py").is_file())
            index = wiki / "index.md"
            index.write_text(index.read_text(encoding="utf-8") + INDEX_LINES,
                             encoding="utf-8")

            self._write(wiki)
            clean = self._lint(wiki)
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            self.assertNotIn("DECISION", clean.stdout)

            self._write(wiki, consequences="")
            no_section = self._lint(wiki)
            self.assertEqual(no_section.returncode, 1, no_section.stdout)
            self.assertIn(
                "ERROR DECISION wiki/widgets-ship-in-batches.md: "
                "missing required section '## Consequences'", no_section.stdout)

            self._write(wiki, supersedes="ghost")
            dangling = self._lint(wiki)
            self.assertEqual(dangling.returncode, 1, dangling.stdout)
            self.assertIn(
                "ERROR DECISION wiki/widgets-ship-in-batches.md: "
                "supersedes names 'ghost', but wiki/ghost.md does not exist",
                dangling.stdout)


if __name__ == "__main__":
    unittest.main()
