"""Golden test for lint.py's printed sort order: Finding is a namedtuple
(severity, code, path, message), and main() does
`for f in sorted(findings): print(...)`, so Python's default tuple sort
already orders "ERROR" before "WARN" lexicographically. No existing
fixture ever exercised a run producing BOTH severities at once -- this
file closes that gap by building a scenario with exactly one ERROR
finding and exactly one WARN finding, then capturing main()'s real
printed stdout (not just the in-memory findings list) and asserting the
ERROR line comes strictly before the WARN line.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"
LINT_PY = Path(__file__).resolve().parent.parent / "scripts" / "lint.py"

# A lint-clean cross-linked pair of pages (same shape as good_files() in
# test_lint_checks.py) plus one extra "lonely" page: listed in index.md so
# it doesn't trip INDEX, but linked-to by nobody (-> exactly one WARN
# ORPHAN) and containing exactly one link to a page that does not exist
# (-> exactly one ERROR LINK). Nothing else in the tree trips a finding.
FILES = {
    "index.md": "- [Widget assembly](./wiki/widget-assembly.md)\n"
                "- [Quality checks](./wiki/quality-checks.md)\n"
                "- [Lonely page](./wiki/lonely.md)\n",
    "wiki/widget-assembly.md":
        "---\ntitle: Widget assembly\ntopics: [widget-assembly]\n---\n"
        "The weekly batch. Details in\n"
        "[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).\n"
        "See also [quality checks](./quality-checks.md).\n",
    "wiki/quality-checks.md":
        "---\ntitle: Quality checks\ntopics: [widget-assembly]\n---\n"
        "Run after the [widget assembly](./widget-assembly.md), per\n"
        "[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).\n",
    "wiki/lonely.md":
        "---\ntitle: Lonely page\ntopics: [misc]\n---\n"
        "[ghost](./ghost.md)\n",
    "sources/cards/src-2024-01-15-001.md":
        "---\nid: src-2024-01-15-001\ndate: 2024-01-15\norigin: session\n"
        "trust: stated\ntopics: [widget-assembly]\n---\n## Claims\n- a claim\n",
    "sources/cards/card-schema.json":
        (FIXTURE / "sources/cards/card-schema.json").read_text(encoding="utf-8"),
}


class ErrorBeforeWarnPrintedOrder(unittest.TestCase):
    def test_error_before_warn_in_printed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, text in FILES.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(LINT_PY), "--root", str(root)],
                capture_output=True, text=True)

            lines = result.stdout.splitlines()
            error_lines = [i for i, l in enumerate(lines) if l.startswith("ERROR ")]
            warn_lines = [i for i, l in enumerate(lines) if l.startswith("WARN ")]

            # The fixture must produce exactly one finding of each severity
            # -- this is the scenario, not the contract under test.
            self.assertEqual(len(error_lines), 1, result.stdout)
            self.assertEqual(len(warn_lines), 1, result.stdout)
            self.assertIn("lint: 1 error(s), 1 warning(s)", result.stdout)

            # The contract under test: every ERROR line printed strictly
            # before every WARN line.
            self.assertLess(error_lines[0], warn_lines[0], result.stdout)


if __name__ == "__main__":
    unittest.main()
