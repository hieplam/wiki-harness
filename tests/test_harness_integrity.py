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

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from manifest import compute_manifest, hash_bytes, hash_tree, write_manifest  # noqa: E402
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


# Regression guards (Skinner finding, scripts/lint.py:334-342/196-227): a
# malformed or schema-incomplete .wiki-harness-manifest.json must degrade
# gracefully -- exactly one ERROR HARNESS finding, no uncaught traceback --
# like every other check in this file (check_card_citations' try/except
# around a bad regex, check_cards' graceful missing-schema handling), since
# lint.py is the mandatory pre-commit hook and a bare traceback there blocks
# every commit with zero diagnostic output.
class HarnessMalformedJsonManifestFailsClosed(unittest.TestCase):
    def test_harness_malformed_json_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            # A left-over merge-conflict marker / a write interrupted
            # mid-flight -- manifest.write_manifest() is a plain
            # non-atomic Path.write_text(), so a truncated file after a
            # crashed upgrade.py/init.py run is realistic. This is
            # syntactically invalid JSON.
            (root / MANIFEST_FILENAME).write_text(
                "<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> branch\n",
                encoding="utf-8")

            # The impure edge itself must fail closed instead of letting
            # json.JSONDecodeError propagate out of read_harness_manifest().
            findings = check_harness(read_harness_manifest(root))
            self.assertEqual(len(findings), 1)
            self.assertEqual(
                (findings[0].severity, findings[0].code, findings[0].path),
                ("ERROR", "HARNESS", MANIFEST_FILENAME))

            # End-to-end: the actual CLI (the mandatory pre-commit hook)
            # must not crash with a bare traceback and zero lint output.
            lint_py = ROOT / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertNotIn("Traceback", result.stderr, result.stderr)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("ERROR HARNESS", result.stdout)


class HarnessManifestMissingRoleKeyFailsClosed(unittest.TestCase):
    def test_harness_manifest_missing_role_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            (root / "scripts").mkdir()
            (root / "scripts/lint.py").write_bytes(MANAGED_CONTENT)
            # Syntactically valid JSON, but a hand-edited / partially
            # migrated manifest: this files entry has no 'role' key.
            manifest = compute_manifest(
                {}, {}, "git@example.com:hieplam/wiki-harness.git",
                harness_version="1.0.0", source_ref="v1.0.0",
                source_commit="0" * 40, initialised_at="2026-08-26")
            manifest["files"]["scripts/lint.py"] = {
                "sha256": hash_bytes(MANAGED_CONTENT)}
            write_manifest(root / MANIFEST_FILENAME, manifest)

            # The pure check itself must fail closed instead of letting
            # KeyError('role') propagate out of check_harness().
            findings = check_harness(read_harness_manifest(root))
            self.assertEqual(len(findings), 1)
            self.assertEqual(
                (findings[0].severity, findings[0].code, findings[0].path),
                ("ERROR", "HARNESS", MANIFEST_FILENAME))

            lint_py = ROOT / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertNotIn("Traceback", result.stderr, result.stderr)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("ERROR HARNESS", result.stdout)


# Regression guard (Skinner finding, scripts/lint.py:378-381
# read_harness_manifest / manifest.py:136 read_manifest): read_manifest()
# does Path.read_text(encoding="utf-8") before json.loads(), so a manifest
# whose bytes are not valid UTF-8 at all (not merely invalid JSON) raises
# UnicodeDecodeError -- a distinct exception type from json.JSONDecodeError
# -- which read_harness_manifest()'s except clause did not catch, letting
# it propagate uncaught instead of failing closed like every other
# untrustworthy-manifest case above.
class HarnessNonUtf8ManifestFailsClosed(unittest.TestCase):
    def test_harness_non_utf8_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            # Not valid UTF-8 at all (as opposed to
            # HarnessMalformedJsonManifestFailsClosed's syntactically
            # invalid-but-UTF-8 case above) -- raises UnicodeDecodeError,
            # not json.JSONDecodeError.
            (root / MANIFEST_FILENAME).write_bytes(
                b"\xff\xfe\x80\x81 not valid utf-8 at all")

            # The impure edge itself must fail closed instead of letting
            # UnicodeDecodeError propagate out of read_harness_manifest().
            findings = check_harness(read_harness_manifest(root))
            self.assertEqual(len(findings), 1)
            self.assertEqual(
                (findings[0].severity, findings[0].code, findings[0].path),
                ("ERROR", "HARNESS", MANIFEST_FILENAME))

            # End-to-end: the actual CLI (the mandatory pre-commit hook)
            # must not crash with a bare traceback and zero lint output.
            lint_py = ROOT / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertNotIn("Traceback", result.stderr, result.stderr)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("ERROR HARNESS", result.stdout)


