---
id: ref-ownership-classes
c3-seal: 4e6c1ea2088207153f2d963730fe01216dc4ac9243a3f5480dc95abc9cc2bd19
title: Four file-ownership classes drive what upgrade may overwrite
type: ref
goal: |-
    Give every path a wiki instance holds an unambiguous ownership class, so `upgrade` can decide,
    per path, whether silently overwriting it on an in-place upgrade is safe or would clobber
    content the wiki's owner already changed on purpose.
---

## Goal

Give every path a wiki instance holds an unambiguous ownership class, so `upgrade` can decide,
per path, whether silently overwriting it on an in-place upgrade is safe or would clobber
content the wiki's owner already changed on purpose.

## Choice

Four classes, exactly as plan-v3 §2.3's ownership map names them: TEMPLATE (var-substituted,
e.g. `wiki_title`/`org_name`/`content_language`/`repo_name`; library-owned forever), MANAGED
(fixed content, no vars, re-copied byte-for-byte on every `init`/`upgrade`; library-owned
forever), SEEDED (library-owned only at `init` time — written once as a starting point, then
100% instance-owned from that commit on), and INSTANCE (never touched by the library, ever).
The `templates` container splits along exactly the three library-owned classes: `c3-301` holds
TEMPLATE files, `c3-302` holds MANAGED files, `c3-303` holds SEEDED files — INSTANCE content has
no template-container component because the library never ships bytes for it.

## Why

Without a per-file class, `upgrade` has no way to tell "the owner deliberately edited
`sources/cards/recipes.md`" (SEEDED, now 100% instance-owned) from "this file has drifted from
the library's canonical bytes and should be repaired" (MANAGED) — conflating the two either
clobbers real owner content or lets real drift ride forever undetected. The manifest
(`scripts/manifest.py`, `c3-201`) persists the class as a `role` field per path in
`.wiki-harness-manifest.json` precisely so `diff_manifest`'s pure decision logic can apply this
rule mechanically from the recorded class, instead of guessing from file content or timestamps.

## How

`scripts/manifest.py`'s `files` map records `{"role": "managed" | "template" | "removed", ...}` per
path — SEEDED and INSTANCE paths are deliberately absent from the manifest's `files` map
entirely (plan-v3 §2.4: "`files` covers exactly MANAGED + TEMPLATE paths — never
SEEDED/INSTANCE, which are expected to diverge"). `upgrade --adopt-drift <path>` is the one
documented way a path's `role` becomes `"instance-fork"`, moving a previously MANAGED/TEMPLATE
path out of the library's silent-overwrite set for good.
