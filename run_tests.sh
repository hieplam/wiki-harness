#!/usr/bin/env bash
# Thin wrapper around the library's own test suite. Matches the invocation
# style ogp-wiki's AGENTS.md already documents (`python3 -m unittest
# discover -s tests -q`), giving every later task one canonical command to
# run the full suite.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

python3 -m unittest discover -s tests -q
