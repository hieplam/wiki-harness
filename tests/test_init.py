"""End-to-end tests for init.py's full 16-step flow (plan-v3 section 3.1,
T13): no --ci flag anywhere, CLAUDE.md (root) and its 3 nested stubs seeded
as ordinary MANAGED, TRACKED files. Most tests here drive init.py as a
real subprocess against a throwaway temp directory -- never against
wiki-harness's own checkout -- and inspect the resulting on-disk wiki
instance and its git history; the T31A regression guards below instead
drive init.py's main() entry point in-process, or pin the subprocess seam
directly, to reproduce/pin a relative-target defect at the unit level.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
INIT_PY = ROOT / "init.py"

sys.path.insert(0, str(ROOT / "scripts"))
from manifest import hash_tree  # noqa: E402

sys.path.insert(0, str(ROOT))
import init as init_module  # noqa: E402

VARS_ARGS = (
    "--wiki-title", "Sample Wiki",
    "--org-name", "Sample Org",
    "--content-language", "English",
    "--repo-name", "sample-wiki",
)


def _run_init(target, extra_args=()):
    args = [sys.executable, str(INIT_PY), str(target),
           *VARS_ARGS, "--non-interactive", *extra_args]
    return subprocess.run(args, capture_output=True, text=True)


def _git(root, *args):
    """Isolates the test's own git calls from the host's global/system
    config, matching test_harness_e2e.py's _git() -- a hostile or merely
    unusual host gitconfig (commit.gpgsign=true with no usable key, for
    instance) must never change whether these assertions hold."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, env=env)


class InitOnEmptyDirLintsClean(unittest.TestCase):
    def test_init_on_empty_dir_lints_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            lint_result = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint_result.returncode, 0, lint_result.stdout)


