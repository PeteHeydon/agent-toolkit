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

This table is the single source of truth for what exists. `docs/vision.md`
describes what builders are *for*; it does not track status, and neither does
`TODO.md`.

| Builder | Status |
|---|---|
| bootstrap-agent | Implemented |
| create-agent | Implemented |
| validation-agent | Implemented — `/validate-agent`; the rule-expressible checks live in `scripts/semantic_checks.py` |
| design-agent | Planned |
| agent-skills-agent | Planned |
| doco-agent | Planned |
| tov-agent | Planned |
| agent-ops-agent | Planned |
| agent-optimisation-agent | Planned |
| agent-tool-agent | Planned |
| agent-security-agent | Planned |
| agent-refinement-agent | Implemented — `/review-agent` proposes what to promote from `steering.md`; writes nothing |

## Verify

```bash
bash scripts/verify-toolkit.sh
```

**On Windows:** use `python` or `py -3` wherever the docs say `python3` — the
`python3` command is often the Microsoft Store stub rather than an interpreter.
The pre-flight check above and the interpreter probe are the only bash in the
toolkit and need Git Bash or WSL; everything in the path you actually walk is
Python. See [`docs/getting-started.md`](docs/getting-started.md), "On Windows".

## Docs

- [Getting started](docs/getting-started.md)
- [Tutorial: your first agent](docs/tutorial-first-agent.md) — a worked example, start to finish
- [Testing](docs/testing.md)
- [Handoff brief](HANDOFF.md) — background and settled design decisions
- [Architecture](docs/architecture.md) — how a config becomes a running agent
- [Decisions](docs/decisions.md) — the design record, in full
- [Backlog](TODO.md) — prioritised, numbered, in implementation order
- [Repository structure](docs/repository-structure.md)
- [Precedence & inheritance](docs/precedence-and-inheritance.md)
- [Environment variables & secrets](docs/environment-variables.md)
- [Vision](docs/vision.md)
- [Agentic patterns research](docs/research/agentic-patterns-initial-summary.md)

### Proposals

Design work not yet accepted. Referenced by the backlog.

- [Runtime contract](docs/proposals/runtime-contract.md) — how a resolved config becomes a running agent
- [Module library](docs/proposals/module-library.md) — reusable behaviours composed into agents
- [Local UI readiness](docs/proposals/local-ui-readiness.md) — what v1 must get right for a future GUI
