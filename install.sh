#!/bin/sh
# Install the `wiki-harness` command.
#
#   curl -fsSL https://raw.githubusercontent.com/hieplam/wiki-harness/main/install.sh | sh
#
# Downloads the newest release, verifies its published checksum, and puts the
# launcher on your PATH. Everything is written under $HOME -- this never needs
# sudo, and it never touches a system directory.
#
# Re-running it is how you update; `wiki-harness self-update` just runs this
# script again.
#
# Environment:
#   WIKI_HARNESS_BIN_DIR        where to install   (default: ~/.local/bin)
#   WIKI_HARNESS_VERSION        install this exact release instead of the newest
#   WIKI_HARNESS_API_LATEST     where to ask for the newest version
#   WIKI_HARNESS_DOWNLOAD_BASE  where release assets live
#
# The last two exist so this script can be pointed at a mirror, and so the
# test suite can exercise it end to end without reaching GitHub.
#
# POSIX sh: no bash-isms, no arrays, no `local`. It runs under dash on Debian
# and under whatever /bin/sh is on macOS.

set -eu

REPO="hieplam/wiki-harness"
API_LATEST="${WIKI_HARNESS_API_LATEST:-https://api.github.com/repos/${REPO}/releases/latest}"
DOWNLOAD_BASE="${WIKI_HARNESS_DOWNLOAD_BASE:-https://github.com/${REPO}/releases/download}"
BIN_DIR="${WIKI_HARNESS_BIN_DIR:-${HOME}/.local/bin}"

say() { printf '%s\n' "$*"; }
die() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }

need() {
    command -v "$1" >/dev/null 2>&1 || die "$2"
}

# ---- preconditions -------------------------------------------------------

need curl "curl is required to download the release."
need tar "tar is required to unpack the release."

# The harness is Python 3.9+, stdlib only. Check before installing rather
# than letting the first `wiki-harness init` fail with a syntax error.
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[ -n "$PYTHON" ] || die "python3 >= 3.9 is required and was not found on PATH."

# ---- resolve the version -------------------------------------------------

VERSION="${WIKI_HARNESS_VERSION:-}"
if [ -z "$VERSION" ]; then
    say "Resolving the newest release..."
    # No jq dependency: pull tag_name out with the Python we just validated.
    VERSION=$(curl -fsSL "$API_LATEST" | "$PYTHON" -c '
import json, re, sys
try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(1)
tag = data.get("tag_name", "") if isinstance(data, dict) else ""
match = re.match(r"^v?(\d+\.\d+\.\d+)$", tag)
if not match:
    sys.exit(1)
print(match.group(1))
') || die "could not determine the newest release from ${API_LATEST}. Set WIKI_HARNESS_VERSION=X.Y.Z to install a specific one."
fi

VERSION="${VERSION#v}"
say "Installing wiki-harness v${VERSION}"

ARCHIVE="wiki-harness-${VERSION}.tar.gz"
ARCHIVE_URL="${DOWNLOAD_BASE}/v${VERSION}/${ARCHIVE}"

# ---- download and verify -------------------------------------------------

WORK=$(mktemp -d)
# Clean up on success, failure, and Ctrl-C alike -- a half-downloaded payload
# must never be left behind.
trap 'rm -rf "$WORK"' EXIT INT TERM

curl -fsSL -o "${WORK}/${ARCHIVE}" "$ARCHIVE_URL" \
    || die "could not download ${ARCHIVE_URL}
Releases cut before the release workflow existed publish no payload; see https://github.com/${REPO}/releases"

curl -fsSL -o "${WORK}/${ARCHIVE}.sha256" "${ARCHIVE_URL}.sha256" \
    || die "could not download the checksum for v${VERSION}; refusing to install an unverified payload."

# Verify with whatever the machine has. Never skip: an unverifiable payload
# is a refusal, not a warning.
EXPECTED=$(cut -d' ' -f1 < "${WORK}/${ARCHIVE}.sha256")
if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL=$(sha256sum "${WORK}/${ARCHIVE}" | cut -d' ' -f1)
elif command -v shasum >/dev/null 2>&1; then
    ACTUAL=$(shasum -a 256 "${WORK}/${ARCHIVE}" | cut -d' ' -f1)
else
    ACTUAL=$("$PYTHON" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "${WORK}/${ARCHIVE}")
fi

[ -n "$EXPECTED" ] || die "the published checksum for v${VERSION} is empty; refusing to install."
if [ "$EXPECTED" != "$ACTUAL" ]; then
    die "checksum mismatch for v${VERSION}:
  published: ${EXPECTED}
  downloaded: ${ACTUAL}
Nothing was installed."
fi

# ---- install -------------------------------------------------------------

tar -xzf "${WORK}/${ARCHIVE}" -C "$WORK" || die "could not unpack ${ARCHIVE}."
LAUNCHER="${WORK}/wiki-harness-${VERSION}/bin/wiki-harness"
[ -f "$LAUNCHER" ] || die "release v${VERSION} contains no bin/wiki-harness; it predates the CLI. Install a newer release."

mkdir -p "$BIN_DIR"
# Write beside the target and rename: an interrupted install must never leave
# a truncated executable on PATH.
cp "$LAUNCHER" "${BIN_DIR}/.wiki-harness.new"
chmod +x "${BIN_DIR}/.wiki-harness.new"
mv "${BIN_DIR}/.wiki-harness.new" "${BIN_DIR}/wiki-harness"

say ""
say "Installed ${BIN_DIR}/wiki-harness (launcher for release v${VERSION})"

case ":${PATH}:" in
    *":${BIN_DIR}:"*)
        say ""
        say "Try it:"
        say "  wiki-harness init my-wiki --wiki-title 'My Wiki'"
        ;;
    *)
        say ""
        say "${BIN_DIR} is not on your PATH. Add it:"
        say ""
        say "  echo 'export PATH=\"${BIN_DIR}:\$PATH\"' >> ~/.zshrc   # or ~/.bashrc"
        say "  export PATH=\"${BIN_DIR}:\$PATH\""
        say ""
        say "Then:  wiki-harness init my-wiki --wiki-title 'My Wiki'"
        ;;
esac
