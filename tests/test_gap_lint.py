from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gap_ledger  # noqa: E402
import gap_lint  # noqa: E402

SCHEMA_TEXT = (ROOT / "templates" / "gap-schema.default.json").read_text(encoding="utf-8")


def _git(root, *args):
    """Isolated exactly like init.py's/test_init.py's own _git() helper: the
    host's global/system gitconfig (commit.gpgsign=true with no usable key,
    an unusual default branch name, etc.) must never change whether these
    assertions hold."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, env=env)


def _init_repo(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "hunter@example.com")
    _git(root, "config", "user.name", "Hunter")


def gap_record(gid="gap-2024-01-15-001"):
    return {
        "type": "gap", "id": gid, "at": "2024-01-15T09:00:00+00:00",
        "service": "example-service", "session": "0000-session",
        "topics": ["concurrency"], "context": "reading a worker loop",
        "prompt_verbatim": "whats a channel",
        "question": "what is the difference between goroutines and channels in Go?",
        "wiki_answer": "no page covers this", "answer_given": "from general knowledge",
    }


def ledger_text(*records):
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)


def inputs(**overrides):
    records, _ = gap_ledger.parse_ledger(overrides.get("ledger_text", ""))
    base = dict(
        ledger_text=overrides.get("ledger_text", ""),
        view_text=gap_ledger.render_view(records),
        schema_text=SCHEMA_TEXT,
        head_bytes=b"",
        work_bytes=overrides.get("ledger_text", "").encode("utf-8"),
        index_bytes=overrides.get("ledger_text", "").encode("utf-8"),
        deleted_lines=0,
        git_error=None,
        card_ids=frozenset(),
        page_paths=frozenset(),
    )
    base.update(overrides)
    return gap_lint.GapInputs(**base)


def codes(findings):
    return sorted({f.code for f in findings})


class AbsentLedgerIsClean(unittest.TestCase):
    def test_no_ledger_no_findings(self):
        self.assertEqual(gap_lint.check_gaps(inputs()), [])


class L1Parsing(unittest.TestCase):
    def test_unparseable_line_is_an_error(self):
        findings = gap_lint.check_gaps(inputs(ledger_text="{nope\n"))
        self.assertIn("GAP", codes(findings))
        self.assertTrue(all(f.severity == "ERROR" for f in findings))

    def test_missing_trailing_newline_is_an_error(self):
        text = json.dumps(gap_record(), sort_keys=True)
        self.assertTrue(any("newline" in f.message
                            for f in gap_lint.check_gaps(inputs(ledger_text=text))))


class L2L3SchemaAndIds(unittest.TestCase):
    def test_undeclared_key_is_an_error(self):
        rec = gap_record()
        rec["priority"] = "high"
        text = ledger_text(rec)
        findings = gap_lint.check_gaps(inputs(ledger_text=text, work_bytes=text.encode()))
        self.assertTrue(any("priority" in f.message for f in findings))

    def test_malformed_schema_is_its_own_error(self):
        findings = gap_lint.check_gaps(inputs(schema_text="{broken"))
        self.assertIn("GAP_SCHEMA", codes(findings))


class L5ReferenceTargets(unittest.TestCase):
    def build(self, card, page):
        res = {"type": "resolution", "gap": "gap-2024-01-15-001",
               "at": "2024-01-16T09:00:00+00:00", "card": card, "wiki_page": page}
        text = ledger_text(gap_record(), res)
        records, _ = gap_ledger.parse_ledger(text)
        return inputs(ledger_text=text, work_bytes=text.encode(),
                      view_text=gap_ledger.render_view(records),
                      card_ids=frozenset({"src-2024-01-16-001"}),
                      page_paths=frozenset({"wiki/widget-assembly.md"}))

    def test_existing_card_and_page_pass(self):
        found = self.build("src-2024-01-16-001", "wiki/widget-assembly.md")
        self.assertEqual(gap_lint.check_gaps(found), [])

    def test_missing_card_is_an_error(self):
        found = self.build("src-2099-01-01-001", "wiki/widget-assembly.md")
        self.assertTrue(any("src-2099-01-01-001" in f.message
                            for f in gap_lint.check_gaps(found)))

    def test_missing_page_is_an_error(self):
        found = self.build("src-2024-01-16-001", "wiki/nope.md")
        self.assertTrue(any("wiki/nope.md" in f.message
                            for f in gap_lint.check_gaps(found)))


class L6AppendOnly(unittest.TestCase):
    """V2. One case per row of the spec's attack table."""

    def setUp(self):
        self.a = ledger_text(gap_record("gap-2024-01-15-001"))
        self.b = ledger_text(gap_record("gap-2024-01-15-001"),
                             gap_record("gap-2024-01-15-002"))

    def violation(self, head, work):
        return gap_ledger.append_only_violation(head, work)

    def test_append_is_allowed(self):
        self.assertIsNone(self.violation(self.a.encode(), self.b.encode()))

    def test_identical_is_allowed(self):
        self.assertIsNone(self.violation(self.a.encode(), self.a.encode()))

    def test_first_commit_with_no_head_is_allowed(self):
        self.assertIsNone(self.violation(b"", self.b.encode()))

    def test_delete_the_last_line(self):
        self.assertIsNotNone(self.violation(self.b.encode(), self.a.encode()))

    def test_delete_a_middle_line(self):
        head = ledger_text(gap_record("gap-2024-01-15-001"),
                           gap_record("gap-2024-01-15-002"),
                           gap_record("gap-2024-01-15-003"))
        work = ledger_text(gap_record("gap-2024-01-15-001"),
                           gap_record("gap-2024-01-15-003"))
        self.assertIsNotNone(self.violation(head.encode(), work.encode()))

    def test_truncate_to_empty(self):
        self.assertIsNotNone(self.violation(self.a.encode(), b""))

    def test_delete_the_file_and_rewrite_it(self):
        """The failure actually observed in the wild: an agent replaces the
        whole file with its own entries."""
        fresh = ledger_text(gap_record("gap-2024-06-01-001"))
        self.assertIsNotNone(self.violation(self.b.encode(), fresh.encode()))

    def test_reorder_lines(self):
        reordered = ledger_text(gap_record("gap-2024-01-15-002"),
                                gap_record("gap-2024-01-15-001"))
        self.assertIsNotNone(self.violation(self.b.encode(), reordered.encode()))

    def test_edit_one_byte_in_a_committed_line(self):
        edited = self.a.replace("example-service", "example-servicE")
        self.assertIsNotNone(self.violation(self.a.encode(), edited.encode()))

    def test_violation_surfaces_as_a_lint_error(self):
        found = inputs(ledger_text=self.a, work_bytes=self.a.encode(),
                       head_bytes=self.b.encode())
        self.assertTrue(any(f.code == "GAP_APPEND" for f in gap_lint.check_gaps(found)))

    def test_staged_deletion_count_is_an_independent_error(self):
        """Second mechanism: even if the prefix check somehow passed, a
        staged diff that removes lines is itself the violation."""
        found = inputs(ledger_text=self.a, work_bytes=self.a.encode(),
                       head_bytes=self.a.encode(), deleted_lines=3)
        self.assertTrue(any(f.code == "GAP_APPEND" for f in gap_lint.check_gaps(found)))


