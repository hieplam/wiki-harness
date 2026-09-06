"""Tests for bin/wiki-harness -- the installed launcher.

The launcher's whole job is deciding WHICH release to run and materialising
it; the harness logic lives in the payload it execs. So the decisions are
pure and tested directly, and the edges are tested for the way they fail:
this runs on someone's machine against the network, and every failure mode
here is one a person meets with no stack trace to read.

No test in this module touches the network. `fetch_latest` and the
downloader are injected seams; the one end-to-end test builds a real payload
with tools/build_release.py and serves it from a local directory.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "bin" / "wiki-harness"

# The launcher has no .py suffix -- it is what lands on PATH -- so the
# loader has to be named explicitly; spec_from_file_location() alone returns
# None for an extensionless file.
_spec = importlib.util.spec_from_file_location(
    "wiki_harness_launcher", LAUNCHER,
    loader=importlib.machinery.SourceFileLoader("wiki_harness_launcher",
                                                str(LAUNCHER)))
launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launcher)


class CommandLineParsing(unittest.TestCase):
    """Everything after the subcommand is passed through untouched, so a
    new init.py/upgrade.py flag needs no launcher change."""

    def test_init_passes_every_flag_through(self):
        parsed = launcher.parse_cli(
            ["init", "immigration-wiki", "--wiki-title", "Immigration Wiki",
             "--non-interactive"])

        self.assertEqual(parsed.subcommand, "init")
        self.assertEqual(parsed.passthrough,
                         ["immigration-wiki", "--wiki-title",
                          "Immigration Wiki", "--non-interactive"])

    def test_harness_version_is_consumed_by_the_launcher(self):
        """--harness-version selects the release; it must not reach the
        payload, which has never heard of it."""
        parsed = launcher.parse_cli(
            ["init", "w", "--harness-version", "1.2.0", "--wiki-title", "X"])

        self.assertEqual(parsed.pinned, "1.2.0")
        self.assertNotIn("--harness-version", parsed.passthrough)
        self.assertEqual(parsed.passthrough, ["w", "--wiki-title", "X"])

    def test_the_raw_spelling_is_preserved_for_the_error_message(self):
        """parse_cli only splits argv; main() validates, so it can name the
        user's exact spelling when refusing."""
        self.assertEqual(
            launcher.parse_cli(["init", "--harness-version", "v1.2.0"]).pinned,
            "v1.2.0")

    def test_upgrade_exposes_its_target_version(self):
        parsed = launcher.parse_cli(
            ["upgrade", "~/wiki", "--to", "1.3.0", "--apply"])

        self.assertEqual(parsed.subcommand, "upgrade")
        self.assertEqual(parsed.to_version, "1.3.0")
        self.assertIn("--apply", parsed.passthrough)

    def test_upgrade_sees_the_to_flag_in_either_spelling(self):
        """upgrade.py takes v1.3.0 or 1.3.0; the launcher must recognise
        both as naming a version, and normalise_version() is what settles
        the form before a release is addressed."""
        for spelling in ("1.3.0", "v1.3.0", "--to=v1.3.0"):
            with self.subTest(spelling=spelling):
                argv = (["upgrade", "w", spelling] if spelling.startswith("--")
                        else ["upgrade", "w", "--to", spelling])
                raw = launcher.parse_cli(argv).to_version

                self.assertIsNotNone(raw)
                self.assertEqual(launcher.normalise_version(raw), "1.3.0")

    def test_an_unknown_subcommand_is_refused_not_passed_on(self):
        parsed = launcher.parse_cli(["frobnicate", "--wiki-title", "X"])

        self.assertIsNone(parsed.subcommand)


