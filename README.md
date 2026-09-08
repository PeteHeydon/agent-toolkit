# agent-toolkit

Build composable agents from a library of skills, tools, and patterns — starting
from one personalised baseline that every agent inherits.

## Quick start

```bash
git clone <repo> && cd agent-toolkit
claude

/bootstrap-profile        # interview -> ~/.agent-toolkit/baseline.yaml
/create-agent my-agent    # scaffold  -> ~/.agent-toolkit/agents/my-agent/
```

Commands run from inside `agent-toolkit/`. Nothing you create lands inside it —
your profile and agents live under `~/.agent-toolkit/`, so `git pull` never
collides with your work.

## The three things

| | What | Where |
|---|---|---|
| **Builders** | The toolkit's own agents | `builders/` |
| **Baseline profile** | Your defaults — a config file, not an agent | `~/.agent-toolkit/baseline.yaml` |
| **Your agents** | Composed from the baseline | `~/.agent-toolkit/agents/` |

Full detail: [`docs/repository-structure.md`](docs/repository-structure.md)

## Inheritance

Agents inherit by **reference at runtime**, not by copying at creation. Edit the
baseline and every agent that hasn't overridden that field picks up the change on
its next run.

Precedence, lowest to highest: baseline -> agent override -> CLI flag ->
in-session instruction. Higher wins for the field it sets, and only that field.
See [`docs/precedence-and-inheritance.md`](docs/precedence-and-inheritance.md).

## Setup

Set `ANTHROPIC_API_KEY` before first run — see
[`docs/environment-variables.md`](docs/environment-variables.md).

Secrets never go in a profile or an `agent.yaml`. Validation rejects them.

## Status

**v1 — Claude Code.** Planned: Codex, AWS/Azure AI Foundry, and an OpenWebUI
wrapper for a browser-based desktop experience without a CLI. See
[`docs/vision.md`](docs/vision.md).

### Builders

| Builder | Status |
|---|---|
| bootstrap-agent | Implemented |
| create-agent | Implemented |
| validation-agent | Stubbed (hooks in `validate-profile.py`, `validate-agent.py`) |
| design-agent | Planned |
| agent-skills-agent | Planned |
| doco-agent | Planned |
| tov-agent | Planned |
| agent-ops-agent | Planned |
| agent-optimisation-agent | Planned |
| agent-tool-agent | Planned |
| agent-security-agent | Planned |
| agent-refinement-agent | Planned |

## Verify

```bash
bash scripts/verify-toolkit.sh
```

## Docs

- [Getting started](docs/getting-started.md)
- [Tutorial: your first agent](docs/tutorial-first-agent.md) — a worked example, start to finish
- [Testing](docs/testing.md)
- [Handoff brief](HANDOFF.md) — background and settled design decisions
- [TODO](TODO.md) — outstanding work
- [Repository structure](docs/repository-structure.md)
- [Precedence & inheritance](docs/precedence-and-inheritance.md)
- [Environment variables & secrets](docs/environment-variables.md)
- [Vision](docs/vision.md)
- [Agentic patterns research](docs/research/agentic-patterns-initial-summary.md)
