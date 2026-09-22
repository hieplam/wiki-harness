# Neutrality rubric

`wiki-harness` is a public library. Nothing it ships may name, depend on, or be shaped by
any specific company, product, team, person or business domain.

A reviewer answers one question: **could a reader infer, from this diff, what organisation
built or uses this harness?** If yes, it is a violation.

## Violations

- Naming a real company, product, team, internal service, or person.
- Domain vocabulary specific to one business: the names of its processes, its internal
  metrics, its ticket prefixes, its hostnames, its email domains.
- **Invented proper nouns that are clearly internal.** "An internal health-check and auth
  service named Aerith" names no real company, yet is plainly a leak of a private system's
  shape. A denylist cannot catch this; a reader can.
- Examples whose subject matter only makes sense inside one organisation.

## Not violations

- Generic technical subject matter: `"what is the difference between goroutines and
  channels in Go?"`, `example-service`, `widget-assembly`.
- Well-known public technologies, standards and languages.
- Placeholder names that are obviously placeholders: `<repo>`, `example.invalid`.

## Output

For each violation: the file, the line, the offending text, and a neutral replacement.
If there are none, say exactly `NO VIOLATIONS`.
