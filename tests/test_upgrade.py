from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
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


def _library_source_files(root):
    """Copies everything init.py needs to run standalone from `root` --
    its own init.py plus templates/, scripts/, githooks/ -- verbatim from
    this repo's real library sources, so a fixture library checkout
    behaves exactly like a real wiki-harness release (T16B)."""
    shutil.copy2(ROOT / "init.py", root / "init.py")
    shutil.copytree(ROOT / "templates", root / "templates")
    shutil.copytree(ROOT / "scripts", root / "scripts")
    shutil.copytree(ROOT / "githooks", root / "githooks")


def _make_library(root, version):
    """T16B's fixture: a throwaway, git-backed library checkout at
    `version`, tagged v<version>. Every apply-pipeline test in this file
    drives the pipeline via --library-path against a fixture like this one
    -- never a real network round trip."""
    root.mkdir(parents=True, exist_ok=True)
    _library_source_files(root)
    (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "hunter@example.com")
    _git(root, "config", "user.name", "Hunter")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", f"library v{version}")
    _git(root, "tag", f"v{version}")
    return root


def _release_v1_1(v100_root, new_root, *, break_lint=False):
    """Builds a synthetic v1.1.0 release from an existing v1.0.0 fixture
    library checkout, with one deliberate managed-file change:
    templates/wiki.AGENTS.md (copy_managed_agents() copies it verbatim to
    wiki/AGENTS.md). By default the change is a benign comment (a normal,
    lint-clean release); with `break_lint=True` it is a broken markdown
    link instead, so the changed file trips a real LINK finding once it
    lands in the scratch copy -- forcing step 10's scratch lint to fail,
    for the lint-failure-path tests."""
    shutil.copytree(v100_root, new_root, ignore=shutil.ignore_patterns(".git"))
    (new_root / "VERSION").write_text("1.1.0\n", encoding="utf-8")
    tmpl = new_root / "templates" / "wiki.AGENTS.md"
    addition = ("\n[broken](does-not-exist.md)\n" if break_lint
               else "\n<!-- v1.1.0 managed-file change -->\n")
    tmpl.write_text(tmpl.read_text(encoding="utf-8") + addition, encoding="utf-8")
    _git(new_root, "init", "-q")
    _git(new_root, "config", "user.email", "hunter@example.com")
    _git(new_root, "config", "user.name", "Hunter")
    _git(new_root, "add", "-A")
    _git(new_root, "commit", "-q", "-m", "library v1.1.0")
    _git(new_root, "tag", "v1.1.0")
    return new_root


def _release_v1_1_removed_script(v100_root, new_root, removed_script="manifest.py"):
    """Builds a synthetic v1.1.0 release like _release_v1_1(), but instead
    of editing a managed template, DELETES one of the library's own
    scripts/*.py sources entirely (default scripts/manifest.py) -- since
    copy_scripts() (init.py) discovers scripts/*.py purely by what's
    physically present on disk under <library>/scripts/, this makes that
    path drop out of the target version's own build_role_map() altogether,
    simulating a MAJOR release that no longer ships a source for a path
    the OLD manifest still records as managed (T19's guard)."""
    shutil.copytree(v100_root, new_root, ignore=shutil.ignore_patterns(".git"))
    (new_root / "VERSION").write_text("1.1.0\n", encoding="utf-8")
    (new_root / "scripts" / removed_script).unlink()
    _git(new_root, "init", "-q")
    _git(new_root, "config", "user.email", "hunter@example.com")
    _git(new_root, "config", "user.name", "Hunter")
    _git(new_root, "add", "-A")
    _git(new_root, "commit", "-q", "-m",
        f"library v1.1.0 (removed scripts/{removed_script})")
    _git(new_root, "tag", "v1.1.0")
    return new_root


def _release_v1_1_removed_template(v100_root, new_root, removed_template="wiki.AGENTS.md"):
    """Builds a synthetic v1.1.0 release like _release_v1_1_removed_script(),
    but deletes a TEMPLATE source (default templates/wiki.AGENTS.md, which
    copy_managed_agents()'s hardcoded MANAGED_COPY_MAP backs the managed
    path wiki/AGENTS.md with) instead of a scripts/*.py source -- this
    exercises the second, HARDCODED-mapping removal path (as opposed to
    _release_v1_1_removed_script()'s glob-discovered scripts/*.py removal
    path): a source overwrite_scratch()'s own copy_managed_agents() would
    otherwise raise an uncaught FileNotFoundError over, and one
    build_role_map()'s static MANAGED_STATIC_PATHS entry would never
    detect as missing on its own (it names wiki/AGENTS.md unconditionally,
    regardless of whether templates/wiki.AGENTS.md still exists)."""
    shutil.copytree(v100_root, new_root, ignore=shutil.ignore_patterns(".git"))
    (new_root / "VERSION").write_text("1.1.0\n", encoding="utf-8")
    (new_root / "templates" / removed_template).unlink()
    _git(new_root, "init", "-q")
    _git(new_root, "config", "user.email", "hunter@example.com")
    _git(new_root, "config", "user.name", "Hunter")
    _git(new_root, "add", "-A")
    _git(new_root, "commit", "-q", "-m",
        f"library v1.1.0 (removed templates/{removed_template})")
    _git(new_root, "tag", "v1.1.0")
    return new_root


def _release_v1_1_many_changes(v100_root, new_root):
    """Builds a synthetic v1.1.0 release like _release_v1_1(), but instead
    of touching a single managed template, appends a benign, lint-clean
    HTML comment to FIVE managed/template TEMPLATE SOURCES that each map to
    a distinct managed/template TARGET path (per MANAGED_COPY_MAP/
    render_root_templates()'s own hardcoded source names) -- so a real
    apply of this release actually copies 5+ files in promote_scratch()'s
    loop (T21's test needs several files written before its simulated
    mid-loop failure, unlike _release_v1_1()'s single-file change)."""
    shutil.copytree(v100_root, new_root, ignore=shutil.ignore_patterns(".git"))
    (new_root / "VERSION").write_text("1.1.0\n", encoding="utf-8")
    changed_sources = (
        "sources.AGENTS.md",           # -> sources/AGENTS.md
        "wiki.AGENTS.md",               # -> wiki/AGENTS.md
        "sources.cards.AGENTS.md",      # -> sources/cards/AGENTS.md
        "README.md.tmpl",               # -> README.md
        "AGENTS.root.md.tmpl",          # -> AGENTS.md
    )
    for name in changed_sources:
        tmpl = new_root / "templates" / name
        tmpl.write_text(
            tmpl.read_text(encoding="utf-8") + "\n<!-- v1.1.0 change -->\n",
            encoding="utf-8")
    _git(new_root, "init", "-q")
    _git(new_root, "config", "user.email", "hunter@example.com")
    _git(new_root, "config", "user.name", "Hunter")
    _git(new_root, "add", "-A")
    _git(new_root, "commit", "-q", "-m", "library v1.1.0 (many changes)")
    _git(new_root, "tag", "v1.1.0")
    return new_root


INIT_ANSWERS = {
    "wiki_title": "Test Wiki",
    "org_name": "Test Org",
    "content_language": "en",
    "repo_name": "test-repo",
}