class InitSetsHookspath(unittest.TestCase):
    def test_init_sets_hookspath(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            hooks = _git(target, "config", "--get", "core.hooksPath")
            self.assertEqual(hooks.stdout.strip(), ".githooks")


class InitWritesManifestMatchingDisk(unittest.TestCase):
    def test_init_writes_manifest_matching_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            manifest = json.loads(
                (target / ".wiki-harness-manifest.json").read_text(encoding="utf-8"))
            recorded = manifest["files"]
            self.assertTrue(recorded)
            self.assertNotEqual(manifest["source_url"], "")

            actual = hash_tree(target, list(recorded))
            for path, entry in recorded.items():
                self.assertEqual(actual.get(path), entry["sha256"], path)


class InitRefusesNonemptyWithoutForce(unittest.TestCase):
    def test_init_refuses_nonempty_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            target.mkdir()
            (target / "keep.txt").write_text("pre-existing", encoding="utf-8")

            result = _run_init(target)

            self.assertEqual(result.returncode, 2)
            self.assertIn("is not empty", result.stderr)
            self.assertIn("--force", result.stderr)
            self.assertEqual(list(target.iterdir()), [target / "keep.txt"])


class InitRefusesWhenTargetIsAFile(unittest.TestCase):
    """A target path that already exists as a plain file (not a directory)
    can never be scaffolded into -- there is no directory to write into,
    and --force cannot change that. init.py must route this through
    resolve_target_refusal()'s graceful exit-2 refusal, never crash with an
    unhandled NotADirectoryError/FileExistsError traceback, for either
    invocation."""

    def _assert_graceful_refusal(self, result, target, original_bytes):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("not empty", result.stderr)
        self.assertIn("--force", result.stderr)
        self.assertTrue(target.is_file())
        self.assertEqual(target.read_bytes(), original_bytes)

    def test_init_refuses_when_target_is_a_file_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            target.write_text("pre-existing file", encoding="utf-8")
            original = target.read_bytes()

            result = _run_init(target)

            self._assert_graceful_refusal(result, target, original)

    def test_init_refuses_when_target_is_a_file_with_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            target.write_text("pre-existing file", encoding="utf-8")
            original = target.read_bytes()

            result = _run_init(target, extra_args=("--force",))

            self._assert_graceful_refusal(result, target, original)


class InitRefusesWhenTargetIsABrokenSymlink(unittest.TestCase):
    """A target path that already exists on disk as a dangling/broken
    symlink (the link entry is there; whatever it points at is not) is the
    sibling of InitRefusesWhenTargetIsAFile's 'target exists as a
    non-directory' case: Path.exists() reports False for it (it follows
    the link), but Path.mkdir(exist_ok=True) still raises FileExistsError
    (it stats the link entry itself). init.py must route this through
    resolve_target_refusal()'s graceful exit-2 refusal too, never crash
    with an unhandled FileExistsError traceback, for either invocation."""

    def _assert_graceful_refusal(self, result, target):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("not empty", result.stderr)
        self.assertIn("--force", result.stderr)
        self.assertTrue(target.is_symlink())
        self.assertFalse(target.exists())

    def test_init_refuses_when_target_is_a_broken_symlink_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            target.symlink_to(Path(tmp) / "nonexistent-target-xyz")

            result = _run_init(target)

            self._assert_graceful_refusal(result, target)

    def test_init_refuses_when_target_is_a_broken_symlink_with_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            target.symlink_to(Path(tmp) / "nonexistent-target-xyz")

            result = _run_init(target, extra_args=("--force",))

            self._assert_graceful_refusal(result, target)


class InitFirstCommitGoesThroughRealHooks(unittest.TestCase):
    """Subprocess-level proof that .githooks/* are real, live hooks on the
    freshly-scaffolded repo, not merely files copied to disk: a second,
    deliberately invalid-subject `git commit` -- a real subprocess, not an
    in-process call to check_commit_msg.py -- must be refused by the wired
    core.hooksPath, and the one commit init.py's own step 14 made (also a
    real subprocess git commit, per init.py's commit_scaffold()) must be
    the only commit that ever lands."""

    def test_init_first_commit_goes_through_real_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            log_before = _git(target, "log", "--oneline")
            self.assertEqual(len(log_before.stdout.splitlines()), 1)

            bad_commit = _git(target, "commit", "--allow-empty",
                              "-m", "not a valid conventional subject")
            self.assertNotEqual(bad_commit.returncode, 0)

            log_after = _git(target, "log", "--oneline")
            self.assertEqual(log_after.stdout, log_before.stdout)


class InitSeedsClaudeMdStubsTracked(unittest.TestCase):
    CLAUDE_PATHS = ("CLAUDE.md", "sources/CLAUDE.md",
                    "sources/cards/CLAUDE.md", "wiki/CLAUDE.md")
    ATTRIBUTABLE_CODES = ("FM", "INDEX", "ORPHAN", "CARD_FM")

    def test_init_seeds_claude_md_stubs_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            for rel in self.CLAUDE_PATHS:
                self.assertTrue((target / rel).is_file(), rel)

            show = _git(target, "show", "--stat", "HEAD")
            for rel in self.CLAUDE_PATHS:
                self.assertIn(rel, show.stdout, rel)

            # T08 pre-emptively added "CLAUDE.md" to lint.py's RULES_FILES
            # so a tracked CLAUDE.md stub never trips FM/INDEX/ORPHAN/
            # CARD_FM -- this proves that promise against the real,
            # post-scaffold lint run, not merely "lint exits 0 overall".
            lint_result = subprocess.run(
                [sys.executable, str(target / "scripts" / "lint.py"),
                 "--root", str(target)],
                capture_output=True, text=True)
            self.assertEqual(lint_result.returncode, 0, lint_result.stdout)
            for path in self.CLAUDE_PATHS:
                for code in self.ATTRIBUTABLE_CODES:
                    self.assertNotIn(f" {code} {path}:", lint_result.stdout,
                                     f"{code} finding attributable to {path}")


class InitScaffoldHasNoTestsDir(unittest.TestCase):
    def test_init_scaffold_has_no_tests_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            found = [p for p in target.rglob("tests") if p.is_dir()]
            self.assertEqual(found, [])


class NonInteractiveWithAllFlagsZeroPrompts(unittest.TestCase):
    """--non-interactive with all 4 required flags set must never call
    input() -- proven here by starving stdin (DEVNULL) so an accidental
    input() call raises EOFError and crashes the subprocess instead of
    silently reading nothing, plus a rerun proving the output is
    deterministic (identical stdout modulo the commit hash line)."""

    @staticmethod
    def _normalized(stdout, target):
        """Strips the one target path and the one commit-hash prefix that
        legitimately differ run to run, so two independent scaffolds of
        identical inputs can be compared for byte-identical remaining
        output."""
        text = stdout.replace(str(target), "TARGET")
        lines = text.splitlines()
        return [l.split(" -- lint clean")[0] if l.startswith("Scaffolded") else l
               for l in lines]

    def test_non_interactive_with_all_flags_zero_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            args = [sys.executable, str(INIT_PY), str(target),
                    *VARS_ARGS, "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            normalized_1 = self._normalized(result.stdout, target)

        with tempfile.TemporaryDirectory() as tmp2:
            target2 = Path(tmp2) / "wiki"
            args2 = [sys.executable, str(INIT_PY), str(target2),
                     *VARS_ARGS, "--non-interactive"]
            result2 = subprocess.run(args2, capture_output=True, text=True,
                                     stdin=subprocess.DEVNULL)
            self.assertEqual(result2.returncode, 0, result2.stderr)
            normalized_2 = self._normalized(result2.stdout, target2)

            self.assertEqual(normalized_1, normalized_2)


class NonInteractiveMissingRequiredFlagExits2(unittest.TestCase):
    def test_non_interactive_missing_required_flag_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            args = [sys.executable, str(INIT_PY), str(target),
                    "--org-name", "Sample Org",
                    "--content-language", "English",
                    "--repo-name", "sample-wiki",
                    "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 2)
            self.assertIn("--wiki-title", result.stderr)
            self.assertFalse(target.exists())


class AnswersFileSuppliesAllValues(unittest.TestCase):
    def test_answers_file_supplies_all_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_text(json.dumps({
                "wiki_title": "Answers Wiki",
                "org_name": "Answers Org",
                "content_language": "English",
                "repo_name": "answers-wiki",
            }), encoding="utf-8")

            args = [sys.executable, str(INIT_PY), str(target),
                    "--answers-file", str(answers_path), "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(
                (target / ".wiki-harness-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["vars"]["wiki_title"], "Answers Wiki")
            self.assertEqual(manifest["vars"]["org_name"], "Answers Org")
            self.assertEqual(manifest["vars"]["content_language"], "English")
            self.assertEqual(manifest["vars"]["repo_name"], "answers-wiki")


class AnswersFileMalformedJsonExits2(unittest.TestCase):
    """A --answers-file that is not valid JSON must be routed through the
    same graceful exit-2 refusal as every other invalid-input path in
    init.py (resolve_target_refusal(), missing_vars_message()) -- never an
    unhandled json.JSONDecodeError traceback, and nothing gets written."""

    def test_answers_file_malformed_json_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_text("{not valid json", encoding="utf-8")

            args = [sys.executable, str(INIT_PY), str(target),
                    "--answers-file", str(answers_path), "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(str(answers_path), result.stderr)
            self.assertFalse(target.exists())


class AnswersFileMissingPathExits2(unittest.TestCase):
    """A --answers-file path that does not exist on disk must be routed
    through the same graceful exit-2 refusal -- never an unhandled
    FileNotFoundError traceback, and nothing gets written."""

    def test_answers_file_missing_path_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            answers_path = Path(tmp) / "does-not-exist.json"

            args = [sys.executable, str(INIT_PY), str(target),
                    "--answers-file", str(answers_path), "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(str(answers_path), result.stderr)
            self.assertFalse(target.exists())


class AnswersFileNonObjectTopLevelExits2(unittest.TestCase):
    """A --answers-file whose JSON top level parses fine but is not an
    object (a JSON array, in this case) must be routed through the same
    graceful exit-2 refusal -- never an unhandled AttributeError traceback
    from merge_answers() calling .get() on a list, and nothing gets
    written."""

    def test_answers_file_non_object_top_level_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

            args = [sys.executable, str(INIT_PY), str(target),
                    "--answers-file", str(answers_path), "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(target.exists())


class AnswersFileNonStringRequiredValueExits2(unittest.TestCase):
    """A --answers-file value for a required variable that parses as valid
    JSON but is not a JSON string (a JSON number, here) must be refused,
    not silently accepted and persisted as a non-string type -- the CLI
    flag path is argparse-guaranteed to always supply a str for the same
    variable, so the file path must guarantee the same shape."""

    def test_answers_file_non_string_required_value_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_text(json.dumps({
                "wiki_title": 12345,
                "org_name": "Sample Org",
                "content_language": "English",
                "repo_name": "sample-wiki",
            }), encoding="utf-8")

            args = [sys.executable, str(INIT_PY), str(target),
                    "--answers-file", str(answers_path), "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("wiki_title", result.stderr)
            self.assertFalse(target.exists())


class AnswersFileNonStringOriginsExits2(unittest.TestCase):
    """A --answers-file 'origins' value that parses as valid JSON but is
    not a string (a JSON array, the natural way to express a list of
    origins in a JSON file) must be refused through the same graceful
    exit-2 refusal as every other malformed --answers-file shape -- never
    an unhandled AttributeError traceback from parse_origins() calling
    .split() on a non-string, and nothing gets written."""

    def test_answers_file_non_string_origins_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_text(json.dumps({
                "wiki_title": "Sample Wiki",
                "org_name": "Sample Org",
                "content_language": "English",
                "repo_name": "sample-wiki",
                "origins": ["session", "jira"],
            }), encoding="utf-8")

            args = [sys.executable, str(INIT_PY), str(target),
                    "--answers-file", str(answers_path), "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("origins", result.stderr)
            self.assertFalse(target.exists())


# Regression guard (Skinner finding, init.py:264-267 read_answers_file):
# read_answers_file() caught only `except OSError` around
# Path(path).read_text(encoding="utf-8"), but that call can also raise
# UnicodeDecodeError -- a ValueError subclass, not an OSError subclass --
# so a --answers-file containing bytes that are not valid UTF-8 was NOT
# converted into the documented AnswersFileError/exit-2 refusal; it
# crashed with an unhandled traceback and exit code 1.
class AnswersFileNonUtf8FailsClosed(unittest.TestCase):
    """A --answers-file whose bytes are not valid UTF-8 at all (as opposed
    to AnswersFileMalformedJsonExits2's syntactically invalid-but-UTF-8
    case) raises UnicodeDecodeError, not json.JSONDecodeError or OSError,
    and must be routed through the same graceful exit-2 refusal -- never
    an unhandled traceback -- and nothing gets written."""

    def test_answers_file_non_utf8_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            answers_path = Path(tmp) / "answers.json"
            answers_path.write_bytes(b"\xff\xfe\x80\x81 not valid utf-8 at all")

            args = [sys.executable, str(INIT_PY), str(target),
                    "--answers-file", str(answers_path), "--non-interactive"]
            result = subprocess.run(args, capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL)

            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(str(answers_path), result.stderr)
            self.assertFalse(target.exists())


def _seeded_schema(target):
    """init.py seeds exactly one JSON file into <target>/sources/cards/ --
    located by glob (never a hardcoded filename literal) so this suite
    never has to name the schema's on-disk filename, matching the rest of
    this file's fixture-only sourcing discipline (test_genericity.py's
    SyntheticFixtureNotOgpCorpus)."""
    [schema_path] = list((target / "sources/cards").glob("*.json"))
    return json.loads(schema_path.read_text(encoding="utf-8"))


class OriginsFlagSeedsSchemaEnum(unittest.TestCase):
    def test_origins_flag_seeds_schema_enum(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target, extra_args=("--origins", "session,jira,slack"))
            self.assertEqual(result.returncode, 0, result.stderr)

            schema = _seeded_schema(target)
            self.assertEqual(schema["keys"]["origin"]["enum"], ["session", "jira", "slack"])


class OriginsDefaultIsSessionOnly(unittest.TestCase):
    def test_origins_default_is_session_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "wiki"
            result = _run_init(target)
            self.assertEqual(result.returncode, 0, result.stderr)

            schema = _seeded_schema(target)
            self.assertEqual(schema["keys"]["origin"]["enum"], ["session"])


# Regression guard (T31A, init.py:471-481 dry_run_hooks): step 13 exec'd
# both git hooks with a target-RELATIVE program path while also passing
# cwd=target, so a relative --target argument doubled the target name and
# crashed with FileNotFoundError -- the most natural invocation shape a
# user would type (`cd /tmp && python3 init.py my-wiki ...`) was broken by
# accident of how the caller happened to spell the path.
class InitRelativeTargetSucceeds(unittest.TestCase):
    """Drives init.py's own main() entry point in-process with a bare
    relative target name, from a controlled working directory (a
    TemporaryDirectory chdir'd into, with the previous cwd restored in
    `finally` regardless of outcome) -- exactly the invocation shape the
    doubled-path bug broke."""

    def test_init_relative_target_succeeds(self):
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                exit_code = init_module.main(
                    ["relative-wiki", *VARS_ARGS, "--non-interactive"])
            finally:
                os.chdir(original_cwd)

            self.assertEqual(exit_code, 0)
            scaffold = Path(tmp) / "relative-wiki"
            self.assertTrue((scaffold / ".git").is_dir())
            self.assertTrue((scaffold / ".githooks" / "commit-msg").is_file())


class DryRunHooksExecsAbsoluteProgramPaths(unittest.TestCase):
    """Pins dry_run_hooks' subprocess seam directly: the argument vector's
    program path (argv[0]) for BOTH the commit-msg call and the pre-commit
    call must always be an absolute path pointing at the real hook file,
    regardless of whether the caller spelled `target` as a relative or an
    absolute path -- so the fix is pinned at the unit level and cannot
    silently regress if step 13 is refactored."""

    def _dry_run_hooks_argv0s(self, target):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        git_ok = subprocess.CompletedProcess([], 0)
        with mock.patch.object(init_module, "_git", return_value=git_ok), \
             mock.patch.object(init_module.subprocess, "run", side_effect=fake_run):
            result = init_module.dry_run_hooks(target, "chore: test subject")

        self.assertTrue(result)
        self.assertEqual(len(calls), 2)
        commit_msg_argv, pre_commit_argv = calls
        return Path(commit_msg_argv[0]), Path(pre_commit_argv[0])

    def test_absolute_program_path_for_relative_target(self):
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                relative_target = Path("wiki-instance")
                commit_msg_path, pre_commit_path = self._dry_run_hooks_argv0s(
                    relative_target)
                expected_root = (Path(tmp) / "wiki-instance").resolve()
            finally:
                os.chdir(original_cwd)

        self.assertTrue(commit_msg_path.is_absolute(), commit_msg_path)
        self.assertEqual(commit_msg_path.resolve(),
                         expected_root / ".githooks" / "commit-msg")
        self.assertTrue(pre_commit_path.is_absolute(), pre_commit_path)
        self.assertEqual(pre_commit_path.resolve(),
                         expected_root / ".githooks" / "pre-commit")

    def test_absolute_program_path_for_absolute_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            absolute_target = Path(tmp) / "wiki-instance"
            commit_msg_path, pre_commit_path = self._dry_run_hooks_argv0s(
                absolute_target)
            expected_root = absolute_target.resolve()

        self.assertTrue(commit_msg_path.is_absolute(), commit_msg_path)
        self.assertEqual(commit_msg_path.resolve(),
                         expected_root / ".githooks" / "commit-msg")
        self.assertTrue(pre_commit_path.is_absolute(), pre_commit_path)
        self.assertEqual(pre_commit_path.resolve(),
                         expected_root / ".githooks" / "pre-commit")


if __name__ == "__main__":
    unittest.main()


class SummaryNamesTheRunningVersion(unittest.TestCase):
    """v1.0.2 regression guard. `summary_text`'s bypass warning used to
    embed the literal string "wiki-harness v1.0.0", so every wiki
    scaffolded from a later release was told the wrong version -- inside
    the one message that warns about a security limitation. The version
    must come from the library's own VERSION file, the way
    commit_subject(version) already takes it."""

    def test_summary_names_the_version_it_is_given(self):
        text = init_module.summary_text(Path("/tmp/some-wiki"), "abc123def456", "9.9.9")
        self.assertIn("wiki-harness v9.9.9", text)

    def test_summary_never_hardcodes_a_version(self):
        """Any literal release number left in the module's own source is
        the defect restated -- the summary must interpolate, never quote."""
        text = init_module.summary_text(Path("/tmp/some-wiki"), "abc123def456", "9.9.9")
        self.assertNotIn("v1.0.0", text)
        self.assertNotIn("v1.0.1", text)

    def test_scaffold_summary_reports_the_library_version(self):
        """End to end: the summary a real scaffold prints names whatever
        VERSION currently holds."""
        expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_init(Path(tmp) / "version-summary-wiki")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"wiki-harness v{expected}", result.stdout)
