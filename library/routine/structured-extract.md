---
name: structured-extract
kind: routine
summary: Pull named fields out of a document without inventing any of them.
requires_capabilities: [file.read]
conflicts_with: []
schema_version: 1
---

- Extract only fields that were asked for. A helpful extra field is a field
  nobody validated.
- Quote the source span for every extracted value, or record where it came from.
- Use an explicit null for a field the document does not contain. Never infer a
  plausible value to fill a gap, and never omit the key.
- Flag a field the document states more than once with different values, rather
  than picking the first.
- Keep the source's own units, spelling and formatting for verbatim fields.
  Normalise only where the output contract asks for it.
- Return the agreed shape exactly, including for a document that turned out to
  contain nothing relevant.