class VersionSelection(unittest.TestCase):
    """Which release each command needs. Pure: the caller supplies what the
    network said, so no test here waits on GitHub."""

    def test_init_takes_the_newest_release(self):
        self.assertEqual(
            launcher.select_version("init", pinned=None, to_version=None,
                                    latest="1.3.0"),
            "1.3.0")

    def test_upgrade_takes_the_version_it_was_told_to(self):
        """`--to 1.3.0` means 1.3.0, never latest -- the whole point of
        naming it."""
        self.assertEqual(
            launcher.select_version("upgrade", pinned=None, to_version="1.3.0",
                                    latest="1.9.9"),
            "1.3.0")

    def test_upgrade_check_without_to_uses_the_newest(self):
        """`upgrade <target> --check` names no version; it reports what is
        available, so it runs on the newest."""
        self.assertEqual(
            launcher.select_version("upgrade", pinned=None, to_version=None,
                                    latest="1.3.0"),
            "1.3.0")

    def test_a_pin_beats_everything(self):
        self.assertEqual(
            launcher.select_version("upgrade", pinned="1.1.0",
                                    to_version="1.3.0", latest="1.9.9"),
            "1.1.0")
        self.assertEqual(
            launcher.select_version("init", pinned="1.1.0", to_version=None,
                                    latest="1.9.9"),
            "1.1.0")


class ReleaseAddressing(unittest.TestCase):
    def test_the_asset_url_matches_what_the_workflow_uploads(self):
        url = launcher.asset_url("1.2.1")

        self.assertTrue(url.startswith("https://github.com/"), url)
        self.assertIn("/releases/download/v1.2.1/", url)
        self.assertTrue(url.endswith("wiki-harness-1.2.1.tar.gz"), url)

    def test_the_checksum_url_sits_beside_the_asset(self):
        self.assertEqual(launcher.checksum_url("1.2.1"),
                         launcher.asset_url("1.2.1") + ".sha256")

    def test_the_latest_tag_is_read_from_the_releases_api(self):
        payload = json.dumps({"tag_name": "v1.4.2", "name": "v1.4.2"})

        self.assertEqual(launcher.parse_latest_tag(payload), "1.4.2")

    def test_a_latest_response_without_a_tag_is_refused(self):
        for broken in ("{}", "[]", "not json", '{"tag_name": "nightly"}'):
            with self.subTest(broken=broken):
                self.assertIsNone(launcher.parse_latest_tag(broken))

    def test_each_version_caches_under_its_own_directory(self):
        root = Path("/cache")

        self.assertEqual(launcher.cache_dir_for(root, "1.2.1"),
                         root / "releases" / "1.2.1")
        self.assertNotEqual(launcher.cache_dir_for(root, "1.2.1"),
                            launcher.cache_dir_for(root, "1.3.0"))


class ArchiveSafety(unittest.TestCase):
    """A tarball is untrusted input. It is fetched over TLS from a release
    the checksum pins, but the unpacker must still refuse to write outside
    the directory it was given -- the guarantee has to hold on its own."""

    def test_members_that_escape_the_root_are_rejected(self):
        for name in ("../evil", "/etc/passwd", "a/../../evil",
                     "wiki-harness-1.2.1/../../evil"):
            with self.subTest(name=name):
                self.assertFalse(launcher.is_safe_member(name), name)

    def test_ordinary_members_are_accepted(self):
        for name in ("wiki-harness-1.2.1/init.py",
                     "wiki-harness-1.2.1/scripts/lint.py",
                     "wiki-harness-1.2.1"):
            with self.subTest(name=name):
                self.assertTrue(launcher.is_safe_member(name), name)

    def test_an_escaping_member_aborts_the_unpack(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            archive = tmp / "evil.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                data = b"pwned\n"
                info = tarfile.TarInfo("../escaped.txt")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

            with self.assertRaises(launcher.LauncherError):
                launcher.unpack(archive, tmp / "dest")

            self.assertFalse((tmp / "escaped.txt").exists())


class ChecksumVerification(unittest.TestCase):
    def test_a_matching_checksum_passes(self):
        digest = hashlib.sha256(b"payload").hexdigest()

        self.assertIsNone(launcher.checksum_refusal(
            f"{digest}  wiki-harness-1.2.1.tar.gz", b"payload", "1.2.1"))

    def test_a_mismatch_names_both_digests(self):
        message = launcher.checksum_refusal(
            "0" * 64 + "  wiki-harness-1.2.1.tar.gz", b"payload", "1.2.1")

        self.assertIsNotNone(message)
        self.assertIn("0" * 64, message)
        self.assertIn(hashlib.sha256(b"payload").hexdigest(), message)

    def test_an_unreadable_checksum_file_is_a_refusal_not_a_pass(self):
        """Fail closed: an empty or malformed checksum must never be read
        as 'nothing to verify'."""
        for broken in ("", "   ", "not-a-digest  file"):
            with self.subTest(broken=broken):
                self.assertIsNotNone(
                    launcher.checksum_refusal(broken, b"payload", "1.2.1"))


class OfflineAndMissingReleases(unittest.TestCase):
    """The failures a person actually meets."""

    def test_a_version_with_no_published_asset_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fetch_fails(url):
                raise launcher.LauncherError(f"404 fetching {url}")

            with self.assertRaises(launcher.LauncherError) as caught:
                launcher.ensure_release("1.0.0", Path(tmp), fetch=fetch_fails)

            self.assertIn("1.0.0", str(caught.exception))

    def test_a_cached_release_needs_no_network_at_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp)
            payload = launcher.cache_dir_for(cache_root, "1.2.1")
            payload.mkdir(parents=True)
            (payload / "init.py").write_text("# init\n", encoding="utf-8")

            def fetch_explodes(url):
                raise AssertionError(f"network touched for a cached release: {url}")

            self.assertEqual(
                launcher.ensure_release("1.2.1", cache_root, fetch=fetch_explodes),
                payload)


