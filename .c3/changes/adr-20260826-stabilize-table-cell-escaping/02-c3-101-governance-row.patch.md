---
target: c3-101
scope: block
base: c3-101#n114@v1:sha256:9d788ad82403ee0be952dc72a39bd25abb9c7fbf06e9720f6f220cad97e0f86e
---
| rule-stdlib-only-py39 | rule | lint.py imports only re/subprocess/sys/pathlib and opens with `from __future__ import annotations` | Hard | Matches the rule's own Golden Example, drawn from this same file |
