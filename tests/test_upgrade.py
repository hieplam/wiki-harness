from __future__ import annotations

import contextlib
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
UPGRADE_PY = ROOT / "upgrade.py"

sys.path.insert(0, str(ROOT / "scripts"))
from manifest import compute_manifest, hash_tree, write_manifest  # noqa: E402

sys.path.insert(0, str(ROOT))
import upgrade  # noqa: E402  (needs the sys.path line above)

MANIFEST_FILENAME = ".wiki-harness-manifest.json"


def _git(root, *args):
    """Isolated exactly like init.py's own _git() helper: the host's
    global/system git config never leaks into these throwaway fixture
    repos, only PATH etc. does (via the inherited environment)."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, env=env)


def _make_remote(root, tags):
    """Builds a throwaway local git repo (never a real network remote --
    `git ls-remote` accepts a filesystem path exactly like a URL) with one
    commit and the given lightweight `tags` list, and returns its path as
    a string usable directly as a manifest source_url."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "hunter@example.com")
    _git(root, "config", "user.name", "Hunter")
    (root / "f.txt").write_text("hi\n", encoding="utf-8")
    _git(root, "add", "f.txt")
    _git(root, "commit", "-q", "-m", "init")
    for tag in tags:
        _git(root, "tag", tag)
    return str(root)


def _make_target(root, harness_version, source_url):
    """Builds a throwaway wiki instance directory carrying only what
    upgrade --check reads: a self-consistent manifest naming
    `harness_version`/`source_url`. --check never reads any other file."""
    root.mkdir(parents=True, exist_ok=True)
    write_manifest(root / MANIFEST_FILENAME, compute_manifest(
        {}, {}, source_url,
        harness_version=harness_version, source_ref=f"v{harness_version}",
        source_commit="0" * 40, initialised_at="2026-08-26"))
    return root