class LauncherRefusesCleanly(unittest.TestCase):
    """Every failure exits non-zero with one line. A traceback out of a
    command on someone's PATH is a crash, not a verdict."""

    def _run(self, *args, env=None):
        environ = dict(os.environ)
        environ["WIKI_HARNESS_CACHE"] = env or "/nonexistent-cache"
        return subprocess.run([sys.executable, str(LAUNCHER), *args],
                              capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60,
                              env=environ)

    def test_no_arguments_prints_usage_and_exits_2(self):
        result = self._run()

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("init", result.stdout + result.stderr)
        self.assertIn("upgrade", result.stdout + result.stderr)

    def test_an_unknown_subcommand_names_the_real_ones(self):
        result = self._run("frobnicate")

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("frobnicate", result.stderr)

    def test_version_reports_without_touching_the_network(self):
        result = self._run("--version")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(launcher.LAUNCHER_VERSION, result.stdout)

    def test_a_v_prefixed_pin_resolves_to_the_cached_release(self):
        """`--harness-version v1.2.0` must be understood, not refused, and
        must resolve to the same cache entry as the bare spelling. Seeded
        cache, so this proves the whole path with no network."""
        with tempfile.TemporaryDirectory() as tmp:
            payload = launcher.cache_dir_for(Path(tmp), "1.2.0")
            payload.mkdir(parents=True)
            (payload / "init.py").write_text(
                "import sys; print('payload ran'); sys.exit(0)\n",
                encoding="utf-8")

            result = self._run("init", "w", "--harness-version", "v1.2.0",
                               "--wiki-title", "X", env=tmp)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("payload ran", result.stdout)
            self.assertNotIn("not a release version", result.stderr)

    def test_a_malformed_harness_version_is_refused_before_any_fetch(self):
        result = self._run("init", "w", "--harness-version", "latest",
                           "--wiki-title", "X")

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("latest", result.stderr)


