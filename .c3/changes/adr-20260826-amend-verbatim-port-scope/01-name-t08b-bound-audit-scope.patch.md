---
target: ref-verbatim-port
scope: block
base: ref-verbatim-port#n53@v1:sha256:a0a393912248d93783cf5a794b21fc2380f93c82a384123e8099e03da6304af9
---
Fork `scripts/lint.py`, `scripts/card_frontmatter_lint.py`, `scripts/check_commit_msg.py`,
`.githooks/pre-commit`, and `.githooks/commit-msg` byte-for-byte from ogp-wiki HEAD commit
`f8b43fb` (T01), applying only the specific, itemized additive/prose fixes plan-v3 names by
number — T03 (genericize examples, byte-match `CARD_KEY`, fix the `raw:` example, remove a
dangling spec reference), T04 (schema-driven card-id mechanism, deleting the hardcoded
`CARD_ID_RE`), T08 (the `RULES_FILES` generalization), and T08b (RULES_FILES parity in the
card-lint CLI discovery, a defect T04 itself introduced) — never a freehand rewrite of the
checks themselves.

Audit-driven fixes in this phase are limited to defects introduced by those itemized tasks. A
defect inherited byte-identical from ogp-wiki — for example the unanchored citation scan's
prefix-matching, list-item rule non-enforcement, or `git diff HEAD` vs `--cached` in
`git_changes()` — is out of scope for the port and is tracked as a post-migration hardening
candidate, never fixed "freehand" during the port.
