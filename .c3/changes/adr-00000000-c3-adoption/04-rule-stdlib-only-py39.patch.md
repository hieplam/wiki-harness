---
target: rule-stdlib-only-py39
scope: whole
type: rule
title: Python 3.9 floor, stdlib only
---

## Goal

Guarantee every wiki-harness Python module runs on the oldest interpreter a consuming wiki might
have available, with zero install step, matching how `scripts/lint.py` already runs today in
ogp-wiki.

## Rule

Every wiki-harness `.py` module targets Python 3.9, imports only the standard library, and opens
with `from __future__ import annotations` as its first import.

## Golden Example

Literal code from `/Users/hip/repo/ogp-wiki/scripts/lint.py` (HEAD `f8b43fb`), lines 1-15:

```python
#!/usr/bin/env python3
"""Mechanical lint for the OGP wiki (spec §7.1).

Pure core: parse/extract/resolve helpers and check_* functions (data in ->
Findings out). Impure edges: scan()/git_changes()/main() at the bottom.
Python 3 stdlib only.
"""
from __future__ import annotations            # REQUIRED: first import, every module

import re                                      # REQUIRED: stdlib only —
import subprocess                               # re, subprocess, sys, pathlib
import sys                                      # are all standard library
from pathlib import Path, PurePosixPath
```

## Not This

| Anti-Pattern | Correct | Why Wrong Here |
|---|---|---|
| Add a third-party dependency (e.g. `pyyaml`, `click`) to simplify CLI/config parsing | Use `argparse`/`json`/`re` and other stdlib modules, exactly as `scripts/*.py` already does | A wiki instance has no package-manager step; a third-party import breaks `python3 scripts/lint.py` on a bare interpreter |
| A new module ships without `from __future__ import annotations` | Add it as the first import line, matching every existing script | The Python 3.9 floor (plan-v3 D2) relies on this line to accept annotation syntax written as if on a newer interpreter |
| Ship a `pyproject.toml`/`setup.py` so the library can declare a dependency | Keep every entry point a plain script invocation, `python3 wiki-harness/init.py <target-dir>`, same shape `scripts/lint.py` already uses | plan-v3 §2.1 explicitly rules out `pyproject.toml`, `setup.py`, and console-script entry points for this library |

## Scope

Applies to every `.py` file in `scripts/`, the `lifecycle` container (`init.py`, `upgrade.py`,
`manifest.py`), and `tests/*.py`.

## Override

None.
