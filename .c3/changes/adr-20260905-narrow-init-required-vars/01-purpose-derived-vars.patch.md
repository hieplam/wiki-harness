---
target: c3-210
scope: block
base: c3-210#n352@v1:sha256:6e2723f014140c8dc4545fdfbb2d00d73abec199e690a669aafc603bd36f4715
---
Own `init.py`'s 16 ordered, fail-closed steps (plan-v3 §3.1): resolve target, collect the
template variables — only `wiki_title` is required, the other three are derived from the
target's basename and the library defaults by the pure `apply_defaults()` — plus `--origins`,
`git init`, create the three `.gitkeep` placeholders, copy scripts/hooks verbatim, render
`AGENTS.md`/`README.md`, copy MANAGED files verbatim, seed SEEDED files, seed the 4 tracked
`CLAUDE.md` stubs, write the manifest, wire `core.hooksPath`, self-verify by actually running
`lint.py` and both hooks, make the real first commit, verify it landed, print the summary.
Non-goal: `init` never runs again against an already-initialized wiki — that is `c3-211`
(upgrade)'s job entirely; the two share `c3-201`/`c3-3` and, since v1.2.0, `apply_defaults()`
on the `--adopt` path, but not each other's flow.
