---
target: c3-101
scope: block
base: c3-101#n120@v1:sha256:7f024d887573c943fd0fe6da2bb48eefa97f44fba2c229383bf40df61211864e
---
| scan(root) -> (files, encoding_findings) | OUT | Reads exactly the glob set index.md, AGENTS.md, VISION.md, sources/AGENTS.md, sources/cards/card-schema.json, `wiki/**/*.md`, `sources/cards/*.md` plus sources/raw/* (existence-only), decoding as utf-8-sig; a non-UTF-8 file becomes an ENCODING finding instead of raising | Impure edge — the only place this component touches the filesystem to build files | /Users/hip/repo/ogp-wiki/scripts/lint.py:169-190 |
