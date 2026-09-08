# HANDOFF

Context for continuing this project in Claude Code. Read this first.
**Outstanding work is tracked in `TODO.md`, not here** — this file is
background: what the toolkit is, how it's laid out, and which design calls
are already settled.

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
- `/create-agent` — scaffolds an agent that inherits from the baseline
- `resolve-config.py` — the precedence resolver, with per-field provenance
- `validate-profile.py`, `validate-agent.py` — structural, resolution, and hygiene checks
- `detect-profile.sh` — five-state detection (NONE / VALID / STALE / INVALID / UNREADABLE)
- JSON schemas for both the baseline and agent overrides, with both validators
  deriving their enum rules from the schema rather than hardcoding a copy
- `tests/` — 30 automated tests (`python3 -m unittest discover -s tests`) covering
  detection, both validators, resolution, and schema drift; see `docs/testing.md`

What's not built yet, and the known gaps in what is: `TODO.md`.

## Design decisions already settled — don't relitigate without reason

- **Baseline is user-level and singular.** `~/.agent-toolkit/baseline.yaml`. Per-project
  copies destroy the inheritance model.
- **Inheritance is by reference at runtime, not snapshot at creation.** Editing the
  baseline changes every agent that hasn't overridden that field.
- **Overrides only.** An `agent.yaml` that restates a baseline value silently pins
  that field. `validate-agent.py` warns on every one.
- **Arrays replace, they never merge.** Silently appending permission arrays is how
  an agent gets access nobody granted it.
- **`extends` is explicit**, not convention — so agents are portable to Codex/Foundry
  later, and can point at different baselines.
- **Commands run from inside `agent-toolkit/`**, chosen over installing to
  `~/.claude/commands/` to keep the toolkit self-contained with no install step.
- **Defaults are deliberately conservative**: mid-tier model, `standalone` pattern,
  no evaluation loop. Multi-agent patterns cost roughly 10–15x the tokens. Every
  vendor's guidance converges on "start simple." See
  `docs/research/agentic-patterns-initial-summary.md`.
- **No secrets in any config file.** `env:VAR_NAME` references only; validators reject
  literals.

## First run

1. Run `bash scripts/verify-toolkit.sh` — confirm everything is in place
2. Run `/bootstrap-profile` — create your real baseline
3. Run `/create-agent` — scaffold one agent, confirm the flow feels right
4. Then see `TODO.md` for what's next

## Where to look

| Question | File |
|---|---|
| What's left to do? | `TODO.md` |
| How is this laid out and why? | `docs/repository-structure.md` |
| How do config layers resolve? | `docs/precedence-and-inheritance.md` |
| How do I use it? | `docs/getting-started.md` |
| Can I see it built, start to finish? | `docs/tutorial-first-agent.md` |
| How do I test it? | `docs/testing.md` |
| How do secrets work? | `docs/environment-variables.md` |
| What's the long-term plan? | `docs/vision.md` |
| What patterns exist and why these defaults? | `docs/research/agentic-patterns-initial-summary.md` |
