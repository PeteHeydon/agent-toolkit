# Agent Toolkit — Vision Statement

Date: September 2026

## Vision

Build a composable agent toolkit: a library of skills, tools, and agents that can be assembled, edited, and run to create purpose-built agents on demand. The system should let someone describe an outcome — *"build me an agent that does…"* — and have the toolkit compose the right skills, tools, and sub-agents into a working agent, ready to run.

Agents should be simple and easy to use, with a focus on a professional context.

## Core Concept

- **Composable agents** — agents are built from reusable modules, not written from scratch each time.
- **Modules** — the building blocks agents draw on:
  - Skills, knowledge, and context
  - Tools
  - Git integration with auto-update
  - Optimisation across tokens, compaction, and file handling
- **Bootstrap** — every agent starts from a profile file covering localisation and tone of voice, so new agents inherit sensible defaults rather than being configured from zero.
- **Patterns** — recurring patterns become the process for building agents, not assumptions. The toolkit should encode *how* agents get built as reusable process, so quality and consistency scale as the library grows.

## What the Toolkit Does

1. **Create/edit agents** — define an agent from a library of skills, tools, and existing agents; compose and configure rather than hand-code.
2. **Run agents** — execute the composed agent against a task, with the supporting modules (optimisation, git auto-update, bootstrap profile) operating in the background.

## Sub-Agents

The toolkit itself is builder-agnostic, but the build/maintenance process is imagined as its own set of specialised agents.  Potential indicative sub-agents include:

- **Agent Refinement Agent** — iterates and improves existing agent definitions
- **Agent Skills Agent** — manages the skills library available to agents
- **Bootstrap Agent** — handles profile/localisation/tone-of-voice setup for new agents
- **Validation Agent** — checks agents for correctness before they're run
- **Design Agent** — assists in structuring/designing new agents
- **Agent Ops Agent** — handles operational concerns (running, monitoring)
- **Documentation Agent** — generates and maintains documentation for agents
- **TOV (Tone of Voice) Agent** — enforces consistent voice across agents
- **Agent Optimisation Agent** — manages token/context/file optimisation
- **Agent Tool Agent** — manages the tool library agents can call
- **Agent Security Agent** — handles security/safety review of agents



## Release Roadmap

**v1 — Claude Code**
The initial build runs on Claude Code, targeting a CLI-first workflow for building and running composable agents.

**Future releases**
- **Codex support** — extend the toolkit to run on Codex as an alternative execution environment
- **AWS / Azure AI Foundry support** — bring the toolkit into cloud-native agent platforms
- **Private Agents** utilising the likes of an OpenWebUI wrapper, enableing a browser-based desktop experience for people not comfortable with a CLI, exposing the same create/edit/run workflow through a GUI



## Broader Integration

- Cross-platform: works alongside Claude and ChatGPT/M365 Copilot workflows
- Applicable to both business and personal/professional use
- Patterns discovered through use feed back into the agent-building process itself — the toolkit should **build from process, not assumption**
