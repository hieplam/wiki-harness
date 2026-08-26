from __future__ import annotations

import hashlib
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
from manifest import compute_manifest, write_manifest  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
