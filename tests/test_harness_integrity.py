"""Tests for lint.py's HARNESS finding: the eighth impure edge
(read_harness_manifest(root)) plus its pure judgment (check_harness()),
mirroring the existing hooks_finding(root)/check_raw_immutability() split.

Every test builds a real, throwaway temp-directory wiki tree and a real
.wiki-harness-manifest.json (via manifest.py's own compute_manifest/
write_manifest -- never a hand-rolled dict, so these tests exercise the
exact same manifest shape upgrade.py/init.py will actually produce) rather
than hand-building a ManifestState, so read_harness_manifest()'s own
Path.read_bytes() disk reads are exercised, not just check_harness()'s
pure judgment.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from manifest import compute_manifest, hash_bytes, write_manifest  # noqa: E402
from lint import (MANIFEST_FILENAME, check_harness, read_harness_manifest,  # noqa: E402
                  run, scan)

MANAGED_CONTENT = b"scripts/lint.py contents\n"
TEMPLATE_CONTENT = b"AGENTS.md contents\n"

# A fully lint-clean tree (two cross-linking wiki pages, so neither is an
# ORPHAN) -- the narrow-blast-radius test proves every non-HARNESS check
# still finds nothing wrong on this exact fixture even when the manifest
# is entirely absent.
FIXTURE = ROOT / "tests" / "fixtures" / "sample-wiki"
CLEAN_WIKI_FILES = {
    "index.md": "- [Widget assembly](./wiki/widget-assembly.md)\n"
                "- [Quality checks](./wiki/quality-checks.md)\n",
    "wiki/widget-assembly.md":
        "---\ntitle: Widget assembly\ntopics: [widget-assembly]\n---\n"
        "The weekly batch. Details in\n"
        "[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).\n"
        "See also [quality checks](./quality-checks.md).\n",
    "wiki/quality-checks.md":
        "---\ntitle: Quality checks\ntopics: [widget-assembly]\n---\n"
        "Run after the [widget assembly](./widget-assembly.md), per\n"
        "[src-2024-01-15-001](../sources/cards/src-2024-01-15-001.md).\n",
    "sources/cards/src-2024-01-15-001.md":
        "---\nid: src-2024-01-15-001\ndate: 2024-01-15\norigin: session\n"
        "trust: stated\ntopics: [widget-assembly]\n---\n## Claims\n- a claim\n",
    "sources/cards/card-schema.json":
        (FIXTURE / "sources/cards/card-schema.json").read_text(encoding="utf-8"),
}


def _write_tree(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _write_manifest(root, entries, harness_version="1.2.3"):
    """entries: {path: (role, bytes)}. Writes each path's bytes to disk and
    a real .wiki-harness-manifest.json (via manifest.py's own
    compute_manifest/write_manifest) recording the given role and
    caller-supplied recorded sha256 for each -- callers pass a
    deliberately mismatched recorded hash to simulate drift."""
    hashes = {}
    for path, (role, recorded_sha256) in entries.items():
        hashes[path] = {"role": role, "sha256": recorded_sha256}
    manifest = compute_manifest(
        hashes, {}, "git@example.com:hieplam/wiki-harness.git",
        harness_version=harness_version, source_ref=f"v{harness_version}",
        source_commit="0" * 40, initialised_at="2026-08-26")
    write_manifest(root / MANIFEST_FILENAME, manifest)


class HarnessCleanManifestZeroFindings(unittest.TestCase):
    def test_harness_clean_manifest_zero_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts/lint.py").write_bytes(MANAGED_CONTENT)
            (root / "AGENTS.md").write_bytes(TEMPLATE_CONTENT)
            _write_manifest(root, {
                "scripts/lint.py": ("managed", hash_bytes(MANAGED_CONTENT)),
                "AGENTS.md": ("template", hash_bytes(TEMPLATE_CONTENT)),
            })

            self.assertEqual(check_harness(read_harness_manifest(root)), [])


class HarnessHandEditedManagedFile(unittest.TestCase):
    def test_harness_hand_edited_managed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            recorded_hash = hash_bytes(MANAGED_CONTENT)
            # On-disk bytes differ from the manifest's recorded hash --
            # a hand edit the manifest was never updated to reflect.
            edited_content = b"scripts/lint.py HAND-EDITED contents\n"
            (root / "scripts/lint.py").write_bytes(edited_content)
            _write_manifest(root, {
                "scripts/lint.py": ("managed", recorded_hash),
            })
            found_hash = hash_bytes(edited_content)

            findings = check_harness(read_harness_manifest(root))

            self.assertEqual(len(findings), 1)
            f = findings[0]
            self.assertEqual((f.severity, f.code, f.path),
                             ("ERROR", "HARNESS", "scripts/lint.py"))
            self.assertEqual(
                f.message,
                "local edit conflicts with library-managed content "
                f"(expected sha256 {recorded_hash}, found sha256 {found_hash}) "
                "— this file is harness-owned; run 'upgrade --adopt-drift "
                "scripts/lint.py' if this is intentional, or 'git checkout -- "
                "scripts/lint.py' to discard it.")


class HarnessMissingManagedFile(unittest.TestCase):
    def test_harness_missing_managed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # scripts/lint.py is listed in the manifest but never written
            # to disk at all.
            _write_manifest(root, {
                "scripts/lint.py": ("managed", hash_bytes(MANAGED_CONTENT)),
            })

            findings = check_harness(read_harness_manifest(root))

            self.assertEqual(findings, [
                ("ERROR", "HARNESS", "scripts/lint.py",
                 "managed file missing — harness is incomplete; "
                 "re-run upgrade or re-init."),
            ], [tuple(f) for f in findings])


class HarnessMissingManifestNarrowBlastRadius(unittest.TestCase):
    def test_harness_missing_manifest_narrow_blast_radius(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            # Deliberately no .wiki-harness-manifest.json written at all.

            files, enc = scan(root)
            self.assertEqual(enc, [])
            other_findings = run(files, [])
            harness_findings = check_harness(read_harness_manifest(root))

            # Every other check still runs normally on the same fixture --
            # zero unrelated findings on this clean tree.
            self.assertEqual(other_findings, [])
            self.assertEqual(harness_findings, [
                ("ERROR", "HARNESS", MANIFEST_FILENAME,
                 "manifest missing — this wiki was not initialised with "
                 "wiki-harness, or the manifest was deleted; run 'upgrade "
                 "--adopt' to generate one."),
            ], [tuple(f) for f in harness_findings])


class HarnessInstanceForkWarn(unittest.TestCase):
    def test_harness_instance_fork_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pre_fork_content = b"wiki/AGENTS.md pre-fork contents\n"
            forked_content = b"wiki/AGENTS.md forked, locally-edited contents\n"
            (root / "wiki").mkdir()
            (root / "wiki/AGENTS.md").write_bytes(forked_content)
            _write_manifest(root, {
                "wiki/AGENTS.md": ("instance-fork", hash_bytes(pre_fork_content)),
            }, harness_version="1.4.0")

            findings = check_harness(read_harness_manifest(root))

            self.assertEqual(findings, [
                ("WARN", "HARNESS", "wiki/AGENTS.md",
                 "forked from wiki-harness at v1.4.0; local edits are "
                 "permanent and will not receive future updates."),
            ], [tuple(f) for f in findings])


if __name__ == "__main__":
    unittest.main()
