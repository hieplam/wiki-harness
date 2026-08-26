"""Tests for manifest.py: the pure compute_manifest/diff_manifest pair, the
role validation logic (including the reserved-but-unused "removed" value),
and the thin read/write I/O edge for .wiki-harness-manifest.json.

compute_manifest/diff_manifest never touch a filesystem or clock themselves
(rule-pure-core-impure-edge) -- every test below hands them plain dicts and
asserts on the dicts/lists they return, except the round-trip test, which
exercises the named I/O edge functions explicitly.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from manifest import (Drift, VALID_ROLES, compute_manifest, diff_manifest,
                      hash_bytes, is_valid_role, read_manifest, write_manifest)

VARS = {"wiki_title": "OGP Wiki", "org_name": "OGP tribe",
        "content_language": "English", "repo_name": "ogp-wiki"}


def make_manifest(hashes, source_url="git@github.com:hieplam/wiki-harness.git"):
    return compute_manifest(
        hashes, VARS, source_url,
        harness_version="1.0.0", source_ref="v1.0.0",
        source_commit="3f9c2a1" + "0" * 33,
        initialised_at="2026-08-25")


class ComputeManifestIsDeterministic(unittest.TestCase):
    def test_compute_manifest_is_deterministic(self):
        hashes = {
            "scripts/lint.py": {"role": "managed", "sha256": hash_bytes(b"lint")},
            "AGENTS.md": {"role": "template", "sha256": hash_bytes(b"agents")},
        }
        m1 = make_manifest(hashes)
        m2 = make_manifest(hashes)
        self.assertEqual(json.dumps(m1, sort_keys=True),
                          json.dumps(m2, sort_keys=True))
        self.assertEqual(m1, m2)


class MutatedByteDetected(unittest.TestCase):
    def test_mutated_byte_detected(self):
        original = hash_bytes(b"scripts/lint.py contents\n")
        mutated = hash_bytes(b"scripts/lint.py Contents\n")  # one byte flipped
        self.assertNotEqual(original, mutated)

        recorded = make_manifest(
            {"scripts/lint.py": {"role": "managed", "sha256": original}})["files"]
        actual = {"scripts/lint.py": mutated}

        drifts = diff_manifest(recorded, actual)
        self.assertEqual(drifts, [Drift("scripts/lint.py", "hash_mismatch")])


class MissingVsDriftedDistinguished(unittest.TestCase):
    def test_missing_vs_drifted_distinguished(self):
        drifted_hash = hash_bytes(b"on-disk drifted bytes")
        recorded = make_manifest({
            "scripts/lint.py": {"role": "managed",
                                "sha256": hash_bytes(b"recorded bytes")},
            "AGENTS.md": {"role": "template",
                         "sha256": hash_bytes(b"agents bytes")},
        })["files"]
        # scripts/lint.py is present on disk but with a different hash;
        # AGENTS.md is recorded but absent from disk entirely.
        actual = {"scripts/lint.py": drifted_hash}

        drifts = {d.path: d.status for d in diff_manifest(recorded, actual)}
        self.assertEqual(drifts["scripts/lint.py"], "hash_mismatch")
        self.assertEqual(drifts["AGENTS.md"], "missing")
        self.assertNotEqual(drifts["scripts/lint.py"], drifts["AGENTS.md"])


class SourceUrlRoundTrips(unittest.TestCase):
    def test_source_url_round_trips(self):
        import tempfile
        url = "git@github.com:hieplam/wiki-harness.git"
        manifest = make_manifest(
            {"scripts/lint.py": {"role": "managed", "sha256": hash_bytes(b"x")}},
            source_url=url)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".wiki-harness-manifest.json"
            write_manifest(path, manifest)
            loaded = read_manifest(path)
        self.assertEqual(loaded["source_url"], url)
        self.assertEqual(loaded, manifest)


class RoleRemovedIsAValidEnumValue(unittest.TestCase):
    def test_role_removed_is_a_valid_enum_value(self):
        self.assertIn("removed", VALID_ROLES)
        self.assertTrue(is_valid_role("removed"))
        # still unused by compute_manifest's own callers in this task, but
        # accepted, not rejected, when a caller does supply it.
        m = make_manifest(
            {"sources/AGENTS.md": {"role": "removed", "sha256": hash_bytes(b"x")}})
        self.assertEqual(m["files"]["sources/AGENTS.md"]["role"], "removed")

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            make_manifest(
                {"x": {"role": "bogus-role", "sha256": hash_bytes(b"x")}})


if __name__ == "__main__":
    unittest.main()