def _release_v1_1_bad_hook(v100_root, new_root):
    """Builds a synthetic v1.1.0 release like _release_v1_1(), but engineers
    a lint-vs-hook DIVERGENCE (T23's defense-in-depth case) instead of a
    managed-template content change: this release's own
    githooks/pre-commit is replaced with a hook that unconditionally exits
    non-zero, while scripts/lint.py -- the exact program step 10's scratch
    lint runs -- is left byte-for-byte unmodified and still exits 0. The
    scratch copy step 10 lints is never a git work tree at all (it is a
    bare tempfile.mkdtemp() tree with no .git), so lint.py's own
    hooks_finding() check is skipped there regardless -- step 10 stays
    green. Only once copy_hooks() promotes this broken pre-commit verbatim
    into the REAL target's own .githooks/pre-commit (which IS a live git
    work tree with core.hooksPath already set to .githooks by init) does
    the divergence become observable: a real `git commit` in the target
    now gets rejected by a hook that step 10's lint could never have
    caught, since it never runs through the hook subprocess path at all.

    ALSO adds a brand-new scripts/newthing.py source alongside the existing
    scripts/*.py sources. copy_scripts() (init.py) discovers scripts/*.py
    purely by glob, so this becomes a NEW managed target path
    (scripts/newthing.py) that promote_scratch() writes to the real target
    as a previously-untracked file -- exercising the rollback's untracked-
    new-file case: a plain `git reset` (unstage) + `git checkout -- .`
    (restore tracked paths only) can never remove a file git never tracked
    in the first place, so a rollback that omits `git clean -fd` would
    leave this file behind and the tree dirty. Lint-clean, valid Python, so
    the divergence this fixture exercises comes only from the bad hook,
    never from step 10's scratch lint."""
    shutil.copytree(v100_root, new_root, ignore=shutil.ignore_patterns(".git"))
    (new_root / "VERSION").write_text("1.1.0\n", encoding="utf-8")
    (new_root / "githooks" / "pre-commit").write_text(
        "#!/bin/sh\nexit 1\n", encoding="utf-8")
    (new_root / "scripts" / "newthing.py").write_text(
        '#!/usr/bin/env python3\n'
        '"""A brand-new managed script shipped starting in v1.1.0 (test '
        'fixture only)."""\n'
        'from __future__ import annotations\n',
        encoding="utf-8")
    _git(new_root, "init", "-q")
    _git(new_root, "config", "user.email", "hunter@example.com")
    _git(new_root, "config", "user.name", "Hunter")
    _git(new_root, "add", "-A")
    _git(new_root, "commit", "-q", "-m",
        "library v1.1.0 (pre-commit hook diverges from scripts/lint.py; "
        "adds scripts/newthing.py)")
    _git(new_root, "tag", "v1.1.0")
    return new_root


def _run_init(library_root, target, answers=INIT_ANSWERS):
    args = [sys.executable, str(library_root / "init.py"), str(target),
            "--non-interactive"]
    for key, value in answers.items():
        args += [f"--{key.replace('_', '-')}", value]
    return subprocess.run(args, capture_output=True, text=True)


def _edit_seeded_file_and_commit(target):
    """A legitimate, SEEDED-file-only local edit (VISION.md), committed so
    the tree is clean before upgrade runs -- upgrade's step-1 drift check
    only ever looks at MANAGED/TEMPLATE paths, so this edit must survive
    the apply pipeline byte-for-byte untouched."""
    (target / "VISION.md").write_text(
        "# VISION\n\nOwner edit: ship the widget export next quarter.\n",
        encoding="utf-8")
    _git(target, "add", "-A")
    # Subject must match check_commit_msg.py's '<op>(<ref>): <summary>'
    # convention (the wired-up commit-msg hook enforces this even for a
    # throwaway fixture edit) -- "chore" with no ref is always accepted.
    _git(target, "commit", "-q", "-m", "chore: seeded edit")


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
        (T16B) the full apply pipeline completes: not the dirty-tree exit
        (2), not the drift-abort exit (1) -- the pipeline itself is
        exercised in depth by TestApplyPipeline below; this test only
        proves step 1's gates never block a genuinely clean, non-drifted
        tree."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--library-path", str(v110))
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


