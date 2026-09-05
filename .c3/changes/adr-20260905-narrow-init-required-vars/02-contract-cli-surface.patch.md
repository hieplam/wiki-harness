---
target: c3-210
scope: block
base: c3-210#n362@v1:sha256:add09a21150d90f87f38e6b09ca047d8612c2cbe5fb8ee46d63ed4bf6a3ec883
---
| python3 wiki-harness/init.py <target-dir> --wiki-title <title> [--org-name ...] [--content-language ...] [--repo-name ...] [--origins a,b,c] [--answers-file ...] [--non-interactive] [--force] | IN/OUT | Fail-closed at any of the 16 ordered steps. `--wiki-title` is the only required variable (v1.2.0); `org_name`, `content_language`, and `repo_name` are derived when omitted — from `wiki_title`, `English`, and the target's resolved basename — and a supplied value is never overridden. A non-empty target without --force exits 2 with the exact quoted message before writing anything; a missing `--wiki-title` under --non-interactive exits 2 naming the flag; a prompt with no readable stdin exits 2 naming --non-interactive, never a traceback. Success leaves one real commit, a clean git status, and lint.py --root . exiting 0 | CLI process boundary | plan-v3.md §3.1; CHANGELOG.md v1.2.0; docs/compatibility-policy.md §2.1 |