# Regression guard (Skinner finding, scripts/lint.py:346-361
# _manifest_shape_error / scripts/lint.py:227-262 check_harness):
# _manifest_shape_error() only checked that a "files" entry carries the
# 'role'/'sha256' KEYS, never that the 'role' VALUE is one of
# manifest.VALID_ROLES. An unrecognized role string (e.g. a hand-edit
# typo) fell through check_harness()'s if/elif role chain with zero
# findings emitted -- silently swallowing real drift instead of failing
# closed like every other untrustworthy-manifest case.
class HarnessManifestUnknownRoleFailsClosed(unittest.TestCase):
    def test_harness_manifest_unknown_role_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            recorded_hash = hash_bytes(MANAGED_CONTENT)
            # Real drift: the on-disk bytes no longer match the manifest's
            # recorded hash at all.
            drifted_content = b"scripts/lint.py HAND-EDITED, drifted contents\n"
            (root / "scripts/lint.py").write_bytes(drifted_content)
            manifest = compute_manifest(
                {}, {}, "git@example.com:hieplam/wiki-harness.git",
                harness_version="1.0.0", source_ref="v1.0.0",
                source_commit="0" * 40, initialised_at="2026-08-26")
            # A typo'd role value that is not one of manifest.VALID_ROLES
            # ("managed"/"template"/"instance-fork"/"removed") --
            # check_harness()'s if/elif role chain has no branch for it.
            manifest["files"]["scripts/lint.py"] = {
                "role": "mangaed",
                "sha256": recorded_hash,
            }
            write_manifest(root / MANIFEST_FILENAME, manifest)

            # Without role-value validation this returned [] -- the real
            # drift above was silently swallowed. Must fail closed with
            # exactly one ERROR HARNESS finding instead.
            findings = check_harness(read_harness_manifest(root))
            self.assertEqual(len(findings), 1, [tuple(f) for f in findings])
            self.assertEqual(
                (findings[0].severity, findings[0].code, findings[0].path),
                ("ERROR", "HARNESS", MANIFEST_FILENAME))


