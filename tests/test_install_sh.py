"""End-to-end tests for install.sh, the script people pipe into a shell.

It is verified against a REAL payload built by tools/build_release.py and
served over a real local HTTP server, driven through `sh` exactly as a user
would run it -- only WIKI_HARNESS_API_LATEST / WIKI_HARNESS_DOWNLOAD_BASE
point at the local server instead of GitHub, and HOME points at a throwaway
directory so nothing touches the developer's machine.

Skipped when `sh` or `curl` is unavailable.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT / "install.sh"

HAVE_SHELL = bool(shutil.which("sh") and shutil.which("curl"))


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: A003 - silence the test output
        pass


@unittest.skipUnless(HAVE_SHELL, "sh and curl are required")
class InstallScriptEndToEnd(unittest.TestCase):
    """One real payload, served locally, installed by the real script."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.version = (ROOT / "VERSION").read_text(encoding="utf-8").split()[0]

        served = tmp / "served"
        (served / f"v{cls.version}").mkdir(parents=True)
        built = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build_release.py"),
             "--tag", f"v{cls.version}",
             "--out-dir", str(served / f"v{cls.version}")],
            capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        assert built.returncode == 0, built.stderr

        # The releases API response the script parses tag_name out of.
        (served / "latest.json").write_text(
            json.dumps({"tag_name": f"v{cls.version}"}), encoding="utf-8")

        cls.served = served
        # SimpleHTTPRequestHandler takes `directory` as a constructor kwarg.
        cls._server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            lambda *a, **kw: _QuietHandler(*a, directory=str(served), **kw))
        cls.base = f"http://127.0.0.1:{cls._server.server_address[1]}"
        cls._thread = threading.Thread(target=cls._server.serve_forever,
                                       daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        cls._thread.join(timeout=10)
        cls._tmp.cleanup()

    def _install(self, home, extra_env=None):
        env = dict(os.environ)
        env.update({
            "HOME": str(home),
            "WIKI_HARNESS_API_LATEST": f"{self.base}/latest.json",
            "WIKI_HARNESS_DOWNLOAD_BASE": self.base,
        })
        env.pop("WIKI_HARNESS_VERSION", None)
        env.update(extra_env or {})
        return subprocess.run(["sh", str(INSTALL_SH)], env=env,
                              capture_output=True, text=True, timeout=180)

    def test_it_installs_a_working_launcher(self):
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)

            result = self._install(home)

            self.assertEqual(result.returncode, 0,
                             result.stdout + result.stderr)
            installed = home / ".local" / "bin" / "wiki-harness"
            self.assertTrue(installed.is_file(), result.stdout)
            self.assertTrue(os.access(installed, os.X_OK),
                            "the installed launcher must be executable")

            # It runs, and reports without touching the network.
            ran = subprocess.run([sys.executable, str(installed), "--version"],
                                 capture_output=True, text=True, timeout=60,
                                 env={**os.environ,
                                      "WIKI_HARNESS_CACHE": str(home / "cache")})
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertIn("launcher", ran.stdout)

    def test_it_says_how_to_fix_a_path_that_lacks_the_bin_dir(self):
        with tempfile.TemporaryDirectory() as home:
            result = self._install(Path(home), {"PATH": "/usr/bin:/bin"})

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("not on your PATH", result.stdout)
            self.assertIn("export PATH=", result.stdout)

    def test_a_custom_bin_dir_is_honoured(self):
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)
            target = home / "custom-bin"

            result = self._install(home, {"WIKI_HARNESS_BIN_DIR": str(target)})

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / "wiki-harness").is_file())

    def test_a_tampered_payload_is_refused_and_nothing_is_installed(self):
        """The checksum is the whole reason it is published; a payload that
        does not match it must never reach PATH."""
        archive = (self.served / f"v{self.version}"
                   / f"wiki-harness-{self.version}.tar.gz")
        original = archive.read_bytes()
        archive.write_bytes(b"this is not the payload")
        try:
            with tempfile.TemporaryDirectory() as home:
                home = Path(home)

                result = self._install(home)

                self.assertEqual(result.returncode, 1,
                                 result.stdout + result.stderr)
                self.assertIn("checksum mismatch", result.stderr)
                self.assertFalse(
                    (home / ".local" / "bin" / "wiki-harness").exists())
        finally:
            archive.write_bytes(original)

    def test_a_missing_release_refuses_without_installing(self):
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)

            result = self._install(home, {"WIKI_HARNESS_VERSION": "99.99.99"})

            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("could not download", result.stderr)
            self.assertFalse(
                (home / ".local" / "bin" / "wiki-harness").exists())


if __name__ == "__main__":
    unittest.main()