class V3FailClosed(unittest.TestCase):
    """VISION.md records the exact bug this guards: git_changes returns an
    empty change list when git fails, so 'unknown' reads as 'no changes'
    and a tampered file passes. A git error must ERROR, never pass."""

    def test_git_error_is_an_error_not_silence(self):
        findings = gap_lint.check_gaps(inputs(git_error="fatal: not a git repository"))
        self.assertTrue(findings)
        self.assertTrue(all(f.severity == "ERROR" for f in findings))
        self.assertIn("GAP_APPEND", codes(findings))


class L7ViewSync(unittest.TestCase):
    def test_stale_view_is_an_error(self):
        text = ledger_text(gap_record())
        found = inputs(ledger_text=text, work_bytes=text.encode(),
                       view_text="# Knowledge gaps\n\nstale\n")
        self.assertTrue(any(f.code == "GAP_VIEW" for f in gap_lint.check_gaps(found)))

    def test_fresh_view_passes(self):
        text = ledger_text(gap_record())
        records, _ = gap_ledger.parse_ledger(text)
        found = inputs(ledger_text=text, work_bytes=text.encode(),
                       view_text=gap_ledger.render_view(records))
        self.assertEqual(gap_lint.check_gaps(found), [])


class RunDeleteGapsFolderRegression(unittest.TestCase):
    """Finding 1 (Critical): the observed attack is an agent deleting the
    WHOLE gaps/ folder (ledger + schema together), not just rewriting the
    ledger. run()'s old guard -- 'no ledger text AND no schema text' -- reads
    that as 'never adopted' and returns [] with no findings at all, silently
    discarding both the tampered-history evidence and any git error. This
    test commits a ledger, deletes gaps/ entirely from the working tree, and
    asserts run() still reports the append-only violation. It must FAIL
    against the pre-fix guard and PASS after the HEAD-based fix."""

    def test_deleting_ledger_and_schema_is_still_caught_by_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            gaps_dir = root / "gaps"
            gaps_dir.mkdir()
            text = ledger_text(gap_record())
            (gaps_dir / "knowledge-gaps.jsonl").write_text(text, encoding="utf-8")
            (gaps_dir / "gap-schema.json").write_text(SCHEMA_TEXT, encoding="utf-8")
            records, _ = gap_ledger.parse_ledger(text)
            (gaps_dir / "KNOWLEDGE_GAP.md").write_text(
                gap_ledger.render_view(records), encoding="utf-8")
            add = _git(root, "add", "-A")
            self.assertEqual(add.returncode, 0, add.stderr)
            commit = _git(root, "commit", "-q", "-m", "seed ledger")
            self.assertEqual(commit.returncode, 0, commit.stderr)

            # The attack: delete the whole gaps/ folder from the working tree
            # (not staged -- run() judges the working tree against HEAD).
            for name in ("knowledge-gaps.jsonl", "gap-schema.json", "KNOWLEDGE_GAP.md"):
                (gaps_dir / name).unlink()

            findings = gap_lint.run(root)
            self.assertNotEqual(findings, [],
                "run() must not return [] once a ledger has been committed "
                "and then deleted -- that silently discards the tampering")
            self.assertTrue(any(f.code == "GAP_APPEND" for f in findings))