# Regression guard (Skinner-tracker Blocker, A8): plan-v3 section 2.2 only
# vendors scripts/{lint,card_frontmatter_lint,check_commit_msg}.py into a
# real wiki -- lint.py's `from manifest import ...` cannot resolve there
# unless manifest.py is ALSO vendored under scripts/ (A8). This test proves
# lint.py runs standalone from a directory that carries only scripts/*.py
# copied by glob (never a hardcoded 3-file list) and nothing else on
# PYTHONPATH -- exactly the shape init.py/--adopt actually produce in a
# real wiki.
class LintRunsFromVendoredScriptsDirAlone(unittest.TestCase):
    def test_lint_runs_from_vendored_scripts_dir_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            (root / "scripts").mkdir()
            # Glob, never a hardcoded 3-file list, so a future fourth
            # vendored module (e.g. scripts/manifest.py, A8) is covered
            # by this test without editing it.
            managed_paths = []
            for src in sorted((ROOT / "scripts").glob("*.py")):
                shutil.copy(src, root / "scripts" / src.name)
                managed_paths.append(f"scripts/{src.name}")

            actual = hash_tree(root, managed_paths)
            hashes = {path: {"role": "managed", "sha256": actual[path]}
                     for path in managed_paths}
            manifest = compute_manifest(
                hashes, {}, "git@example.com:hieplam/wiki-harness.git",
                harness_version="1.0.0", source_ref="v1.0.0",
                source_commit="0" * 40, initialised_at="2026-08-26")
            write_manifest(root / MANIFEST_FILENAME, manifest)

            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, str(root / "scripts" / "lint.py"),
                 "--root", str(root)],
                cwd=str(root), env=env, capture_output=True, text=True)

            self.assertNotIn("Traceback", result.stderr, result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("HARNESS", result.stdout, result.stdout)


# Regression guard (Skinner finding, scripts/lint.py:357
# _manifest_shape_error): a syntactically valid JSON manifest whose
# top-level value is not a JSON object at all (a list, string, number, or
# bool) crashed with an uncaught AttributeError from
# `manifest.get("files")` -- lists/strs/etc have no .get() -- instead of
# failing closed like every other untrustworthy-manifest shape above.
class HarnessNonObjectTopLevelManifestFailsClosed(unittest.TestCase):
    def test_harness_non_object_top_level_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            # Valid JSON (a bare list), but not a JSON object -- the exact
            # shape `manifest.get("files")` cannot survive.
            (root / MANIFEST_FILENAME).write_text("[]", encoding="utf-8")

            # The impure edge itself must fail closed instead of letting
            # AttributeError propagate out of read_harness_manifest().
            findings = check_harness(read_harness_manifest(root))
            self.assertEqual(len(findings), 1)
            self.assertEqual(
                (findings[0].severity, findings[0].code, findings[0].path),
                ("ERROR", "HARNESS", MANIFEST_FILENAME))

            # End-to-end: the actual CLI (the mandatory pre-commit hook)
            # must not crash with a bare traceback and zero lint output.
            lint_py = ROOT / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertNotIn("Traceback", result.stderr, result.stderr)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("ERROR HARNESS", result.stdout)


# Regression guard (Skinner finding, scripts/lint.py:363
# _manifest_shape_error -> scripts/manifest.py:42 is_valid_role): a
# manifest "files" entry whose 'role' value is an unhashable type (a JSON
# array or object) crashed with an uncaught TypeError from the frozenset
# membership test `role in VALID_ROLES` instead of failing closed like the
# unknown-role-string case above.
class HarnessManifestUnhashableRoleFailsClosed(unittest.TestCase):
    def test_harness_manifest_unhashable_role_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts/lint.py").write_bytes(MANAGED_CONTENT)
            manifest = compute_manifest(
                {}, {}, "git@example.com:hieplam/wiki-harness.git",
                harness_version="1.0.0", source_ref="v1.0.0",
                source_commit="0" * 40, initialised_at="2026-08-26")
            # An unhashable role value (a JSON array) -- `role in
            # VALID_ROLES` (a frozenset membership test) cannot even
            # evaluate this without raising TypeError.
            manifest["files"]["scripts/lint.py"] = {
                "role": ["managed"],
                "sha256": hash_bytes(MANAGED_CONTENT),
            }
            write_manifest(root / MANIFEST_FILENAME, manifest)

            # The impure edge itself must fail closed instead of letting
            # TypeError propagate out of read_harness_manifest().
            findings = check_harness(read_harness_manifest(root))
            self.assertEqual(len(findings), 1)
            self.assertEqual(
                (findings[0].severity, findings[0].code, findings[0].path),
                ("ERROR", "HARNESS", MANIFEST_FILENAME))

            lint_py = ROOT / "scripts" / "lint.py"
            result = subprocess.run(
                [sys.executable, str(lint_py), "--root", str(root)],
                capture_output=True, text=True)
            self.assertNotIn("Traceback", result.stderr, result.stderr)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("ERROR HARNESS", result.stdout)


# Regression guard (Skinner finding, scripts/lint.py:397-421
# read_harness_manifest / scripts/manifest.py:121-127 hash_tree): none of
# _manifest_shape_error()'s validation checked the recorded PATH strings
# themselves for containment inside `root`. hash_tree() does
# `f = root / path; ... f.read_bytes()`, and Path.__truediv__ discards
# `root` entirely when `path` is absolute, and simply walks upward when
# `path` contains ".." segments -- so a manifest carrying a
# ".."-prefixed or absolute-path key (a malicious PR, a hand edit, or a
# future init.py/upgrade.py bug) made lint.py -- "the mandatory pre-commit
# hook" -- silently hash and print the sha256 of an arbitrary file outside
# the wiki root. Must fail closed exactly like every other
# untrustworthy-manifest shape above, before hash_tree() is ever called.
class HarnessManifestPathTraversalFailsClosed(unittest.TestCase):
    def test_harness_manifest_path_traversal_fails_closed(self):
        cases = {
            "dotdot_relative": "../outside-secret.txt",
            "absolute": "/etc/outside-secret.txt",
        }
        for name, traversal_path in cases.items():
            with self.subTest(case=name, path=traversal_path):
                with tempfile.TemporaryDirectory() as tmp:
                    outer = Path(tmp)
                    root = outer / "wiki-root"
                    root.mkdir()
                    _write_tree(root, CLEAN_WIKI_FILES)
                    # A real file that a naive root/path join would
                    # escape to -- placed one directory above `root` so
                    # the relative ".." case has something real to leak.
                    secret = outer / "outside-secret.txt"
                    secret.write_bytes(b"TOP SECRET, never read by lint.py\n")

                    manifest = compute_manifest(
                        {}, {}, "git@example.com:hieplam/wiki-harness.git",
                        harness_version="1.0.0", source_ref="v1.0.0",
                        source_commit="0" * 40, initialised_at="2026-08-26")
                    manifest["files"][traversal_path] = {
                        "role": "managed", "sha256": "0" * 64}
                    write_manifest(root / MANIFEST_FILENAME, manifest)

                    # The pure shape check must reject the traversal path
                    # before read_harness_manifest() ever calls
                    # hash_tree() on it -- exactly one ERROR HARNESS
                    # finding on the manifest itself, never on the
                    # escaping path, and the outside file's real sha256
                    # must never appear anywhere in the finding.
                    findings = check_harness(read_harness_manifest(root))
                    self.assertEqual(len(findings), 1, [tuple(f) for f in findings])
                    f = findings[0]
                    self.assertEqual((f.severity, f.code, f.path),
                                     ("ERROR", "HARNESS", MANIFEST_FILENAME))
                    self.assertNotIn(hash_bytes(secret.read_bytes()), f.message)

                    # End-to-end: the actual CLI must not leak the
                    # outside file's hash either.
                    lint_py = ROOT / "scripts" / "lint.py"
                    result = subprocess.run(
                        [sys.executable, str(lint_py), "--root", str(root)],
                        capture_output=True, text=True)
                    self.assertNotIn("Traceback", result.stderr, result.stderr)
                    self.assertNotIn(hash_bytes(secret.read_bytes()), result.stdout)


# Regression guard (Skinner finding, scripts/lint.py:401-419
# read_harness_manifest / scripts/manifest.py:116-127 hash_tree): neither
# read_harness_manifest() nor hash_tree() caught OSError (PermissionError,
# a mid-run FileNotFoundError race between hash_tree()'s is_file() and
# read_bytes(), etc.) raised while reading a file straight off disk --
# either the manifest file itself, or a managed/template/instance-fork
# path it records -- letting it propagate uncaught out of
# read_harness_manifest() -> check_harness() in main(), crashing lint.py
# (the mandatory pre-commit hook) with a bare traceback and zero
# diagnostic output, exactly the failure class every other
# untrustworthy-manifest case above already fails closed against.
class HarnessUnreadableFileFailsClosed(unittest.TestCase):
    def test_harness_unreadable_manifest_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            _write_manifest(root, {})
            manifest_file = root / MANIFEST_FILENAME
            manifest_file.chmod(0o000)
            try:
                # The impure edge itself must fail closed instead of
                # letting PermissionError propagate out of
                # read_harness_manifest().
                findings = check_harness(read_harness_manifest(root))
                self.assertEqual(len(findings), 1, [tuple(f) for f in findings])
                self.assertEqual(
                    (findings[0].severity, findings[0].code, findings[0].path),
                    ("ERROR", "HARNESS", MANIFEST_FILENAME))

                # End-to-end: the actual CLI (the mandatory pre-commit
                # hook) must not crash with a bare traceback and zero
                # lint output.
                lint_py = ROOT / "scripts" / "lint.py"
                result = subprocess.run(
                    [sys.executable, str(lint_py), "--root", str(root)],
                    capture_output=True, text=True)
                self.assertNotIn("Traceback", result.stderr, result.stderr)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("ERROR HARNESS", result.stdout)
            finally:
                manifest_file.chmod(0o644)

    def test_harness_unreadable_managed_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tree(root, CLEAN_WIKI_FILES)
            (root / "scripts").mkdir()
            managed_file = root / "scripts/lint.py"
            managed_file.write_bytes(MANAGED_CONTENT)
            _write_manifest(root, {
                "scripts/lint.py": ("managed", hash_bytes(MANAGED_CONTENT)),
            })
            managed_file.chmod(0o000)
            try:
                # The impure edge itself must fail closed instead of
                # letting PermissionError propagate out of
                # read_harness_manifest() -> manifest.hash_tree().
                findings = check_harness(read_harness_manifest(root))
                self.assertEqual(len(findings), 1, [tuple(f) for f in findings])
                self.assertEqual(
                    (findings[0].severity, findings[0].code, findings[0].path),
                    ("ERROR", "HARNESS", MANIFEST_FILENAME))

                # End-to-end: the actual CLI must not crash with a bare
                # traceback and zero lint output either.
                lint_py = ROOT / "scripts" / "lint.py"
                result = subprocess.run(
                    [sys.executable, str(lint_py), "--root", str(root)],
                    capture_output=True, text=True)
                self.assertNotIn("Traceback", result.stderr, result.stderr)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("ERROR HARNESS", result.stdout)
            finally:
                managed_file.chmod(0o644)


if __name__ == "__main__":
    unittest.main()
