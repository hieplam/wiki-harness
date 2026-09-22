#!/usr/bin/env bash
# Advisory neutrality review of the working diff.
#
# ADVISORY BY DESIGN: it prints and always exits 0. An LLM verdict is not
# deterministic, and a flaky hard gate would be worse than none. The
# deterministic, blocking half of this job is tests/test_genericity.py,
# which CI already runs.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

DIFF="$(git diff HEAD -- . ':(exclude)docs/neutrality-rubric.md')"
if [ -z "$DIFF" ]; then
  echo "neutrality: no changes to review."
  exit 0
fi

if ! command -v copilot >/dev/null 2>&1; then
  echo "neutrality: 'copilot' not found; skipping the advisory review." >&2
  echo "neutrality: the blocking check is ./run_tests.sh (test_genericity)." >&2
  exit 0
fi

PROMPT="$(cat docs/neutrality-rubric.md)

Review the following diff against that rubric. Report only violations.

$DIFF"

printf '%s' "$PROMPT" | copilot -p - --allow-all-tools --no-ask-user || {
  echo "neutrality: the advisory review could not run; not blocking." >&2
  exit 0
}
