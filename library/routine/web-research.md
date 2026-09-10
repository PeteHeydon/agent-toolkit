---
name: web-research
kind: routine
summary: Search, corroborate across independent sources, and cite.
requires_capabilities: [web.search, web.fetch]
conflicts_with: []
schema_version: 1
---

- Search before answering anything that depends on facts you cannot verify from
  the inputs you were given.
- Corroborate load-bearing claims across two independent sources. One source is
  a lead, not a finding.
- Two pages repeating the same press release are one source. Check whether they
  are independent before counting them.
- Cite the URL inline for every claim taken from a page.
- Prefer the primary document over coverage of it, and the current version over
  a cached one. Note the date of anything time-sensitive.
- Say what you could not confirm, rather than reporting the closest thing you
  did find as though it answered the question.
