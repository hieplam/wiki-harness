from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THIS_FILE = Path(__file__).resolve()

# Anything naming OGP, Prospa, the OGP tribe, or content specific to
# ogp-wiki's real cards/pages (e.g. "pay run", "partner commissions") --
# found while porting T01's forked scripts/ and githooks/ files (T02).
OGP_SPECIFIC_TERMS = (
    "OGP",
    "Prospa",
    "pay run",
    "pay-run",
    "partner commissions",
    "partner-commissions",
)

# Globs the OGP-corpus sweep covers. T02 scoped this to scripts/,
# githooks/ only (templates/ didn't exist yet); T12 extends it to
# "templates/**/*" now that templates/ exists, without rewriting any test
# already in this module -- both test_genericity_zero_ogp_strings and
# test_genericity_extended_to_templates below share this one tuple.
GENERICITY_GLOBS = ("scripts/**/*.py", "githooks/*", "templates/**/*")


def _library_files():
    """The library's own forked-from-ogp-wiki files: scripts/ and
    githooks/. Impure edge -- walks the real filesystem so the pure
    genericity check below can run against plain strings."""
    seen = set()
    for pattern in GENERICITY_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def find_ogp_strings(files):
    """(path, text) pairs in -> (relative path, offending term) pairs out.
    Pure: no filesystem access, just string search."""
    hits = []
    for path, text in files:
        lower = text.lower()
        for term in OGP_SPECIFIC_TERMS:
            if term.lower() in lower:
                hits.append((path, term))
    return hits


class GenericityGrep(unittest.TestCase):
    """scripts/ and githooks/ are the library's own code, forked verbatim
    from ogp-wiki by T01 -- nothing OGP/Prospa-specific may survive in
    them, or every downstream wiki that installs this library inherits
    ogp-wiki's private vocabulary."""

    def test_genericity_zero_ogp_strings(self):
        files = [(p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))
                  for p in _library_files()]
        self.assertEqual(find_ogp_strings(files), [])

    def test_genericity_extended_to_templates(self):
        """T12: extends the same OGP-corpus sweep to templates/ (now that
        it exists), including the two CLAUDE.*.tmpl files -- via
        GENERICITY_GLOBS above rather than a second, separate grep."""
        template_paths = [p for p in _library_files()
                          if p.relative_to(ROOT).parts[0] == "templates"]
        self.assertTrue(template_paths, "expected templates/ files to be swept")
        names = {p.name for p in template_paths}
        self.assertIn("CLAUDE.root.tmpl", names)
        self.assertIn("CLAUDE.nested.tmpl", names)
        files = [(p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))
                  for p in template_paths]
        self.assertEqual(find_ogp_strings(files), [])


class SyntheticFixtureNotOgpCorpus(unittest.TestCase):
    """The library's own test suite must be self-contained: every test
    runs entirely against tests/fixtures/sample-wiki/, never a real,
    on-disk ogp-wiki path."""

    # The exact shapes T01's fork used to read a real, top-level
    # sources/cards/card-schema.json at import/call time.
    DANGEROUS_PATTERNS = (
        "ROOT / SCHEMA_PATH",
        'parent.parent / "sources/cards/card-schema.json"',
        "parent.parent / SCHEMA_PATH",
    )

    def test_lint_suite_uses_synthetic_fixture_not_ogp_corpus(self):
        offenders = []
        for path in sorted((ROOT / "tests").glob("*.py")):
            if path.resolve() == THIS_FILE:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in text:
                    offenders.append((path.name, pattern))
            if "card-schema.json" in text or "SCHEMA_PATH" in text:
                self.assertTrue(
                    "fixtures" in text and "sample-wiki" in text,
                    f"{path.name} reads a card schema but does not source "
                    "it from tests/fixtures/sample-wiki/")
        self.assertEqual(offenders, [])


class FullSuiteDiscovery(unittest.TestCase):
    """T01's own acceptance deliberately did not require `unittest
    discover` to pass (its 3 forked-verbatim test files crashed on
    import/call against a real, on-disk ogp-wiki path that doesn't exist
    in this library). T02 is where it first must -- this is the literal
    test that was red immediately after T01."""

    # Guards against the subprocess below re-discovering (and re-running)
    # this very test, which would otherwise spawn a subprocess per level
    # forever. Only the outer, real invocation performs the check; a
    # nested invocation (this same test running inside the subprocess it
    # spawned) is a no-op by design, not a coverage gap.
    _GUARD_ENV = "WIKI_HARNESS_FULL_SUITE_SELFTEST_GUARD"

    def test_full_suite_discovers_and_imports_cleanly(self):
        if os.environ.get(self._GUARD_ENV):
            self.skipTest("nested invocation from the parent discover run "
                           "this test itself spawned")
        env = dict(os.environ)
        env[self._GUARD_ENV] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
            cwd=str(ROOT), capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
