# TODO

What's left on the agent toolkit. Background, vision, and settled design
decisions live in `HANDOFF.md` — this file tracks outstanding work only.

## Next up

- [ ] **Agent runtime.** The precedence chain is implemented and documented,
  but nothing yet reads a resolved config and acts on it. Agents can be
  created and resolved; nothing executes them. This is the next substantial
  piece of work.
- [ ] **Validation builder.** The natural next builder to build, since both
  `validate-profile.py` and `validate-agent.py` already have a stub
  `run_semantic_checks()` hook waiting for it — pattern-vs-evaluation-loop
  coherence, permissions-vs-guardrails coherence, tone-vs-audience coherence,
  and similar checks that need judgment rather than a schema rule.

## Builders not yet built

Nine of the eleven from the original notes — only bootstrap-agent and
create-agent exist:

- [ ] Design
- [ ] Doco
- [ ] TOV
- [ ] Ops
- [ ] Optimisation
- [ ] Tool
- [ ] Security
- [ ] Refinement

## Scaffolding not yet built

- [ ] `skills/`, `tools/`, `patterns/` — don't exist yet, not even as
  placeholders. Create when the first builder or agent actually needs one;
  don't scaffold ahead of a real use.

## Open questions

- [ ] **Is the empty `CLAUDE.md` process skeleton still the right call?**
  `templates/agent/CLAUDE.md` ships with an empty numbered process section by
  design — `/create-agent` deliberately doesn't guess at what an agent does.
  That call was made before any real agent existed. Worth confirming once a
  handful of agents have been built and the pattern has been lived with.

## Recently closed

- [x] Schema duplication — `scripts/schema_utils.py` now derives `ENUMS` from
  each JSON schema at import time instead of hardcoding a copy in both
  validators; `verify-toolkit.sh` and `tests/test_schema_sync.py` assert the
  two schemas agree wherever they share a field.
- [x] Test harness — `tests/`, 30 tests via `python3 -m unittest discover -s
  tests`, covering detection, both validators, resolution, and schema drift.
- [x] bootstrap-agent's missing scripts and docs rebuilt to match what
  HANDOFF described (`detect-profile.sh`, `validate-profile.py`,
  `docs/environment-variables.md`, `.gitignore`, `.env.example`).
- [x] `docs/tutorial-first-agent.md` — worked-example tutorial, separate from
  the `getting-started.md` reference doc.