def _tree_snapshot(root):
    """Test-only I/O: a {relative_path: sha256} map of every file under
    `root`, used to prove --check wrote nothing at all -- not even a
    touched mtime-only file, since content hash is what's compared."""
    snapshot = {}
    for f in sorted(root.rglob("*")):
        if f.is_file():
            snapshot[f.relative_to(root).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return snapshot


def _run_check(target):
    return subprocess.run(
        [sys.executable, str(UPGRADE_PY), str(target), "--check"],
        capture_output=True, text=True)


def _run_upgrade(target, *extra_args):
    return subprocess.run(
        [sys.executable, str(UPGRADE_PY), str(target), *extra_args],
        capture_output=True, text=True)


def _make_wiki(root, harness_version="1.0.0"):
    """T16's fixture: a REAL git-backed wiki instance carrying actual
    managed files on disk (wiki/AGENTS.md, index.md), a self-consistent
    manifest recording them as role 'managed' with their real sha256
    (computed the same way compute_manifest()/hash_tree() do it -- no
    hand-typed hex), then a clean, committed git baseline -- so every test
    below mutates from a known-clean starting tree, isolated from the
    host's global/system git config exactly like _git()'s other callers."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "wiki").mkdir(parents=True, exist_ok=True)
    (root / "wiki" / "AGENTS.md").write_text("# Wiki rules\n", encoding="utf-8")
    (root / "index.md").write_text("# Index\n", encoding="utf-8")
    managed_paths = ["wiki/AGENTS.md", "index.md"]
    hashes = {p: {"role": "managed", "sha256": h}
             for p, h in hash_tree(root, managed_paths).items()}
    manifest = compute_manifest(
        hashes, {}, "https://example.invalid/wiki-harness.git",
        harness_version=harness_version, source_ref=f"v{harness_version}",
        source_commit="0" * 40, initialised_at="2026-08-26")
    write_manifest(root / MANIFEST_FILENAME, manifest)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "hunter@example.com")
    _git(root, "config", "user.name", "Hunter")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


class TestCheck(unittest.TestCase):
    def test_check_reports_up_to_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            remote = _make_remote(tmp / "remote", ["v1.0.0"])
            target = _make_target(tmp / "target", "1.0.0", remote)
            result = _run_check(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), "up to date at v1.0.0")

    def test_check_reports_newer_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            remote = _make_remote(tmp / "remote", ["v1.0.0", "v1.2.0"])
            target = _make_target(tmp / "target", "1.0.0", remote)
            result = _run_check(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                result.stdout.strip(),
                "v1.2.0 available -- run `upgrade --to v1.2.0 --apply`")

    def test_check_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            remote = _make_remote(tmp / "remote", ["v1.0.0"])
            target = _make_target(tmp / "target", "1.0.0", remote)
            before = _tree_snapshot(target)
            result = _run_check(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(_tree_snapshot(target), before)

            remote2 = _make_remote(tmp / "remote2", ["v1.0.0", "v1.2.0"])
            target2 = _make_target(tmp / "target2", "1.0.0", remote2)
            before2 = _tree_snapshot(target2)
            result2 = _run_check(target2)
            self.assertEqual(result2.returncode, 0, result2.stdout + result2.stderr)
            self.assertEqual(_tree_snapshot(target2), before2)

    def test_check_unreachable_remote_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            unreachable = str(tmp / "does-not-exist-as-a-git-repo")
            target = _make_target(tmp / "target", "1.0.0", unreachable)
            result = _run_check(target)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_check_ls_remote_tags_passes_timeout(self):
        """Regression guard: ls_remote_tags's `git ls-remote` subprocess
        call must bound its wait via `timeout=`, so a reachable-but-
        unresponsive remote (firewall drop, network black hole, stalled
        VPN path) is reported as unreachable within a bounded time instead
        of hanging past the module's own 'one round-trip' contract."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(upgrade.subprocess, "run", side_effect=fake_run):
            upgrade.ls_remote_tags("irrelevant")

        self.assertIn("timeout", captured)
        self.assertIsNotNone(captured["timeout"])
        self.assertGreater(captured["timeout"], 0)

    def test_check_stalled_remote_exits_1(self):
        """A remote that is reachable but never responds -- `git ls-remote`
        hitting the timeout above and subprocess.run raising
        TimeoutExpired -- must be treated exactly like a hard-failure
        unreachable remote: --check exits 1, never an uncaught
        exception/traceback."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            target = _make_target(
                tmp / "target", "1.0.0", "https://example.invalid/repo.git")
            with patch.object(
                    upgrade.subprocess, "run",
                    side_effect=subprocess.TimeoutExpired(
                        cmd=["git", "ls-remote", "--tags"], timeout=1)):
                self.assertIsNone(upgrade.ls_remote_tags(str(target)))
                rc = upgrade.main([str(target), "--check"])
            self.assertEqual(rc, 1)

    def test_check_malformed_local_version_does_not_claim_up_to_date(self):
        """Regression guard: a manifest whose harness_version is missing or
        not well-formed semver must never be reported as 'up to date' --
        that fabricates a comparison result nobody actually made, even when
        (as here) the remote genuinely carries a newer release. --check
        must instead surface that the local version could not be
        determined, while still honouring the exit-0 contract (only an
        unreachable remote/checkout exits 1)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            remote = _make_remote(tmp / "remote", ["v1.0.0", "v9.9.9"])
            target = _make_target(tmp / "target", "not-a-semver-string", remote)
            result = _run_check(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            combined = result.stdout + result.stderr
            self.assertNotIn("up to date", combined)
            self.assertIn("not-a-semver-string", combined)

    def test_check_null_local_version_does_not_crash(self):
        """Regression guard: a manifest whose harness_version field is
        present but JSON null (e.g. a hand-edited or partially-written
        manifest) must be treated exactly like any other malformed local
        version -- surfaced via check_message()'s documented 'not valid
        semver -- cannot determine whether an upgrade is available'
        message -- never an uncaught TypeError/traceback out of
        parse_semver()/check_message()."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            remote = _make_remote(tmp / "remote", ["v1.0.0", "v9.9.9"])
            target = _make_target(tmp / "target", None, remote)
            result = _run_check(target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            combined = result.stdout + result.stderr
            self.assertNotIn("Traceback", combined)
            self.assertNotIn("up to date", combined)
            self.assertIn("not valid semver", combined)

    def test_check_invalid_json_manifest_exits_cleanly(self):
        """Regression guard: a manifest file that exists but is not
        syntactically valid JSON (a truncated write, a hand edit) must
        make --check exit 1 with a clean error message on stderr, never
        an uncaught JSONDecodeError traceback -- the same clean
        error-message-plus-exit-1 pattern run_check() already uses for an
        unreachable remote."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            target = tmp / "target"
            target.mkdir()
            (target / MANIFEST_FILENAME).write_text("{not valid json", encoding="utf-8")
            result = _run_check(target)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_check_non_object_manifest_exits_cleanly(self):
        """Regression guard: a manifest file that parses as valid JSON but
        is not a JSON object (e.g. a bare JSON array) must not crash
        run_check()'s manifest.get(...) field access with an uncaught
        AttributeError -- it must exit 1 with a clean error message on
        stderr instead, same pattern as the invalid-JSON case above."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            target = tmp / "target"
            target.mkdir()
            (target / MANIFEST_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
            result = _run_check(target)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_check_missing_manifest_exits_1_without_remote_call(self):
        """Regression guard (amendment A11): a target directory with NO
        manifest file at all must fail closed before any remote contact --
        ls_remote_tags() must never be called -- with the exact clarity
        message on stderr, never the misleading "remote '' is
        unreachable" that falls out of treating a missing manifest like an
        empty one."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()

            def _must_not_be_called(*args, **kwargs):
                raise AssertionError(
                    "ls_remote_tags must not be called for a missing manifest")

            stderr = io.StringIO()
            with patch.object(upgrade, "ls_remote_tags", side_effect=_must_not_be_called):
                with contextlib.redirect_stderr(stderr):
                    rc = upgrade.run_check(target)

            self.assertEqual(rc, 1)
            expected = (
                f"upgrade --check: manifest {str(target / MANIFEST_FILENAME)!r} "
                "is missing — this wiki was not initialised with "
                "wiki-harness; run 'upgrade --adopt' to generate one")
            self.assertIn(expected, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_check_non_utf8_manifest_exits_1_without_remote_call(self):
        """Regression guard (amendment A11): a manifest file whose bytes are
        not valid UTF-8 (e.g. a hand edit in a different encoding) must fail
        closed exactly like an unreadable/invalid-JSON manifest -- exit 1,
        one clean stderr line, no traceback -- and must never reach the
        remote round-trip; ls_remote_tags() must never be called."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            (target / MANIFEST_FILENAME).write_bytes(b"\xff\xfe bad")

            def _must_not_be_called(*args, **kwargs):
                raise AssertionError(
                    "ls_remote_tags must not be called for a non-UTF-8 manifest")

            stderr = io.StringIO()
            with patch.object(upgrade, "ls_remote_tags", side_effect=_must_not_be_called):
                with contextlib.redirect_stderr(stderr):
                    rc = upgrade.run_check(target)

            self.assertEqual(rc, 1)
            lines = stderr.getvalue().splitlines()
            self.assertEqual(len(lines), 1, stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_check_null_manifest_is_non_object_exits_1_without_remote_call(self):
        """Regression guard (amendment A11): a manifest file whose content is
        the JSON literal `null` (read_manifest() returns Python None) is a
        NON-OBJECT manifest, not an absent one -- --check must fail closed
        with the existing 'is not a JSON object' message and must never
        reach the remote round-trip (previously manifest.get(...) was
        skipped via `if manifest else ""`, source_url became "", and
        ls_remote_tags("") was called, producing the misleading "remote ''
        is unreachable")."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            (target / MANIFEST_FILENAME).write_text("null", encoding="utf-8")

            def _must_not_be_called(*args, **kwargs):
                raise AssertionError(
                    "ls_remote_tags must not be called for a null manifest")

            stderr = io.StringIO()
            with patch.object(upgrade, "ls_remote_tags", side_effect=_must_not_be_called):
                with contextlib.redirect_stderr(stderr):
                    rc = upgrade.run_check(target)

            self.assertEqual(rc, 1)
            value = stderr.getvalue()
            self.assertNotIn("remote ''", value)
            self.assertNotIn("unreachable", value)
            self.assertIn("is not a JSON object", value)
            self.assertNotIn("Traceback", value)


class TestDriftCheck(unittest.TestCase):
    """T16: the refuse-before-write drift check -- the fatal-flaw fix and
    the single most load-bearing test in the whole plan (plan-v3 section
    3.2 step 1, quoted verbatim in the T16 brief)."""

    def test_clean_upgrade_no_drift(self):
        """A clean fixture, no local edits at all -> every gate passes and
        step 1 reaches the (not-yet-implemented) apply-pipeline stub: not
        the dirty-tree exit (2), not the drift-abort exit (1)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = _make_wiki(Path(tmp) / "target")
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply")
            combined = result.stdout + result.stderr
            self.assertNotIn(
                "commit or stash local changes before running upgrade",
                combined)
            self.assertNotIn("refusing to proceed", combined)
            self.assertNotIn(result.returncode, (1, 2), combined)

    def test_hand_edited_managed_file_blocks_upgrade(self):
        """A managed file is hand-edited AND COMMITTED (clean tree, drifted
        hash). upgrade must abort with exit 1, name the drifted path and
        BOTH hashes, and -- the entire point of this test -- leave every
        single file on disk byte-for-byte unchanged: proving nothing was
        fetched or written, not merely that the exit code looks right."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            target = _make_wiki(tmp / "target")
            recorded_hash = hashlib.sha256(b"# Wiki rules\n").hexdigest()
            edited_bytes = b"# Wiki rules (hand-edited)\n"
            actual_hash = hashlib.sha256(edited_bytes).hexdigest()
            (target / "wiki" / "AGENTS.md").write_bytes(edited_bytes)
            _git(target, "add", "-A")
            _git(target, "commit", "-q", "-m", "hand edit of a managed file")

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply")
            after = _tree_snapshot(target)

            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 1, combined)
            self.assertIn("wiki/AGENTS.md", combined)
            self.assertIn(recorded_hash, combined)
            self.assertIn(actual_hash, combined)
            self.assertEqual(after, before,
                             "upgrade wrote/modified something on disk -- "
                             "step 1 must abort before any fetch or write")

    def test_missing_managed_path_is_drift_not_crash(self):
        """A managed file is git-rm'd and committed (clean tree, path gone
        entirely). upgrade must refuse with the DISTINCT deleted-path
        message, exit 1 -- never a crash, never a silent recreate."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            target = _make_wiki(tmp / "target", harness_version="1.0.0")
            _git(target, "rm", "-q", "wiki/AGENTS.md")
            _git(target, "commit", "-q", "-m", "remove a managed file")

            result = _run_upgrade(target, "--to", "v1.1.0", "--apply")
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 1, combined)
            self.assertIn(
                "file was deleted, expected to exist at v1.0.0.", combined)
            self.assertNotIn("Traceback", combined)

    def test_dirty_tree_precondition_names_checkout_remedy(self):
        """An ordinary UNCOMMITTED edit (not a crashed upgrade -- just a
        local edit) must refuse at the very first gate: exit 2, with the
        exact clean-tree message quoted verbatim in the T16 brief -- the
        entire crash-recovery story, byte-for-byte."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            target = _make_wiki(tmp / "target")
            (target / "wiki" / "AGENTS.md").write_text(
                "# uncommitted local edit\n", encoding="utf-8")

            result = _run_upgrade(target, "--to", "v1.1.0", "--apply")
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 2, combined)
            self.assertIn(
                "commit or stash local changes before running upgrade -- "
                "if this follows an interrupted `upgrade --apply`, run "
                "`git checkout -- .` to discard the partial write and "
                "restore the pre-upgrade tree.",
                combined)


if __name__ == "__main__":
    unittest.main()
