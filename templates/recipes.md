# Card recipes

## Trust meanings

| trust | meaning |
|---|---|
| `verified-in-code` | Confirmed against source code or observed system behaviour |
| `stated` | Asserted by a person or document, unverified |
| `hearsay` | Second-hand |

## Per-origin recipes — what to extract

| origin | extract |
|---|---|
| `session` | Verified findings, decisions made, lessons learnt, gotchas discovered |
| `transcript` | Speakers/personas, decisions + owners, commitments |
| `jira` | Problem → root cause → fix → affected services |
| `slack` | The question + the tribal answer |
| `confluence` / `research` | Concepts, definitions, procedures |
| `adr` | Context, decision, rejected options, consequences, status, supersedes |

All recipes emit the SAME contract: a card with claims, filed into wiki pages. A recipe never
invents its own page shape: it files into a page kind that `wiki/AGENTS.md` defines. A decision,
a lesson learnt, or the fix an incident produced goes to a decision page. An `adr` card is filed
as `wiki/AGENTS.md` describes under "Importing an ADR".