class GatherAndRunAgainstRealGit(unittest.TestCase):
    """Finding 2: exercise the impure edge (gather/run/_git_bytes/
    _staged_deletions) against a real git repository, not just the pure
    check_gaps() the rest of this file drives."""

    def test_never_adopted_repo_returns_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            self.assertEqual(
                _git(root, "commit", "-q", "-m", "init").returncode, 0)
            self.assertEqual(gap_lint.run(root), [])

    def test_untampered_committed_ledger_returns_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "sources" / "cards").mkdir(parents=True)
            (root / "wiki").mkdir()
            gaps_dir = root / "gaps"
            gaps_dir.mkdir()
            text = ledger_text(gap_record())
            (gaps_dir / "knowledge-gaps.jsonl").write_text(text, encoding="utf-8")
            (gaps_dir / "gap-schema.json").write_text(SCHEMA_TEXT, encoding="utf-8")
            records, _ = gap_ledger.parse_ledger(text)
            (gaps_dir / "KNOWLEDGE_GAP.md").write_text(
                gap_ledger.render_view(records), encoding="utf-8")
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            self.assertEqual(
                _git(root, "commit", "-q", "-m", "seed ledger").returncode, 0)
            self.assertEqual(gap_lint.run(root), [])

    def test_git_bytes_outside_a_git_repo_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = gap_lint._resolve_repo_state(root)
            data, error = gap_lint._git_bytes(root, "gaps/knowledge-gaps.jsonl", state)
            self.assertIsNone(data)
            self.assertIsNotNone(error)

    def test_git_bytes_on_unborn_head_is_not_an_error(self):
        """A repository with `git init` but zero commits has no HEAD at
        all: `git show HEAD:<path>` fails with "invalid object name
        'HEAD'.", not any of the "path not in this revision" messages.
        That is still the legitimate "nothing committed for this path yet"
        case, not a git failure."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            state = gap_lint._resolve_repo_state(root)
            data, error = gap_lint._git_bytes(root, "gaps/knowledge-gaps.jsonl", state)
            self.assertEqual(data, b"")
            self.assertIsNone(error)

    def test_run_on_unborn_head_repo_with_no_gaps_folder_returns_no_findings(self):
        """The regression: init.py's dry_run_hooks runs the pre-commit
        hook (which will call gap_lint.run() once Task 7 wires it in)
        against a freshly staged, never-committed scaffold -- i.e. an
        unborn HEAD. A wiki that has never touched gaps/ must not get a
        spurious finding just because HEAD does not exist yet."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            self.assertEqual(gap_lint.run(root), [])

    def test_staged_deletions_counts_removed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            gaps_dir = root / "gaps"
            gaps_dir.mkdir()
            ledger = gaps_dir / "knowledge-gaps.jsonl"
            ledger.write_text(
                ledger_text(gap_record("gap-2024-01-15-001"),
                            gap_record("gap-2024-01-15-002")),
                encoding="utf-8")
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            self.assertEqual(
                _git(root, "commit", "-q", "-m", "seed").returncode, 0)
            ledger.write_text(ledger_text(gap_record("gap-2024-01-15-001")),
                              encoding="utf-8")
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            state = gap_lint._resolve_repo_state(root)
            deleted, error = gap_lint._staged_deletions(
                root, gap_ledger.LEDGER_PATH, state)
            self.assertIsNone(error)
            self.assertGreaterEqual(deleted, 1)

    def test_git_bytes_path_not_in_head_with_other_commits_present(self):
        """A repository that has real history, but never committed this
        particular path, must still read as (b"", None) -- not confused
        with the truly-unborn case, and not an error."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _init_repo(root)
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            self.assertEqual(
                _git(root, "commit", "-q", "-m", "init").returncode, 0)
            state = gap_lint._resolve_repo_state(root)
            data, error = gap_lint._git_bytes(root, "gaps/knowledge-gaps.jsonl", state)
            self.assertEqual(data, b"")
            self.assertIsNone(error)


class GhostRefBypassAttack(unittest.TestCase):
    """The reviewer's demonstrated bypass, reproduced end to end. Writing
    `ref: refs/heads/ghost` into `.git/HEAD` makes `git show
    HEAD:<path>` fail with the exact same stderr text
    ("fatal: invalid object name 'HEAD'.") as a genuinely unborn
    repository -- even though a real commit with a real, committed
    ledger still exists at refs/heads/main. Stderr-matching code cannot
    tell these two cases apart; this test proves the fix, which never
    reads stderr, can. This test must FAIL against the pre-fix
    `_git_bytes` (stderr substring matching) and PASS after the
    exit-code/count-based redesign."""

    def _seed_committed_ledger(self, root):
        _init_repo(root)
        (root / "sources" / "cards").mkdir(parents=True)
        (root / "wiki").mkdir()
        gaps_dir = root / "gaps"
        gaps_dir.mkdir()
        text = ledger_text(gap_record("gap-2024-01-15-001"))
        (gaps_dir / "knowledge-gaps.jsonl").write_text(text, encoding="utf-8")
        (gaps_dir / "gap-schema.json").write_text(SCHEMA_TEXT, encoding="utf-8")
        records, _ = gap_ledger.parse_ledger(text)
        (gaps_dir / "KNOWLEDGE_GAP.md").write_text(
            gap_ledger.render_view(records), encoding="utf-8")
        self.assertEqual(_git(root, "add", "-A").returncode, 0)
        commit = _git(root, "commit", "-q", "-m", "seed real ledger")
        self.assertEqual(commit.returncode, 0, commit.stderr)

    def test_ghost_ref_bypass_is_caught_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_committed_ledger(root)

            # The attack: point HEAD at a branch ref that was never
            # created. No git command, no privileges -- a single file
            # write. The real commit (and its real ledger) still exists
            # at refs/heads/main; only the HEAD pointer is forged.
            (root / ".git" / "HEAD").write_text(
                "ref: refs/heads/ghost\n", encoding="utf-8")

            # Forge the ledger: replace committed content with a fully
            # schema-valid, fabricated record.
            forged = ledger_text(gap_record("gap-2099-01-01-001"))
            gaps_dir = root / "gaps"
            (gaps_dir / "knowledge-gaps.jsonl").write_text(
                forged, encoding="utf-8")
            forged_records, _ = gap_ledger.parse_ledger(forged)
            (gaps_dir / "KNOWLEDGE_GAP.md").write_text(
                gap_ledger.render_view(forged_records), encoding="utf-8")

            findings = gap_lint.run(root)
            self.assertTrue(
                findings,
                "the ghost-ref bypass must be caught, not silently pass "
                "with []")
            self.assertTrue(all(f.severity == "ERROR" for f in findings))
            self.assertIn("GAP_APPEND", codes(findings))

    def test_bogus_sha_head_is_also_caught(self):
        """The pre-existing 'exists on disk, but not in' phrase was
        exploitable the same way: a bogus 40-hex SHA in .git/HEAD
        produces that exact stderr, already matched as legitimate by the
        old code. Confirm the fix catches this variant too."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_committed_ledger(root)

            bogus_sha = "f" * 40
            (root / ".git" / "HEAD").write_text(bogus_sha + "\n",
                                                encoding="utf-8")

            forged = ledger_text(gap_record("gap-2099-01-01-001"))
            gaps_dir = root / "gaps"
            (gaps_dir / "knowledge-gaps.jsonl").write_text(
                forged, encoding="utf-8")
            forged_records, _ = gap_ledger.parse_ledger(forged)
            (gaps_dir / "KNOWLEDGE_GAP.md").write_text(
                gap_ledger.render_view(forged_records), encoding="utf-8")

            findings = gap_lint.run(root)
            self.assertTrue(findings)
            self.assertTrue(all(f.severity == "ERROR" for f in findings))
            self.assertIn("GAP_APPEND", codes(findings))


