# Proposal: the module library

Status: **accepted**. Recorded as D14 in [`../decisions.md`](../decisions.md).
Referenced by `TODO.md` items 6.x.

## The problem

`skills/`, `tools/` and `patterns/` appear in the documented repository layout
and do not exist on disk. That is the right call so far — scaffolding three
empty vocabularies before anything uses one is how a toolkit accumulates
structure it never fills. But it leaves no unit of reuse below "a whole agent",
so every new agent starts from a near-empty profile and the user re-types the
same operating guidance into every `CLAUDE.md` they write.

## Shape

One directory, three kinds distinguished by frontmatter rather than by three
parallel directories.

```
library/
├── README.md                  # the index; what exists and when to use it
├── pattern/
│   ├── standalone.md
│   ├── pipeline.md
│   └── evaluator-optimizer.md
├── role/
│   ├── researcher.md
│   ├── reviewer.md
│   └── editor.md
└── routine/
    ├── web-research.md
    ├── structured-extract.md
    └── document-summarise.md
```

| Kind | Answers | Example |
|---|---|---|
| `pattern` | How does this agent's process run? | `evaluator-optimizer` — draft, critique, revise, bounded by `max_cycles` |
| `role` | What stance and expertise does it work from? | `reviewer` — assume the work is nearly right and look for the specific thing that isn't |
| `routine` | What concrete procedure does it follow? | `web-research` — search, corroborate across sources, cite |

Nine modules to start. Not ninety. A module earns its place by being written
twice by hand first.

## Module format

```markdown
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
- Cite the URL inline for every claim taken from a page.
- Say what you could not confirm, rather than reporting the closest thing you
  did find as though it answered the question.
```

Constraints, so the library stays light:

- Body of 40 lines or fewer. A module longer than that is a document, not a
  module.
- Imperative guidance only. No configuration — that belongs in the schema.
- `requires_capabilities` names what the module cannot function without.

## Composition

```yaml
# agent.yaml
compose:
  - role/researcher
  - routine/web-research
```

- **Patterns are not composed.** `operating_constraints.pattern` already names
  one, and the renderer loads `library/pattern/<pattern>.md` automatically.
  Two ways to say the same thing is two ways to disagree.
- `compose` is an array, so D4 applies: it replaces the inherited value
  wholesale rather than appending.
- Warn above four composed modules. An agent that needs six is two agents.
- Modules are **inlined at render time**, not linked. The agent directory stays
  self-contained and portable to a runtime that has never heard of this
  toolkit.

## Resolution order

`$AGENT_TOOLKIT_HOME/library/` first, then `<toolkit>/library/`. A user module
with the same name as a shipped one wins, which is the same precedence logic
the rest of the toolkit already uses. `git pull` never overwrites a personal
module.

## Validation

Composition gives `run_semantic_checks()` its first real check, and it is a
useful one:

| Check | Severity |
|---|---|
| Composed module does not exist on either path | error |
| `requires_capabilities` not satisfied by the resolved permission set | error |
| Two composed modules list each other in `conflicts_with` | error |
| More than four composed modules | warning |
| A `web.*` capability granted with no module or process step that uses it | none — this is normal |

The first two are exactly the failure the toolkit produces today in silence: a
research agent with no web access, discovered at run time.
