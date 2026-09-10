# library

Reusable agent behaviour, below the level of a whole agent. Without this, every
new agent starts from a near-empty profile and the same operating guidance gets
retyped into every `CLAUDE.md` anyone writes.

One directory, three kinds, told apart by frontmatter rather than by three
parallel vocabularies (D14).

| Kind | Answers | Composed? |
|---|---|---|
| `pattern` | How does this agent's process run? | **No** — set `operating_constraints.pattern` |
| `role` | What stance and expertise does it work from? | Yes |
| `routine` | What concrete procedure does it follow? | Yes |

## The index

### pattern

| Module | Requires | Summary |
|---|---|---|
| `pattern/standalone` | — | One agent, one pass, no extra machinery. The default, and usually right. |
| `pattern/pipeline` | — | Fixed stages in order, each checked before it feeds the next. |
| `pattern/evaluator-optimizer` | — | Draft, critique your own draft, revise. Bounded by max_cycles. |

### role

| Module | Requires | Summary |
|---|---|---|
| `role/researcher` | — | Find out what is true, and be explicit about what you could not establish. |
| `role/reviewer` | — | Assume the work is nearly right, and find the specific thing that is not. |
| `role/editor` | — | Cut what does not earn its place; keep the author's meaning intact. |

### routine

| Module | Requires | Summary |
|---|---|---|
| `routine/web-research` | `web.search`, `web.fetch` | Search, corroborate across independent sources, and cite. |
| `routine/structured-extract` | `file.read` | Pull named fields out of a document without inventing any of them. |
| `routine/document-summarise` | `file.read` | Compress a document without losing what a reader would act on. |

`tests/test_modules.py` asserts this index against the files on disk, so a
module added without a row here fails the suite.

## Composing

```yaml
# agent.yaml
compose:
  - role/researcher
  - routine/web-research
```

Composed bodies are **inlined** into the generated region of the agent's
`CLAUDE.md` at render time, not linked. The agent directory stays
self-contained and portable to a runtime that has never heard of this toolkit.

`compose` is an array, so D4 applies: it replaces the inherited value wholesale
rather than appending to it.

**Patterns are not composed.** `operating_constraints.pattern` already names
one, and it seeds the agent's Process section when the agent is created. Two
ways to name a pattern is two ways for them to disagree.

Validation rejects an agent that composes a module whose
`requires_capabilities` it has not been granted — a research agent with no web
access is exactly the failure this toolkit used to produce in silence.

## Writing one

```markdown
---
name: web-research
kind: routine
summary: Search, corroborate across independent sources, and cite.
requires_capabilities: [web.search, web.fetch]
conflicts_with: []
schema_version: 1
---

- Imperative guidance, one directive per line.
```

Two constraints keep the library light, and the loader enforces both:

- **40 body lines or fewer.** Longer than that is a document, not a module.
- **Guidance only, no configuration.** Settings belong in the schema, where
  they can be validated and resolved. A module carrying settings is a second
  place for them to disagree.

`name` must match the filename and `kind` must match the directory, because
`compose` addresses modules as `kind/name`.

Nine modules ship. That is deliberate: a library nobody has used is a guess,
and a module earns its place by being written twice by hand first.

## Where modules come from

Resolution is user-first:

1. `$AGENT_TOOLKIT_HOME/library/`
2. `<toolkit>/library/`

First match wins, so your own `routine/web-research` shadows the shipped one
and `git pull` never overwrites it. Shadowing is reported rather than silent —
"why is my guidance not taking effect" is a miserable thing to debug.
