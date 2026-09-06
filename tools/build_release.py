#!/usr/bin/env python3
"""Build the release payload a consumer installs.

Run by the `assets` job of .github/workflows/release-please.yml against a
tag release-please has already cut. Produces two files in --out-dir:

    wiki-harness-<X.Y.Z>.tar.gz          the payload
    wiki-harness-<X.Y.Z>.tar.gz.sha256   its checksum, in `sha256sum` format

The payload holds exactly what a wiki instance is assembled from -- the two
entry points, the three vendored trees, VERSION, and RELEASE.json -- and
nothing a consumer never runs. It is NOT a `git archive`: those include the
whole repository and their bytes are not stable across git versions, and
the launcher verifies a recorded checksum.

RELEASE.json exists because an unpacked tarball has no `.git`, so init.py's
read_source_url()/read_source_ref()/read_source_commit() edges have nothing
to interrogate and would silently record a local path, "unknown", and forty
zeros in the consumer's manifest. This file is what they read instead.

This module lives in tools/, never scripts/: init.py's copy_scripts()
vendors every scripts/*.py into each consumer wiki, so a build tool there
would ship into every wiki and change every consumer's manifest hash.

Pure core: version_mismatch(), archive_name(), release_metadata(),
tar_filter() -- data in, data or a refusal out. Impure edges: git_output(),
build_payload(), write_archive(), main(). Python 3 stdlib only.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Everything a consumer wiki is assembled from. init.py discovers the
# contents of scripts/ and githooks/ off disk at run time, so these are
# whole trees, not file lists -- a new template or script ships with no
# change here. Anything absent from this tuple never reaches a consumer.
PAYLOAD_PATHS = ("init.py", "upgrade.py", "VERSION",
                 "bin", "scripts", "githooks", "templates")

DEFAULT_SOURCE_URL = "https://github.com/hieplam/wiki-harness"

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# Fixed timestamp and ownership for every member, so two builds of the same
# tag are byte-identical. The dispatch recovery path re-runs this build for
# a tag someone may already have installed; it must not publish different
# bytes under the same name.
EPOCH = 0


def version_mismatch(tag, version):
    """Pure. The refusal message when the tag being released and the
    repository's VERSION file disagree, or None when they match. A
    mismatch means the checkout is not the commit the tag points at, and
    every path below would build a payload labelled with the wrong
    version."""
    match = TAG_RE.match(tag)
    if not match:
        return (f"tag {tag!r} is not a release tag; expected the form "
                f"vX.Y.Z")
    tagged = ".".join(match.groups())
    if tagged != version:
        return (f"tag {tag!r} does not match VERSION {version!r}; the "
                f"checkout is not the commit that tag points at")
    return None


def archive_name(version):
    """Pure. The payload's filename for a version."""
    return f"wiki-harness-{version}.tar.gz"


def release_metadata(version, tag, commit, source_url):
    """Pure. RELEASE.json's content: the provenance init.py would have
    asked git for, recorded at build time so a .git-less payload can still
    write an honest manifest."""
    return {
        "version": version,
        "tag": tag,
        "commit": commit,
        "source_url": source_url,
    }


def tar_filter(info):
    """Pure. Normalises one archive member so the build is reproducible:
    a fixed mtime, uid/gid 0, and no recorded owner names."""
    info.mtime = EPOCH
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


# ---- impure edges ----

def git_output(root, *args):
    """Impure edge. One git read against `root`, host config neutralised so
    an unusual-but-legal setting cannot change what gets recorded. Returns
    the stripped stdout, or "" when git fails for any reason."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    try:
        result = subprocess.run(["git", "-C", str(root), *args],
                                capture_output=True, text=True, env=env,
                                timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def read_version(root):
    """Impure edge. Same first-token parse as init.py's read_version()."""
    text = (root / "VERSION").read_text(encoding="utf-8").strip()
    return text.split()[0] if text.split() else ""


def resolve_source_url(root):
    """Impure edge. The repository's own remote, falling back to the
    canonical URL when the build runs from an archive or a remote-less
    clone -- never a local filesystem path, which is what would poison a
    consumer's `upgrade --check`."""
    url = git_output(root, "config", "--get", "remote.origin.url")
    if not url:
        return DEFAULT_SOURCE_URL
    # Normalise the ssh remote form so the recorded value is fetchable by
    # anyone, not just someone with this machine's keys.
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    return url[:-len(".git")] if url.endswith(".git") else url


def build_payload(root, staging, version, metadata):
    """Impure edge. Copies PAYLOAD_PATHS into `staging/wiki-harness-<v>/`
    and writes RELEASE.json beside them. Refuses when a listed path is
    missing rather than shipping an incomplete payload."""
    top = staging / f"wiki-harness-{version}"
    top.mkdir(parents=True)
    for rel in PAYLOAD_PATHS:
        source = root / rel
        if not source.exists():
            raise FileNotFoundError(
                f"payload path {rel!r} is missing from {root}")
        if source.is_dir():
            shutil.copytree(source, top / rel,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(source, top / rel)
    (top / "RELEASE.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return top


def write_archive(top, out_dir, version):
    """Impure edge. Tars `top` deterministically and writes the checksum
    file beside it. Returns (archive_path, checksum_path)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / archive_name(version)

    raw = out_dir / f".{archive.name}.tar"
    with tarfile.open(raw, "w") as tar:
        # Sorted and non-recursive so member order is the same on every
        # machine; tar_filter() zeroes the per-member metadata.
        for path in sorted(top.rglob("*")):
            tar.add(path, arcname=str(path.relative_to(top.parent)),
                    recursive=False, filter=tar_filter)
    # gzip stamps its own header with an mtime and the source filename;
    # both are pinned here, or two builds of one tag differ in bytes.
    with open(archive, "wb") as compressed:
        with open(raw, "rb") as plain, \
                gzip.GzipFile(filename="", mode="wb", fileobj=compressed,
                              mtime=EPOCH) as gz:
            shutil.copyfileobj(plain, gz)
    raw.unlink()

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = Path(str(archive) + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, checksum


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="build_release.py")
    parser.add_argument("--tag", required=True,
                        help="the release tag being built, e.g. v1.3.0")
    parser.add_argument("--out-dir", required=True,
                        help="directory to write the archive and checksum into")
    parser.add_argument("--source-root", default=str(REPO_ROOT),
                        help="repository to build from (default: this checkout)")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    root = Path(args.source_root).resolve()

    try:
        version = read_version(root)
    except OSError as exc:
        print(f"cannot read {root / 'VERSION'}: {exc}", file=sys.stderr)
        return 2

    refusal = version_mismatch(args.tag, version)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2

    metadata = release_metadata(
        version, args.tag,
        git_output(root, "rev-parse", "HEAD") or "0" * 40,
        resolve_source_url(root))

    with tempfile.TemporaryDirectory() as staging:
        try:
            top = build_payload(root, Path(staging), version, metadata)
            archive, checksum = write_archive(top, Path(args.out_dir).resolve(),
                                              version)
        except (FileNotFoundError, OSError, tarfile.TarError) as exc:
            print(f"building the release payload failed: {exc}",
                  file=sys.stderr)
            return 2

    print(f"{archive}")
    print(f"{checksum}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
