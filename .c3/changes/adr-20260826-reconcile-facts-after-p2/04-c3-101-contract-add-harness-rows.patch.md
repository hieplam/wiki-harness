---
target: c3-101
scope: insert
base: c3-101#n603@v1:sha256:02b8b61e5236a9f19491a3dfbd6c3524be2b3fca1b7ea2be3eedbc2358902cd4
---
| `read_harness_manifest(root) -> ManifestState / ManifestMalformed / None` | OUT | Impure edge: reads `.wiki-harness-manifest.json` via `manifest.read_manifest`, hashes every recorded path with role in {managed, template, instance-fork} via `manifest.hash_tree`; fails closed on non-UTF-8 / invalid JSON / bad shape / unknown role | Impure edge — the only place this component reads/hashes the harness manifest and its tracked paths | /Users/hip/repo/wiki-harness/scripts/lint.py:484 |
