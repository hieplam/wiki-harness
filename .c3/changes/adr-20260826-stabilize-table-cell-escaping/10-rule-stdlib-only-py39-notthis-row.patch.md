---
target: rule-stdlib-only-py39
scope: block
base: rule-stdlib-only-py39#n517@v1:sha256:bc81d3dab07cf1b646a8e77a8548df9d07f0511a191a1cadc80f2120e2eead3f
---
| A new module ships without `from __future__ import annotations` | Add it as the first import line, matching every existing script | The Python 3.9 floor (plan-v3 D2) relies on this line to accept annotation syntax written as if on a newer interpreter |
