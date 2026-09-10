# HANDOFF

Context for continuing this project in Claude Code. Read this first.
**Outstanding work is tracked in `TODO.md`, not here** — this file is
background: what the toolkit is, how it's laid out, and which design calls
are already settled.

The canonical design record is `docs/decisions.md`, and `docs/architecture.md`
describes how a configuration becomes a running agent. `TODO.md` is a
prioritised numbered backlog, ordered for sequential execution.

## What this is

A composable agent toolkit. Agents are assembled from a library of skills, tools,
and patterns, starting from one personalised baseline profile that every agent
inherits from. v1 targets Claude Code; later releases add Codex, AWS/Azure AI
Foundry, and an OpenWebUI browser wrapper for non-CLI users.

Full vision: `docs/vision.md`

## The three things — do not conflate these

| | What | Where | Executes? |
|---|---|---|---|
| **Builders** | The toolkit's own agents | `builders/` | Yes |
| **Baseline profile** | Your defaults. **A config file, not an agent.** | `~/.agent-toolkit/baseline.yaml` | No |
| **Your agents** | Composed from the baseline | `~/.agent-toolkit/agents/` | Yes |

`builders/` is deliberately not named `agents/` — `agents/` means "agents you
built" everywhere else, and reusing the word is how the categories blur.

Detail: `docs/repository-structure.md`

## Current state

**Implemented and tested:**
- `/bootstrap-profile` — creates the baseline via Express (5 questions) or Full interview
- `/create-agent` — scaffolds an agent that inherits from the baseline, via a
  deterministic script call rather than prose (Step 4 of the process)
- `scaffold-agent.py` — deterministic agent-directory creation, callable with
  no model in the loop
- `resolve-config.py` — the precedence resolver, with per-field provenance
- `validate-profile.py`, `validate-agent.py` — structural, resolution, and hygiene checks
- `detect-profile.py` — six-state detection (NONE / VALID / STALE / INVALID /
  UNREADABLE / NO_PYTHON), called by both builders. `detect-profile.sh`
  remains as the interpreter probe: it finds a working Python and delegates,
  which is the one thing a Python script cannot do for itself
- `cli_output.py` — the one JSON envelope (`ok`/`errors`/`warnings`/`data`)
  every script above emits under `--json`, per D16
- `/create-agent --web` / `--no-web` — per-agent web access, expanding to the
  whole inherited capability set because arrays replace. Withheld
  high-consequence capabilities are denied, not merely left unlisted
- `render-agent.py` + `runtimes/claude-code.yaml` — one renderer, one pass:
  the generated region of `CLAUDE.md` and the tool permissions, from one
  resolved config and one hash. `--check` reports staleness
- `agent-status.py` — every agent, what it pins, whether it still validates,
  whether its rendered instructions have fallen behind the baseline
- `library/` + `module_utils.py` — nine composable modules in three kinds
  (`pattern`, `role`, `routine`), resolved user-library-first so a personal
  module shadows a shipped one and `git pull` never overwrites it. Roles and
  routines are inlined into an agent's generated region by `compose`; patterns
  seed its Process section instead, and are deliberately *not* composable
- Composition is validated: an agent composing a module whose
  `requires_capabilities` it lacks fails with the module, the capability and
  the fix named. That is the run-time failure this toolkit used to produce
  silently
- `migrate-config.py` — carries a baseline **or an agent** forward a schema
  version, backing the original up first and reporting what the bump changed
  on the user's behalf. Values survive; comments do not, and it says so
- The lifecycle commands: `/list-agents`, `/refresh-agent` (one agent or
  `--all`, plus a migrate path), `/edit-agent` (change one thing without
  restating the rest), `/review-agent` (propose changes, write nothing) and
  `/validate-agent` (mechanical findings and judgment findings, reported apart)
- `semantic_checks.py` — the coherence rules both validators share: a pattern
  that needs a loop it has switched off, a budget that cannot cover the passes
  the pattern implies, a composed module the agent cannot run. An error means
  two fields contradict each other; a warning means it is coherent but worth a
  look. The toolkit's own risk postures are run through it as a test, because
  a check that fails the shipped defaults is broken rather than strict
- `describe-schema.py` — reads the interview out of the schema's `x-` keywords,
  per D17. The bootstrap interview and the builder README's characteristics
  list are both generated from it, so there is one place to change a question
- JSON schemas for both the baseline and agent overrides at **schema_version 2**,
  with both validators deriving their enum rules from the schema rather than
  hardcoding a copy. Capability is a closed vocabulary — `file.read`,
  `file.search`, `file.write`, `shell`, `web.search`, `web.fetch`, `subagent` —
  and web search is granted at every risk posture, fetch at all but the
  strictest (D12)
- `tests/` — 71 automated tests (`python3 -m unittest discover -s tests`) covering
  detection, both validators, resolution, scaffolding, the JSON envelope, the
  interview descriptor, and schema drift; see `docs/testing.md`

What's not built yet, and the known gaps in what is: `TODO.md`.

**Known gap:** the per-domain web rules in `runtimes/claude-code.yaml` use a
rule syntax that has not been checked against Claude Code's own documentation —
see TODO 10.0. If it is wrong those rules are inert, which fails open for a
blocked domain.

## The five that matter first

Nineteen design decisions are recorded in **`docs/decisions.md`**, in full and
with their rationale. That file is canonical — this list is the subset you need
before touching anything.

- **The baseline is user-level and singular.** `~/.agent-toolkit/baseline.yaml`.
  Per-project copies destroy the inheritance model.
- **Inheritance is by reference at runtime, not a snapshot at creation.** Editing
  the baseline changes every agent that hasn't overridden that field.
- **Overrides only, and arrays replace.** An `agent.yaml` that restates a baseline
  value silently pins it, and an array from a higher layer replaces rather than
  appends. Silently merging permission arrays is how an agent gets access nobody
  granted it.
- **An agent is a directory you run Claude Code in.** `cd <agent-dir> && claude`.
  The working directory is what loads its `CLAUDE.md` and permissions.
- **No secrets in any config file.** `env:VAR_NAME` references only; validators
  reject literals.

Don't relitigate any of the nineteen without a reason. If you find one that no
longer holds, change it in `docs/decisions.md` — not here, and not in a doc that
happens to restate it.

## First run

1. Run `bash scripts/verify-toolkit.sh` — confirm everything is in place
2. Run `/bootstrap-profile` — create your real baseline
3. Run `/create-agent` — scaffold one agent, confirm the flow feels right
4. Then see `TODO.md` for what's next

## Where to look

| Question | File |
|---|---|
| What's left to do, and in what order? | `TODO.md` |
| What has been decided, and why? | `docs/decisions.md` |
| How does a config become a running agent? | `docs/architecture.md` |
| How is this laid out and why? | `docs/repository-structure.md` |
| How do config layers resolve? | `docs/precedence-and-inheritance.md` |
| How do I use it? | `docs/getting-started.md` |
| Can I see it built, start to finish? | `docs/tutorial-first-agent.md` |
| How do I test it? | `docs/testing.md` |
| How do secrets work? | `docs/environment-variables.md` |
| What's the long-term plan? | `docs/vision.md` |
| What patterns exist and why these defaults? | `docs/research/agentic-patterns-initial-summary.md` |