class ForgedIndexBypassAttack(unittest.TestCase):
    """C1 (whole-branch review, final pass): the lint used to judge only
    the working tree (`work_bytes`) plus a numstat line-count summary
    (`deleted_lines`). What a commit actually captures is the INDEX, and
    for a blob git treats as binary, `git diff --cached --numstat` prints
    `-\\t-\\t<path>` -- unparseable as a digit, so the old
    `_staged_deletions` fell through to `return 0, None`: clean. These
    tests must FAIL against the pre-fix `gap_lint` (no `index_bytes`
    input, `_staged_deletions` returning 0 on a binary line) and PASS
    after `_staged_bytes`/`_staged_deletions` were made to judge the raw
    staged bytes and fail closed."""

    def _seed_committed_ledger(self, root):
        _init_repo(root)
        (root / "sources" / "cards").mkdir(parents=True)
        (root / "wiki").mkdir()
        gaps_dir = root / "gaps"
        gaps_dir.mkdir()
        text = ledger_text(gap_record("gap-2024-01-15-001"),
                           gap_record("gap-2024-01-16-001"))
        (gaps_dir / "knowledge-gaps.jsonl").write_text(text, encoding="utf-8")
        (gaps_dir / "gap-schema.json").write_text(SCHEMA_TEXT, encoding="utf-8")
        records, _ = gap_ledger.parse_ledger(text)
        (gaps_dir / "KNOWLEDGE_GAP.md").write_text(
            gap_ledger.render_view(records), encoding="utf-8")
        self.assertEqual(_git(root, "add", "-A").returncode, 0)
        commit = _git(root, "commit", "-q", "-m", "seed real ledger")
        self.assertEqual(commit.returncode, 0, commit.stderr)
        return text

    def test_forged_nul_blob_staged_via_update_index_is_caught(self):
        """The reviewer's exact demonstrated bypass: write HEAD's ledger
        with a leading NUL byte to a new blob, and stage THAT blob for the
        ledger path with `git update-index --cacheinfo` -- never touching
        the working tree at all, so the working-tree check alone would
        stay silent, and `git diff --cached --numstat` reports the change
        as binary ('-\\t-\\t<path>'), unparseable as a digit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head_text = self._seed_committed_ledger(root)

            forged_path = root / "forged.bin"
            forged_path.write_bytes(b"\x00" + head_text.encode("utf-8"))
            hash_object = _git(root, "hash-object", "-w", str(forged_path))
            self.assertEqual(hash_object.returncode, 0, hash_object.stderr)
            blob = hash_object.stdout.strip()

            cacheinfo = "100644,{},{}".format(blob, gap_ledger.LEDGER_PATH)
            update = _git(root, "update-index", "--cacheinfo", cacheinfo)
            self.assertEqual(update.returncode, 0, update.stderr)

            # Confirm the exact reviewer-observed numstat shape before
            # asserting the fix -- this is the bypass's root cause, not
            # incidental to it.
            numstat = _git(root, "diff", "--cached", "--numstat", "--",
                           gap_ledger.LEDGER_PATH)
            self.assertEqual(numstat.stdout.strip(),
                             "-\t-\t{}".format(gap_ledger.LEDGER_PATH))

            findings = gap_lint.run(root)
            self.assertTrue(
                findings,
                "a forged binary blob staged for the ledger must be "
                "caught, not silently pass with []")
            self.assertTrue(all(f.severity == "ERROR" for f in findings))
            self.assertIn("GAP_APPEND", codes(findings))

    def test_gitattributes_diff_marker_plus_staged_line_removal_is_caught(self):
        """The second trigger the review names: mark the ledger `-diff` in
        `.gitattributes` (committed, so it is honoured), stage a line
        removal, then restore the working tree so ONLY the index differs
        from HEAD. If the fix judged the working tree alone this would
        pass; the index still carries the shrunk content."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head_text = self._seed_committed_ledger(root)

            (root / ".gitattributes").write_text(
                "{} -diff\n".format(gap_ledger.LEDGER_PATH), encoding="utf-8")
            self.assertEqual(_git(root, "add", "-A").returncode, 0)
            attr_commit = _git(root, "commit", "-q", "-m", "mark ledger -diff")
            self.assertEqual(attr_commit.returncode, 0, attr_commit.stderr)

            ledger_path = root / gap_ledger.LEDGER_PATH
            shrunk = "".join(head_text.splitlines(keepends=True)[:1])
            ledger_path.write_text(shrunk, encoding="utf-8")
            self.assertEqual(_git(root, "add", "--", gap_ledger.LEDGER_PATH).returncode, 0)

            # Confirm '-diff' really did make numstat binary/unparseable,
            # then restore the working tree so only the INDEX still
            # differs from HEAD -- the wedge the review describes: the
            # working-tree check alone now sees no divergence at all.
            numstat = _git(root, "diff", "--cached", "--numstat", "--",
                           gap_ledger.LEDGER_PATH)
            self.assertEqual(numstat.stdout.strip(),
                             "-\t-\t{}".format(gap_ledger.LEDGER_PATH))
            ledger_path.write_text(head_text, encoding="utf-8")

            findings = gap_lint.run(root)
            self.assertTrue(
                findings,
                "a staged line-removal hidden behind a '-diff' attribute "
                "must be caught even when the working tree was restored")
            self.assertTrue(all(f.severity == "ERROR" for f in findings))
            self.assertIn("GAP_APPEND", codes(findings))

    def test_ordinary_commit_touching_unrelated_file_is_still_clean(self):
        """The false-positive guard for the 'committed ledger present in
        HEAD but not staged' decision: staging an unrelated file while the
        ledger itself is untouched (working tree AND index both still
        exactly what HEAD committed) must produce no gap findings at
        all."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_committed_ledger(root)

            (root / "README.md").write_text("routine tidy\n", encoding="utf-8")
            self.assertEqual(_git(root, "add", "--", "README.md").returncode, 0)

            findings = gap_lint.run(root)
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
