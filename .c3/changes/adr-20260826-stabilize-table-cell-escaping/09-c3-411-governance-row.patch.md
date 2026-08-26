---
target: c3-411
scope: block
base: c3-411#n460@v1:sha256:7420fcff2b6f6ca6a2f0e8859f205fbc2da9d976982d841f307c110ecb2c0825
---
| rule-stdlib-only-py39 | rule | Every test_*.py module here imports only the standard library (unittest), opens with `from __future__ import annotations` | Hard | Same floor every module in scripts/lifecycle/tests targets |