class TestApplyPipeline(unittest.TestCase):
    """T16B: the core --apply write pipeline -- resolve the target version
    (step 6), scratch-copy (step 8), overwrite every managed/template path
    (step 9), lint the scratch copy (step 10), bare promote-copy (step
    11), write the manifest last (step 12). No guards (downgrade/
    adopt-drift/MAJOR-removal) -- every fixture here is a clean,
    non-drifted, forward upgrade only."""

    def test_scratch_lint_is_harness_clean(self):
        """Warchief amendment A9: the target's manifest lists >=1 managed
        file whose bytes change in v1.1.0 -- step 10's scratch lint must
        exit 0 with NO HARNESS line at all (the scratch already carries the
        NEW, self-consistent manifest by the time it lints, per A9), and
        the REAL target's manifest bytes stay unchanged until step 12
        (verified by monkeypatching promote to raise immediately after a
        spied-on lint call succeeds)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            before_manifest = (target / MANIFEST_FILENAME).read_bytes()

            real_lint = upgrade.run_scratch_lint
            captured = {}

            def spy_lint(scratch):
                ok, output = real_lint(scratch)
                captured["ok"] = ok
                captured["output"] = output
                return ok, output

            with patch.object(upgrade, "run_scratch_lint", side_effect=spy_lint), \
                 patch.object(upgrade, "promote_scratch",
                              side_effect=RuntimeError("stop-before-promote")):
                with self.assertRaises(RuntimeError):
                    upgrade.run_upgrade(target, False, [], "v1.1.0", str(v110), False)

            self.assertTrue(captured.get("ok"), captured.get("output"))
            self.assertNotIn("HARNESS", captured.get("output", ""))

            after_manifest = (target / MANIFEST_FILENAME).read_bytes()
            self.assertEqual(after_manifest, before_manifest)

    def test_apply_completes_and_updates_every_managed_template_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            init_result = _run_init(v100, target)
            self.assertEqual(init_result.returncode, 0,
                             init_result.stdout + init_result.stderr)
            _edit_seeded_file_and_commit(target)
            seeded_content = (target / "VISION.md").read_bytes()

            old_manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            old_source_url = old_manifest["source_url"]

            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--library-path", str(v110))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            # Every SEEDED edit survives byte-for-byte.
            self.assertEqual((target / "VISION.md").read_bytes(), seeded_content)

            # Every MANAGED/TEMPLATE path (incl. the 4 CLAUDE.md paths) now
            # matches v1.1.0 exactly -- proven by comparing against an
            # INDEPENDENT reference init from the SAME v1.1.0 library and
            # the SAME vars, never hand-duplicated expected bytes.
            reference = tmp / "reference"
            ref_result = _run_init(v110, reference)
            self.assertEqual(ref_result.returncode, 0,
                             ref_result.stdout + ref_result.stderr)
            ref_manifest = json.loads(
                (reference / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            managed_template_paths = [
                p for p, entry in ref_manifest["files"].items()
                if entry["role"] in ("managed", "template")]
            for claude_path in ("CLAUDE.md", "sources/CLAUDE.md",
                                "sources/cards/CLAUDE.md", "wiki/CLAUDE.md"):
                self.assertIn(claude_path, managed_template_paths)
            for path in managed_template_paths:
                self.assertEqual(
                    (target / path).read_bytes(), (reference / path).read_bytes(),
                    f"{path} does not match v1.1.0 exactly")

            # lint.py still exits 0 against the REAL target.
            lint_result = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint_result.returncode, 0,
                             lint_result.stdout + lint_result.stderr)

            # The manifest reflects v1.1.0.
            new_manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(new_manifest["harness_version"], "1.1.0")
            self.assertEqual(new_manifest["source_ref"], "v1.1.0")
            self.assertEqual(new_manifest["source_url"], old_source_url)
            v110_head = _git(v110, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(new_manifest["source_commit"], v110_head)

    def test_scratch_copy_used_not_real_target_until_promote(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            v110_broken = _release_v1_1(
                v100, tmp / "lib-v1.1.0-broken", break_lint=True)

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--library-path", str(v110_broken))
            after = _tree_snapshot(target)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(
                after, before,
                "the real target must stay byte-identical until step 11 "
                "promotes -- step 10's scratch lint failed and must abort "
                "before any real-target write")

    def test_lint_failure_in_scratch_blocks_promote(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            v110_broken = _release_v1_1(
                v100, tmp / "lib-v1.1.0-broken", break_lint=True)

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--library-path", str(v110_broken))
            after = _tree_snapshot(target)
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 1, combined)
            self.assertIn("broken link: does-not-exist.md", combined)
            self.assertNotIn("Traceback", combined)
            self.assertEqual(after, before)

    def test_manifest_written_last_after_promote(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            before_manifest = (target / MANIFEST_FILENAME).read_bytes()

            with patch.object(upgrade, "promote_scratch",
                              side_effect=RuntimeError("promote exploded")):
                with self.assertRaises(RuntimeError):
                    upgrade.run_upgrade(target, False, [], "v1.1.0", str(v110), False)

            after_manifest = (target / MANIFEST_FILENAME).read_bytes()
            self.assertEqual(after_manifest, before_manifest)
            self.assertIn(b'"harness_version": "1.0.0"', after_manifest)


class TestDowngradeGuard(unittest.TestCase):
    """T17: `--to` older than the manifest's current harness_version is
    refused (exit 2) unless --allow-downgrade is passed -- one guard on top
    of T16B's already-working apply pipeline, checked before any fetch or
    write."""

    def test_downgrade_refused_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")
            self.assertEqual(_run_init(v110, target).returncode, 0)

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.0.0", "--apply",
                                  "--library-path", str(v100))
            after = _tree_snapshot(target)

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(
                result.stderr.strip(),
                "`--to v1.0.0` is older than the installed v1.1.0; downgrade "
                "is not supported -- pass `--allow-downgrade` if you "
                "specifically intend this.")
            self.assertEqual(
                after, before,
                "a refused downgrade must fetch/write nothing at all")

    def test_downgrade_proceeds_with_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")
            self.assertEqual(_run_init(v110, target).returncode, 0)

            result = _run_upgrade(target, "--to", "v1.0.0", "--apply",
                                  "--library-path", str(v100),
                                  "--allow-downgrade")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(
                "DOWNGRADE: content is moving BACKWARD from v1.1.0 to "
                "v1.0.0.", result.stderr)

            new_manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(new_manifest["harness_version"], "1.0.0")


class TestAdoptDrift(unittest.TestCase):
    """T18: --adopt-drift <path> (repeatable) flips a drifted managed/
    template path's manifest role to instance-fork PERMANENTLY -- both when
    the path is present-but-edited (its local bytes are preserved exactly)
    and when it is missing entirely from disk (fork-and-never-recreate)."""

    def test_adopt_drift_flips_role_to_instance_fork(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)

            agents_path = target / "wiki" / "AGENTS.md"
            forked_bytes = agents_path.read_bytes() + b"\n<!-- local fork edit -->\n"
            agents_path.write_bytes(forked_bytes)
            _git(target, "add", "-A")
            commit = _git(target, "commit", "--no-verify", "-q", "-m",
                          "chore: fork wiki/AGENTS.md")
            self.assertEqual(commit.returncode, 0, commit.stdout + commit.stderr)

            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--adopt-drift", "wiki/AGENTS.md",
                                  "--library-path", str(v110))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            # The local fork edit is preserved byte-for-byte.
            self.assertEqual(agents_path.read_bytes(), forked_bytes)

            # Every OTHER managed/template path matches an INDEPENDENT
            # reference init of v1.1.0 exactly -- never hand-duplicated
            # expected bytes.
            reference = tmp / "reference"
            ref_result = _run_init(v110, reference)
            self.assertEqual(ref_result.returncode, 0,
                             ref_result.stdout + ref_result.stderr)
            ref_manifest = json.loads(
                (reference / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            managed_template_paths = [
                p for p, entry in ref_manifest["files"].items()
                if entry["role"] in ("managed", "template")]
            self.assertIn("wiki/AGENTS.md", managed_template_paths)
            for path in managed_template_paths:
                if path == "wiki/AGENTS.md":
                    continue
                self.assertEqual(
                    (target / path).read_bytes(), (reference / path).read_bytes(),
                    f"{path} does not match v1.1.0 exactly")

            new_manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(new_manifest["harness_version"], "1.1.0")
            self.assertEqual(
                new_manifest["files"]["wiki/AGENTS.md"]["role"], "instance-fork")

    def test_adopt_drift_warns_every_run_not_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)

            agents_path = target / "wiki" / "AGENTS.md"
            agents_path.write_bytes(
                agents_path.read_bytes() + b"\n<!-- local fork edit -->\n")
            _git(target, "add", "-A")
            commit = _git(target, "commit", "--no-verify", "-q", "-m",
                          "chore: fork wiki/AGENTS.md")
            self.assertEqual(commit.returncode, 0, commit.stdout + commit.stderr)

            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--adopt-drift", "wiki/AGENTS.md",
                                  "--library-path", str(v110))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            # Reproduced byte-for-byte from lint.py's check_harness()
            # instance-fork branch.
            expected_line = (
                "WARN HARNESS wiki/AGENTS.md: forked from wiki-harness at "
                "v1.1.0; local edits are permanent and will not receive "
                "future updates.")

            lint1 = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint1.returncode, 0, lint1.stdout + lint1.stderr)
            self.assertIn(expected_line, lint1.stdout)

            lint2 = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint2.returncode, 0, lint2.stdout + lint2.stderr)
            self.assertIn(expected_line, lint2.stdout)

    def test_adopt_drift_on_missing_path_never_recreates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)

            agents_path = target / "wiki" / "AGENTS.md"
            _git(target, "rm", "-q", "wiki/AGENTS.md")
            commit = _git(target, "commit", "--no-verify", "-q", "-m",
                          "chore: remove wiki/AGENTS.md")
            self.assertEqual(commit.returncode, 0, commit.stdout + commit.stderr)
            self.assertFalse(agents_path.exists())

            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--adopt-drift", "wiki/AGENTS.md",
                                  "--library-path", str(v110))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(agents_path.exists())

            manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["files"]["wiki/AGENTS.md"]["role"], "instance-fork")

            # A SUBSEQUENT upgrade with NO --adopt-drift flag must never
            # recreate it. is_downgrade() to the same version is False, so
            # re-running --to v1.1.0 proceeds through the pipeline again.
            _git(target, "add", "-A")
            commit2 = _git(target, "commit", "--no-verify", "-q", "-m",
                           "chore: land the v1.1.0 upgrade")
            self.assertEqual(commit2.returncode, 0, commit2.stdout + commit2.stderr)

            result2 = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                   "--library-path", str(v110))
            self.assertEqual(result2.returncode, 0, result2.stdout + result2.stderr)
            self.assertFalse(agents_path.exists())


class TestMajorRemovalGuard(unittest.TestCase):
    """T19: for every OLD-manifest managed/template path, if the fetched
    target version's own checkout no longer provides a source for that path
    (i.e. it is no longer a key in init.py's own build_role_map()) -> abort,
    exit 1, name every removed path -- never a crash, never a silent
    orphan, never a silent delete of anything on the real target."""

    def test_major_removal_guard_fires_loud(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            v110_removed = _release_v1_1_removed_script(
                v100, tmp / "lib-v1.1.0-removed")

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--library-path", str(v110_removed))
            after = _tree_snapshot(target)
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 1, combined)
            self.assertIn("scripts/manifest.py", combined)
            self.assertNotIn("Traceback", combined)
            self.assertEqual(
                after, before,
                "the MAJOR-removal guard must abort before any write to "
                "the real target -- nothing fetched or written")

    def test_major_removal_guard_fires_on_removed_template(self):
        """A TEMPLATE source (not a scripts/*.py source) is removed --
        templates/wiki.AGENTS.md, which copy_managed_agents()'s hardcoded
        MANAGED_COPY_MAP backs the managed path wiki/AGENTS.md with. This
        must NOT crash overwrite_scratch() with an uncaught
        FileNotFoundError (build_role_map() alone could never detect this
        removal -- its static entries name wiki/AGENTS.md unconditionally)
        -- the guard must catch it BEFORE any scratch copy, exactly like
        the removed-script case above."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            v110_removed = _release_v1_1_removed_template(
                v100, tmp / "lib-v1.1.0-removed-template")

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--library-path", str(v110_removed))
            after = _tree_snapshot(target)
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 1, combined)
            self.assertIn("wiki/AGENTS.md", combined)
            self.assertNotIn("Traceback", combined)
            self.assertEqual(
                after, before,
                "the MAJOR-removal guard must abort before any write to "
                "the real target, even for a removed TEMPLATE source (not "
                "just a removed script)")

    def test_major_removal_guard_message_does_not_claim_no_fetch(self):
        """By the time this guard runs, step 6 has already fetched/checked
        out the target version -- that fetched checkout is this guard's
        whole premise. The abort message must never claim nothing was
        FETCHED (only that nothing was WRITTEN to the real target)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            v110_removed = _release_v1_1_removed_script(
                v100, tmp / "lib-v1.1.0-removed")

            result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                  "--library-path", str(v110_removed))
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 1, combined)
            self.assertNotIn("fetched", combined)


class TestDryRunSplit(unittest.TestCase):
    """T20: no flags / --report is UNCONDITIONALLY non-mutating, and
    computes+prints the same pending-change report the --apply path would
    act on; only --apply reaches the write pipeline T16B already built and
    proved. This closes v2's own "single biggest self-contradiction" -- a
    bare upgrade invocation (the ordinary, most common case) must NEVER
    write to the real target, full stop, even when there's a legitimate
    pending change to report."""

    def test_no_flags_writes_nothing_even_with_pending_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            # A genuine pending managed-file change at the target version:
            # templates/wiki.AGENTS.md -> wiki/AGENTS.md (_release_v1_1's
            # own deliberate change).
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.1.0",
                                  "--library-path", str(v110))
            after = _tree_snapshot(target)
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 0, combined)
            self.assertIn("wiki/AGENTS.md", combined)
            self.assertEqual(
                after, before,
                "a bare `upgrade --to ...` with no flags must NEVER write "
                "to the real target, even when there is a legitimate "
                "pending change to report")

    def test_report_flag_identical_to_no_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            before = _tree_snapshot(target)
            no_flags_result = _run_upgrade(target, "--to", "v1.1.0",
                                           "--library-path", str(v110))
            after_no_flags = _tree_snapshot(target)
            report_result = _run_upgrade(target, "--to", "v1.1.0",
                                         "--library-path", str(v110), "--report")
            after_report = _tree_snapshot(target)

            self.assertEqual(report_result.returncode, no_flags_result.returncode)
            self.assertEqual(report_result.stdout, no_flags_result.stdout)
            self.assertEqual(after_no_flags, before)
            self.assertEqual(after_report, before)

    def test_apply_flag_routes_to_existing_pipeline(self):
        """Spies on promote_scratch -- the write path calls it, the
        dry-run path must not -- in-process, since monkeypatching cannot
        reach a subprocess. Does NOT re-verify on-disk writes; that
        full-pipeline proof already exists in T16B's own
        test_apply_completes_and_updates_every_managed_template_path."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            argv = [str(target), "--to", "v1.1.0", "--library-path", str(v110)]

            with patch.object(upgrade, "promote_scratch",
                              wraps=upgrade.promote_scratch) as spy:
                exit_code = upgrade.main(argv)
            self.assertEqual(exit_code, 0)
            spy.assert_not_called()

            with patch.object(upgrade, "promote_scratch",
                              wraps=upgrade.promote_scratch) as spy:
                exit_code = upgrade.main(argv + ["--apply"])
            self.assertEqual(exit_code, 0)
            spy.assert_called_once()


class TestAtomicPromote(unittest.TestCase):
    """T21: promote_scratch()'s existing bare copy loop (T16B) is wrapped
    in a SINGLE try/except -- any exception mid-loop triggers `git checkout
    -- .` in the real target (reverting every partial write this run made)
    and the whole pipeline exits 1 with the verbatim rollback message,
    rather than propagating a traceback or leaving the real target
    half-written. An uncatchable kill (SIGKILL/power loss) is NOT covered
    by this try/except at all -- T16's pre-existing clean-tree precondition
    is the entire recovery story for that case, catching the resulting
    dirty tree on the NEXT invocation."""

    def test_promote_exception_triggers_full_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            seeded_content = (target / "VISION.md").read_bytes()
            v110 = _release_v1_1_many_changes(v100, tmp / "lib-v1.1.0-many")

            # Confirm this release genuinely changes >=5 managed/template
            # paths -- so promote_scratch()'s loop actually copies several
            # files before our simulated mid-loop failure below.
            probe_scratch = upgrade.copy_target_to_scratch(target)
            probe_init_mod = upgrade.load_init_module(v110)
            old_manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            upgrade.overwrite_scratch(
                probe_init_mod, v110, probe_scratch, old_manifest["vars"])
            pending = upgrade.pending_changes(probe_scratch, target)
            self.assertGreaterEqual(
                len(pending), 5,
                f"fixture must change >=5 managed/template paths, got {pending}")
            shutil.rmtree(probe_scratch.parent)

            before_manifest = (target / MANIFEST_FILENAME).read_bytes()

            # Simulate promote_scratch() dying partway through its loop:
            # let the first N real writes into the target land, then raise
            # on the next one. `git checkout -- .` (the except handler)
            # uses subprocess, never Path.write_bytes, so the revert below
            # still works even while this patch is active.
            real_write_bytes = Path.write_bytes
            target_str = str(target)
            call_count = {"n": 0}
            raise_after = 2

            def counting_write_bytes(self_path, data):
                if str(self_path).startswith(target_str):
                    call_count["n"] += 1
                    if call_count["n"] > raise_after:
                        raise RuntimeError("simulated promote failure")
                return real_write_bytes(self_path, data)

            stderr = io.StringIO()
            with patch.object(Path, "write_bytes", counting_write_bytes), \
                 contextlib.redirect_stderr(stderr):
                exit_code = upgrade.run_upgrade(
                    target, False, [], "v1.1.0", str(v110), False)

            # Proves the raise actually happened mid-loop, not before the
            # loop started or after it already finished.
            self.assertGreater(call_count["n"], raise_after)

            self.assertEqual(exit_code, 1)

            status = _git(target, "status", "--porcelain").stdout
            self.assertEqual(
                status.strip(), "",
                f"git checkout -- . must fully revert every partial write; "
                f"status was: {status!r}")

            # Every SEEDED edit is untouched (git checkout -- . reverts
            # only tracked-and-modified content, which is exactly this).
            self.assertEqual((target / "VISION.md").read_bytes(), seeded_content)

            after_manifest = (target / MANIFEST_FILENAME).read_bytes()
            self.assertEqual(after_manifest, before_manifest)
            self.assertIn(b'"harness_version": "1.0.0"', after_manifest)

            err = stderr.getvalue()
            self.assertIn(
                "promote failed and was rolled back via `git checkout --`:",
                err)
            self.assertIn("; nothing changed.", err)
            self.assertIn("simulated promote failure", err)
            self.assertNotIn("Traceback", err)

    def test_uncatchable_kill_caught_by_clean_tree_precondition(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            v110 = _release_v1_1_many_changes(v100, tmp / "lib-v1.1.0-many")

            # Simulate an UNCATCHABLE kill (SIGKILL/power loss): write N of
            # M managed files DIRECTLY into the target, bypassing upgrade
            # entirely and never committing -- leaving a dirty, partially-
            # promoted tree, exactly what a real kill mid-promote would
            # leave behind.
            killed_paths = ("wiki/AGENTS.md", "sources/AGENTS.md")
            pre_kill = {p: (target / p).read_bytes() for p in killed_paths}

            probe_scratch = upgrade.copy_target_to_scratch(target)
            probe_init_mod = upgrade.load_init_module(v110)
            old_manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            upgrade.overwrite_scratch(
                probe_init_mod, v110, probe_scratch, old_manifest["vars"])
            for p in killed_paths:
                (target / p).write_bytes((probe_scratch / p).read_bytes())
            shutil.rmtree(probe_scratch.parent)

            # A plain (no --apply) upgrade refuses at the EXISTING
            # clean-tree precondition -- T16's clean-tree gate is the
            # entire recovery story for an uncatchable kill; there is no
            # marker file and nothing special happens here.
            result = _run_upgrade(target, "--to", "v1.1.0",
                                  "--library-path", str(v110))
            combined = result.stdout + result.stderr
            self.assertEqual(result.returncode, 2, combined)
            self.assertIn(upgrade.DIRTY_TREE_MESSAGE, combined)
            self.assertIn(
                "run `git checkout -- .` to discard the partial write",
                combined)
            self.assertNotIn("Traceback", combined)

            # The operator follows the message's own named remedy, by hand.
            checkout_result = _git(target, "checkout", "--", ".")
            self.assertEqual(checkout_result.returncode, 0, checkout_result.stderr)
            status = _git(target, "status", "--porcelain").stdout
            self.assertEqual(status.strip(), "", status)
            for p, before_bytes in pre_kill.items():
                self.assertEqual((target / p).read_bytes(), before_bytes)

            # A fresh --apply now completes normally.
            apply_result = _run_upgrade(target, "--to", "v1.1.0", "--apply",
                                        "--library-path", str(v110))
            self.assertEqual(
                apply_result.returncode, 0,
                apply_result.stdout + apply_result.stderr)
            manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness_version"], "1.1.0")


class TestIdempotencyFastPath(unittest.TestCase):
    """T22: re-running upgrade --to <the currently-installed version> on a
    wiki whose managed/template content already matches that version's
    canonical hashes byte-for-byte must print "already at vX.Y.Z", exit 0,
    and write NOTHING to the real target -- not even the scratch-computed
    manifest -- since promote_scratch()/write_manifest() must never even be
    reached."""

    def test_already_current_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            # init already commits the scaffold, so the tree is clean here.
            status = _git(target, "status", "--porcelain").stdout
            self.assertEqual(status.strip(), "", status)

            before = _tree_snapshot(target)
            result = _run_upgrade(target, "--to", "v1.0.0", "--apply",
                                  "--library-path", str(v100))
            after = _tree_snapshot(target)

            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("already at v1.0.0", result.stdout)
            self.assertEqual(
                after, before,
                "an already-current upgrade must write NOTHING to the "
                "real target")

    def test_already_current_never_reaches_promote_or_write_manifest(self):
        """In-process spy proof, mirroring
        test_apply_flag_routes_to_existing_pipeline: the fast path must
        return before promote_scratch() is EVER called (it is only reached
        past the `apply` branch, which the fast path returns before) --
        and write_manifest() must never be called against the REAL
        target's own manifest path, even with --apply. write_manifest() IS
        still called once against the SCRATCH copy's manifest path -- the
        pre-existing, unconditional step-9-addendum write that is part of
        the shared spine EVERY run performs before this fast path's check
        point (right after reconcile_forks()'s missing-fork call); that
        scratch write is not a write to the real target."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)

            with patch.object(upgrade, "promote_scratch",
                              wraps=upgrade.promote_scratch) as promote_spy, \
                 patch.object(upgrade, "write_manifest",
                              wraps=upgrade.write_manifest) as write_spy:
                exit_code = upgrade.run_upgrade(
                    target, False, [], "v1.0.0", str(v100), False, apply=True)

            self.assertEqual(exit_code, 0)
            promote_spy.assert_not_called()
            real_target_manifest = target / MANIFEST_FILENAME
            write_calls = [call.args[0] for call in write_spy.call_args_list]
            self.assertNotIn(
                real_target_manifest, write_calls,
                "write_manifest() must never be called against the real "
                f"target's manifest path; calls were: {write_calls}")


class TestCommitFlag(unittest.TestCase):
    """T23: --commit stages and commits the promoted changes through a
    real `git commit` subprocess, exercising the target's real
    .githooks/* hooks (already wired up by init.py's core.hooksPath). If
    that real commit is rejected by a hook (a defense-in-depth case that
    should not happen, since step 10 already lint-checked the scratch
    copy, but covers a hook/lint divergence bug), the pipeline
    automatically restores the pre-upgrade tree via `git checkout -- .`
    and exits 1 -- never leaving a dirty, half-applied, or half-staged
    tree as the outcome of a failed self-check."""

    def test_commit_flag_commits_through_real_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            seeded_content = (target / "VISION.md").read_bytes()
            head_before = _git(target, "rev-parse", "HEAD").stdout.strip()

            hooks_path = _git(target, "config", "--get", "core.hooksPath").stdout.strip()
            self.assertEqual(hooks_path, ".githooks")

            v110 = _release_v1_1(v100, tmp / "lib-v1.1.0")

            result = _run_upgrade(target, "--to", "v1.1.0", "--apply", "--commit",
                                  "--library-path", str(v110))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(
                "chore: upgrade wiki-harness v1.0.0 -> v1.1.0", result.stdout)

            # Exactly ONE new commit landed on top of the pre-upgrade HEAD.
            head_after = _git(target, "rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(head_after, head_before)
            parent = _git(target, "rev-parse", "HEAD^").stdout.strip()
            self.assertEqual(parent, head_before)

            subject = _git(target, "log", "-1", "--format=%s").stdout.strip()
            self.assertEqual(
                subject, "chore: upgrade wiki-harness v1.0.0 -> v1.1.0")

            # The working tree is clean (the commit captured every change)
            # and it now matches v1.1.0 -- which only happens if the real
            # .githooks/pre-commit hook (running scripts/lint.py against
            # the real target) actually ran and passed, since --commit
            # never passes --no-verify.
            status = _git(target, "status", "--porcelain").stdout
            self.assertEqual(status.strip(), "", status)
            self.assertIn(
                "<!-- v1.1.0 managed-file change -->",
                (target / "wiki" / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertEqual((target / "VISION.md").read_bytes(), seeded_content)

            manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness_version"], "1.1.0")

    def test_failed_post_write_selfcheck_auto_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = tmp / "target"
            self.assertEqual(_run_init(v100, target).returncode, 0)
            _edit_seeded_file_and_commit(target)
            head_before = _git(target, "rev-parse", "HEAD").stdout.strip()
            # .git/ internal plumbing (index, ORIG_HEAD, logs/...) is
            # expected to churn as part of `git add`/`git reset`/
            # `git checkout` -- even a fully correct rollback leaves those
            # touched. What must be byte-identical is the WORKING TREE:
            # every managed/template file, the manifest, and the seeded
            # edit.
            before = {p: h for p, h in _tree_snapshot(target).items()
                      if not p.startswith(".git/")}

            v110_bad_hook = _release_v1_1_bad_hook(v100, tmp / "lib-v1.1.0-badhook")

            result = _run_upgrade(target, "--to", "v1.1.0", "--apply", "--commit",
                                  "--library-path", str(v110_bad_hook))
            combined = result.stdout + result.stderr

            self.assertEqual(result.returncode, 1, combined)
            self.assertNotIn("Traceback", combined)

            # No new commit was created.
            head_after = _git(target, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(head_after, head_before)

            # The working tree is fully clean again ...
            status = _git(target, "status", "--porcelain").stdout
            self.assertEqual(
                status.strip(), "",
                f"auto-rollback must leave a fully clean tree; status was: {status!r}")

            # ... and every managed/template file AND the manifest are
            # byte-identical to their pre-upgrade state -- proves the
            # rollback did more than `git checkout -- .` alone would have
            # (the index was staged via `git add -A` first, so a bare
            # `git checkout -- .` would just copy the staged NEW content
            # right back).
            after = {p: h for p, h in _tree_snapshot(target).items()
                     if not p.startswith(".git/")}
            self.assertEqual(
                after, before,
                "the tree must be fully restored to its pre-upgrade state")

            # A brand-new managed path the target release introduced
            # (scripts/newthing.py, written by promote_scratch() as a
            # previously-untracked file) must not survive the rollback --
            # `git reset` + `git checkout -- .` alone only restore paths
            # git already TRACKS and can never remove one it never tracked.
            self.assertFalse(
                (target / "scripts" / "newthing.py").exists(),
                "rollback must remove a new untracked file the aborted "
                "apply wrote, not just restore already-tracked paths")


PRE_ADOPT_AGENTS_MD = """# Rules for `sources/cards/`

A **card** is the envelope for exactly one source: where it came from, how much to trust it,
and the atomic claims extracted from it. Cards are mutable — claims and topics may improve.

## Trust and contradiction

| trust | meaning |
|---|---|
| `verified-in-code` | Confirmed against source code or observed system behaviour |
| `stated` | Asserted by a person or document, unverified |
| `hearsay` | Second-hand |
| `legacy-import` | Migrated from the pre-harness wiki; trust not yet re-assessed |

Contradictions resolve by higher trust first, then newer date.

### Per-origin recipes — what to extract

| origin | extract |
|---|---|
| `session` | Verified findings, decisions made, gotchas discovered |
| `transcript` | Speakers/personas, decisions + owners, commitments |
| `jira` | Problem → root cause → fix → affected services |
| `slack` | The question + the tribal answer |
| `confluence` / `research` | Concepts, definitions, procedures |
| `legacy-export` | Whatever the old export tool happened to dump |

All recipes emit the SAME contract: a card with claims, filed into wiki pages. A recipe must
never invent its own wiki-page shape.
"""

ADOPT_ANSWERS = {
    "wiki_title": "Existing Wiki",
    "org_name": "Existing Org",
    "content_language": "en",
    "repo_name": "existing-repo",
}

# The library's own self-contained synthetic fixture wiki -- real wiki
# pages, cards, and a card-schema.json, never anything sourced from the
# real, on-disk ogp-wiki corpus (test_genericity.py's
# SyntheticFixtureNotOgpCorpus guards this for every test file that reads
# a card schema).
SAMPLE_WIKI_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-wiki"


def _make_pre_adopt_target(target_root):
    """T27's fixture: a real, git-backed wiki instance that predates
    wiki-harness entirely -- real content (copied verbatim from the
    library's own tests/fixtures/sample-wiki/: index.md, a wiki page, a
    card, a real card-schema.json), plus VISION.md and DISTINCTIVE
    wiki-specific trust/per-origin prose in sources/cards/AGENTS.md -- but
    NO .wiki-harness-manifest.json at all -- --adopt's whole premise. The
    trust/per-origin rows in PRE_ADOPT_AGENTS_MD never appear in the
    library's own templates/sources.cards.AGENTS.md (which already carries
    the post-split '[recipes](./recipes.md)' pointer, not an inline
    table), so a test asserting recipes.md's content came from THIS text
    actually proves something, rather than merely matching what the
    library would have written anyway."""
    shutil.copytree(SAMPLE_WIKI_FIXTURE, target_root)
    (target_root / "sources" / "raw").mkdir(parents=True, exist_ok=True)
    (target_root / "sources" / "raw" / ".gitkeep").write_bytes(b"")
    (target_root / "sources" / "cards" / "AGENTS.md").write_text(
        PRE_ADOPT_AGENTS_MD, encoding="utf-8")
    (target_root / "VISION.md").write_text(
        "# VISION\n\nPre-existing wiki content, predating wiki-harness.\n",
        encoding="utf-8")
    (target_root / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    _git(target_root, "init", "-q")
    _git(target_root, "config", "user.email", "hunter@example.com")
    _git(target_root, "config", "user.name", "Hunter")
    _git(target_root, "add", "-A")
    _git(target_root, "commit", "-q", "-m", "chore: pre-harness wiki content")
    return target_root


class TestBuildRecipesMd(unittest.TestCase):
    """T27: build_recipes_md() -- the pure extraction/assembly core behind
    --adopt's recipes.md seed."""

    def test_extracts_wiki_real_prose_verbatim(self):
        result = upgrade.build_recipes_md(PRE_ADOPT_AGENTS_MD)
        self.assertIn("# Card recipes", result)
        self.assertIn("## Trust meanings", result)
        self.assertIn(
            "| `legacy-import` | Migrated from the pre-harness wiki; "
            "trust not yet re-assessed |", result)
        self.assertIn("## Per-origin recipes — what to extract", result)
        self.assertIn(
            "| `legacy-export` | Whatever the old export tool happened "
            "to dump |", result)
        self.assertIn(
            "All recipes emit the SAME contract: a card with claims, "
            "filed into wiki pages. A recipe must\nnever invent its own "
            "wiki-page shape.", result)
        # Never the generic library template -- this wiki's OWN rows
        # (never present in templates/recipes.md) must survive verbatim.
        library_template = (ROOT / "templates" / "recipes.md").read_text(
            encoding="utf-8")
        self.assertNotEqual(result, library_template)

    def test_raises_when_trust_section_missing(self):
        text = "# Rules\n\nNo trust section here at all.\n"
        with self.assertRaises(ValueError) as ctx:
            upgrade.build_recipes_md(text)
        self.assertIn("Trust and contradiction", str(ctx.exception))

    def test_raises_when_per_origin_section_missing(self):
        text = (
            "# Rules\n\n## Trust and contradiction\n\n"
            "| trust | meaning |\n|---|---|\n| `stated` | x |\n")
        with self.assertRaises(ValueError) as ctx:
            upgrade.build_recipes_md(text)
        self.assertIn("Per-origin recipes", str(ctx.exception))


class TestAdopt(unittest.TestCase):
    """T27: --adopt's real, no-pre-existing-manifest bootstrap."""

    def test_adopt_bootstraps_fresh_target_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = _make_pre_adopt_target(tmp / "target")

            index_before = (target / "index.md").read_bytes()
            vision_before = (target / "VISION.md").read_bytes()
            schema_before = (target / "sources" / "cards" / "card-schema.json").read_bytes()
            wiki_page_before = (target / "wiki" / "widget-assembly.md").read_bytes()
            card_before = (target / "sources" / "cards" / "src-2024-01-15-001.md").read_bytes()

            result = _run_upgrade(
                target, "--to", "v1.0.0", "--adopt",
                "--library-path", str(v100),
                "--wiki-title", ADOPT_ANSWERS["wiki_title"],
                "--org-name", ADOPT_ANSWERS["org_name"],
                "--content-language", ADOPT_ANSWERS["content_language"],
                "--repo-name", ADOPT_ANSWERS["repo_name"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            # Content -- wiki/*.md, sources/cards/*.md, index.md, VISION.md,
            # card-schema.json -- is byte-for-byte untouched.
            self.assertEqual((target / "index.md").read_bytes(), index_before)
            self.assertEqual((target / "VISION.md").read_bytes(), vision_before)
            self.assertEqual(
                (target / "sources" / "cards" / "card-schema.json").read_bytes(),
                schema_before)
            self.assertEqual(
                (target / "wiki" / "widget-assembly.md").read_bytes(), wiki_page_before)
            self.assertEqual(
                (target / "sources" / "cards" / "src-2024-01-15-001.md").read_bytes(),
                card_before)

            # The 4 CLAUDE.md paths (root + 3 nested) are seeded, matching
            # an INDEPENDENT reference init from the SAME library + vars --
            # never hand-duplicated expected bytes.
            reference = tmp / "reference"
            ref_result = _run_init(v100, reference, answers=ADOPT_ANSWERS)
            self.assertEqual(ref_result.returncode, 0,
                             ref_result.stdout + ref_result.stderr)
            ref_manifest = json.loads(
                (reference / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            managed_template_paths = [
                p for p, entry in ref_manifest["files"].items()
                if entry["role"] in ("managed", "template")]
            for claude_path in ("CLAUDE.md", "sources/CLAUDE.md",
                                "sources/cards/CLAUDE.md", "wiki/CLAUDE.md"):
                self.assertIn(claude_path, managed_template_paths)
            for path in managed_template_paths:
                self.assertEqual(
                    (target / path).read_bytes(), (reference / path).read_bytes(),
                    f"{path} does not match a reference init exactly")

            # recipes.md was seeded from the WIKI'S OWN real prose (never
            # the library's generic template), and is NOT part of the
            # manifest's managed/template set.
            expected_recipes = upgrade.build_recipes_md(PRE_ADOPT_AGENTS_MD)
            self.assertEqual(
                (target / "sources" / "cards" / "recipes.md").read_text(encoding="utf-8"),
                expected_recipes)

            # The manifest is present, records exactly the 4 vars, and is
            # self-consistent (proven, as a side effect, by lint.py exiting
            # 0 with no HARNESS finding below).
            manifest = json.loads((target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness_version"], "1.0.0")
            self.assertEqual(manifest["vars"], ADOPT_ANSWERS)
            self.assertNotIn("sources/cards/recipes.md", manifest["files"])

            # core.hooksPath is configured on the real target.
            hooks_path = _git(target, "config", "--get", "core.hooksPath").stdout.strip()
            self.assertEqual(hooks_path, ".githooks")

            # lint.py exits 0 against the REAL target -- proves, as a side
            # effect, the manifest is self-consistent and none of the 4
            # seeded CLAUDE.md paths produces a finding.
            lint_result = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint_result.returncode, 0,
                             lint_result.stdout + lint_result.stderr)

            # The migration commit -- a separate, explicit, hand-run step
            # of the overall migration procedure (adopt itself never
            # commits, per plan-v3): required before the idempotency
            # re-run below, since upgrade's ordinary clean-tree
            # precondition (unaffected by T27 for every OTHER path) still
            # applies once a manifest exists.
            _git(target, "add", "-A")
            commit_result = _git(target, "commit", "-q", "-m",
                                 "chore: adopt wiki-harness v1.0.0")
            self.assertEqual(commit_result.returncode, 0, commit_result.stderr)

            # EXPLICIT POST-CONDITION: a second `upgrade --to v1.0.0` run
            # (no --adopt) writes ZERO files and prints "already at
            # v1.0.0".
            before_snapshot = _tree_snapshot(target)
            second = _run_upgrade(target, "--to", "v1.0.0",
                                  "--library-path", str(v100))
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(second.stdout.strip(), "already at v1.0.0")
            after_snapshot = _tree_snapshot(target)
            self.assertEqual(
                after_snapshot, before_snapshot,
                "the idempotency re-run must write zero files")

    def test_adopt_missing_required_var_exits_2(self):
        """--wiki-title is the one variable adopt cannot derive. Omitting it
        refuses before a single byte is written (v1.2.0 narrowed the
        required set to this one flag; --org-name/--content-language/
        --repo-name are derived, see the sibling test below)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = _make_pre_adopt_target(tmp / "target")

            before_snapshot = _tree_snapshot(target)
            result = _run_upgrade(
                target, "--to", "v1.0.0", "--adopt",
                "--library-path", str(v100),
                "--org-name", ADOPT_ANSWERS["org_name"],
                "--content-language", ADOPT_ANSWERS["content_language"],
                "--repo-name", ADOPT_ANSWERS["repo_name"])
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(
                "missing required value(s) for --non-interactive mode: "
                "--wiki-title", result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            # Nothing was written -- the real target is untouched.
            self.assertEqual(_tree_snapshot(target), before_snapshot)
            self.assertFalse((target / MANIFEST_FILENAME).exists())

    def test_adopt_derives_every_optional_var_from_one_flag(self):
        """v1.2.0: adopt runs off --wiki-title alone, deriving the other
        three exactly as init does -- repo_name from the target's own
        basename, content_language from the library default, org_name from
        the title -- and records them in the manifest it writes."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            v100 = _make_library(tmp / "lib-v1.0.0", "1.0.0")
            target = _make_pre_adopt_target(tmp / "existing-repo")

            result = _run_upgrade(
                target, "--to", "v1.0.0", "--adopt",
                "--library-path", str(v100),
                "--wiki-title", "Existing Wiki")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            manifest = json.loads(
                (target / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["vars"], {
                "wiki_title": "Existing Wiki",
                "org_name": "Existing Wiki",
                "content_language": "English",
                "repo_name": "existing-repo",
            })


class TestCliPolish(unittest.TestCase):
    """T24: finalize upgrade.py's full argparse surface -- every flag
    plan-v3 section 3.2 documents must parse via the module's real
    parse_args() entry point, and every v3-removed flag (--resume,
    --force-clear-marker (A3), --ci (A4), --fix, --force) must be rejected
    by argparse as unrecognized (SystemExit(2)), never silently accepted."""

    def test_full_argparse_surface_matches_spec(self):
        args = upgrade.parse_args([
            "target",
            "--to", "v1.2.3",
            "--library-path", "/some/library",
            "--apply",
            "--report",
            "--adopt-drift", "wiki/AGENTS.md",
            "--adopt-drift", "wiki/README.md",
            "--allow-downgrade",
            "--commit",
            "--adopt",
            "--check",
        ])
        self.assertEqual(args.target, "target")
        self.assertEqual(args.to, "v1.2.3")
        self.assertEqual(args.library_path, "/some/library")
        self.assertTrue(args.apply)
        self.assertTrue(args.report)
        self.assertEqual(args.adopt_drift, ["wiki/AGENTS.md", "wiki/README.md"])
        self.assertTrue(args.allow_downgrade)
        self.assertTrue(args.commit)
        self.assertTrue(args.adopt)
        self.assertTrue(args.check)

        # --adopt-drift is repeatable and defaults to an empty list when
        # never passed at all (run_upgrade()'s callers rely on this).
        bare = upgrade.parse_args(["target"])
        self.assertEqual(bare.adopt_drift, [])

        # v3 removals (A3, A4): each must be rejected as unrecognized.
        for removed_flag in (
                "--resume", "--force-clear-marker", "--ci", "--fix", "--force"):
            with self.subTest(flag=removed_flag), \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    upgrade.parse_args(["target", removed_flag])
                self.assertEqual(ctx.exception.code, 2)

    def test_every_message_string_matches_spec_verbatim(self):
        self.assertEqual(
            upgrade.DIRTY_TREE_MESSAGE,
            "commit or stash local changes before running upgrade -- if "
            "this follows an interrupted `upgrade --apply`, run `git "
            "checkout -- .` to discard the partial write and restore the "
            "pre-upgrade tree.")

        self.assertEqual(
            upgrade.format_downgrade_refusal("1.2.3", "1.5.0"),
            "`--to v1.2.3` is older than the installed v1.5.0; downgrade "
            "is not supported -- pass `--allow-downgrade` if you "
            "specifically intend this.")


if __name__ == "__main__":
    unittest.main()


class BytecodeNeverReachesTheTarget(unittest.TestCase):
    """Regression: `python3 scripts/lint.py` inside the scratch imports the
    scratch's own manifest/card_frontmatter_lint modules, and CPython writes
    `scripts/__pycache__/*.pyc` next to them. Both promote_scratch() and
    pending_changes() walk the scratch with rglob("*"), so that bytecode was
    reported as a "managed/template path that would change" and then copied
    into the consumer's wiki.

    Invisible on macOS, where the system interpreter redirects bytecode to
    ~/Library/Caches/com.apple.python; it fires on every Linux upgrade.
    Caught by the first CI run on this repository.

    Two independent guards, tested separately: the lint subprocess is told
    not to write bytecode at all, and both tree walks skip it regardless of
    what created it.
    """

    def _scratch_and_target(self, tmp):
        """A scratch tree carrying bytecode the target does not have."""
        scratch = Path(tmp) / "scratch"
        target = Path(tmp) / "target"
        for root in (scratch, target):
            (root / "scripts").mkdir(parents=True)
            (root / "scripts" / "lint.py").write_text("# lint\n", encoding="utf-8")
        cache = scratch / "scripts" / "__pycache__"
        cache.mkdir()
        (cache / "manifest.cpython-39.pyc").write_bytes(b"\x00compiled\n")
        (cache / "lint.cpython-313.pyc").write_bytes(b"\x00compiled\n")
        (scratch / "wiki").mkdir()
        (scratch / "wiki" / "AGENTS.md").write_text("real change\n", encoding="utf-8")
        return scratch, target

    def test_pending_changes_never_reports_bytecode(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch, target = self._scratch_and_target(tmp)

            changed = upgrade.pending_changes(scratch, target)

            self.assertIn("wiki/AGENTS.md", changed)
            for path in changed:
                self.assertNotIn("__pycache__", path)
                self.assertFalse(path.endswith(".pyc"), path)

    def test_promote_never_copies_bytecode_into_the_wiki(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch, target = self._scratch_and_target(tmp)

            self.assertIsNone(upgrade.promote_scratch(scratch, target))

            self.assertEqual(
                (target / "wiki" / "AGENTS.md").read_text(encoding="utf-8"),
                "real change\n")
            self.assertFalse((target / "scripts" / "__pycache__").exists())

    def test_the_scratch_lint_is_told_not_to_write_bytecode(self):
        """Root cause, not just cleanup: the bytecode is never created."""
        captured = {}

        def fake_run(args, **kwargs):
            captured.update(kwargs)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with patch.object(upgrade.subprocess, "run", side_effect=fake_run):
            upgrade.run_scratch_lint("/tmp/does-not-matter")

        self.assertEqual(captured["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertIsNotNone(captured.get("timeout"))