class EndToEndAgainstARealPayload(unittest.TestCase):
    """Builds the real payload, serves it from a local file:// URL, and
    drives the launcher end to end -- cache miss, then cache hit."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.version = (ROOT / "VERSION").read_text(encoding="utf-8").split()[0]
        built = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_release.py"),
             "--tag", f"v{cls.version}", "--out-dir", str(tmp / "dist")],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        assert built.returncode == 0, built.stderr
        cls.dist = tmp / "dist"
        cls.cache = tmp / "cache"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _local_fetch(self):
        """Stands in for the GitHub download: same interface, local bytes."""
        def fetch(url):
            name = url.rsplit("/", 1)[-1]
            path = self.dist / name
            if not path.is_file():
                raise launcher.LauncherError(f"no such asset: {name}")
            return path.read_bytes()
        return fetch

    def test_a_cache_miss_downloads_verifies_and_unpacks(self):
        payload = launcher.ensure_release(self.version, self.cache,
                                          fetch=self._local_fetch())

        self.assertTrue((payload / "init.py").is_file())
        self.assertTrue((payload / "scripts" / "lint.py").is_file())
        self.assertTrue((payload / "RELEASE.json").is_file())

    def test_a_corrupted_download_is_refused_and_leaves_no_cache(self):
        """A half-verified payload must never be left behind for the next
        run to pick up as a cache hit."""
        cache = self.cache.parent / "corrupt-cache"

        def corrupt_fetch(url):
            if url.endswith(".sha256"):
                return self._local_fetch()(url)
            return b"this is not the payload"

        with self.assertRaises(launcher.LauncherError) as caught:
            launcher.ensure_release(self.version, cache, fetch=corrupt_fetch)

        self.assertIn("checksum", str(caught.exception).lower())
        self.assertFalse(launcher.cache_dir_for(cache, self.version).exists())

    def test_the_launcher_scaffolds_a_wiki_through_the_payload(self):
        """The headline command, running the payload's own init.py."""
        payload = launcher.ensure_release(self.version, self.cache,
                                          fetch=self._local_fetch())
        target = Path(self._tmp.name) / "immigration-wiki"

        result = subprocess.run(
            [sys.executable, str(payload / "init.py"), str(target),
             "--wiki-title", "Immigration Wiki", "--non-interactive"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=180)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("lint: 0 error(s), 0 warning(s)", result.stdout)


if __name__ == "__main__":
    unittest.main()


class RequestHeaders(unittest.TestCase):
    """Regression: one Accept header was sent for every request, including
    the JSON API call, and GitHub answers `Accept: application/octet-stream`
    on /releases/latest with 415 Unsupported Media Type. Every `init` failed
    at the very first step:

        wiki-harness: 415 fetching
        https://api.github.com/repos/hieplam/wiki-harness/releases/latest

    Only an end-to-end run against the real API could show this -- the
    seams every other test injects skip http_get() entirely.
    """

    def _captured_request(self, url, **kwargs):
        seen = {}

        class FakeResponse:
            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            seen["url"] = request.full_url
            seen["headers"] = {k.lower(): v
                               for k, v in request.header_items()}
            seen["timeout"] = timeout
            return FakeResponse()

        with patch.object(launcher.urllib.request, "urlopen",
                          side_effect=fake_urlopen):
            launcher.http_get(url, **kwargs)
        return seen

    def test_the_json_api_asks_for_json(self):
        seen = self._captured_request(launcher.RELEASES_API,
                                      accept=launcher.ACCEPT_JSON)

        self.assertIn("github", seen["headers"]["accept"])
        self.assertIn("json", seen["headers"]["accept"])
        self.assertNotIn("octet-stream", seen["headers"]["accept"])

    def test_an_asset_download_asks_for_bytes(self):
        seen = self._captured_request(launcher.asset_url("1.3.0"))

        self.assertEqual(seen["headers"]["accept"], "application/octet-stream")

    def test_fetch_latest_version_uses_the_json_accept(self):
        """The specific call that 415'd."""
        seen = {}

        def fake_fetch(url, accept=None):
            seen["url"] = url
            seen["accept"] = accept
            return b'{"tag_name": "v1.3.0"}'

        self.assertEqual(launcher.fetch_latest_version(fetch=fake_fetch),
                         "1.3.0")
        self.assertEqual(seen["url"], launcher.RELEASES_API)
        self.assertIn("json", (seen["accept"] or ""))

    def test_every_request_carries_a_timeout(self):
        seen = self._captured_request(launcher.asset_url("1.3.0"))

        self.assertEqual(seen["timeout"], launcher.NETWORK_TIMEOUT)
