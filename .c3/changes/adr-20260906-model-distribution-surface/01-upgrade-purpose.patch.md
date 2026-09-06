---
target: c3-211
scope: block
base: c3-211#n380@v1:sha256:51a09922122097394d00f9a9f35b0b27ab223a467c2d597d196e20518d22bea4
---
Own `upgrade.py`'s standalone `--check` mode plus its 13 ordered `--apply`/dry-run steps
(plan-v3 §3.2): clean-tree precondition, refuse-before-write drift check (including missing-path
drift), downgrade guard, `--adopt-drift` handling, idempotency fast path, the dry-run/mutating
split, library resolution, MAJOR-removal guard, scratch-copy, re-render, scratch-lint
self-check, atomic promote (`try`/`except` → `git checkout -- .` on any exception, no marker
file, no `--resume`), manifest rewrite, and optional `--commit` with its own automatic rollback
on a rejected commit.

Library resolution (step 6) takes a supplied `--library-path` verbatim — what `c3-501`
(launcher) always passes, naming the release payload it just unpacked, touching neither git nor
the network — and otherwise falls back to fetching and checking out the tag in `upgrade.py`'s
own directory. That fallback fails closed: both git calls are checked and the resulting
checkout's `VERSION` must match the requested release, because ignoring them let a failed
fetch, a missing tag or no network leave the checkout on whatever version it already had and
build a scaffold from it, labelled with the version the operator asked for.

Non-goal: this component never repairs drift itself — every drift path either aborts (default)
or is explicitly, permanently forked via `--adopt-drift`; there is no silent "just overwrite
it" path.
