---
target: c3-210
scope: insert
base: c3-210#n364@v1:sha256:4be549605964186b66b6aafae5cd46ba627e238929d0b59dbc786ccff986c7e9
---
| Scaffolding from a release payload | IN/OUT | The library root may be an unpacked release payload with no `.git` — what `c3-501` (launcher) runs. Provenance then comes from the payload's `RELEASE.json`: the manifest records the real tag, commit and a fetchable https `source_url`, never a local cache path, `"unknown"` and forty zeros. `source_url` is what `upgrade --check` later feeds to `git ls-remote`, so a poisoned one would break that command for the life of the wiki. A git checkout, which has no `RELEASE.json`, is answered by git exactly as before | Filesystem edge — the library root's own metadata | tests/test_init.py::ReleasePayloadProvenance |
