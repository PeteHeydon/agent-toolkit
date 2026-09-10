---
description: Scaffold a new agent from a template, inheriting your baseline profile
argument-hint: "<agent-name> [--path <dir>] [--pattern <pattern>] [--web|--no-web] [--compose <kind/name>] [--express|--full]"
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /create-agent

Scaffold a new agent that inherits from the user's baseline profile.

Arguments: **$ARGUMENTS**

Read and follow the process defined in:
@../../builders/create-agent/CLAUDE.md

## Notes for the invoking agent

- **A baseline profile must exist first.** If none does, stop and tell the user
  to run `/bootstrap-profile`. Do not silently create one — the baseline is a
  deliberate, reviewed artefact, not a side effect.
- **Nothing is written into this repository.** Default destination is
  `$AGENT_TOOLKIT_HOME/agents/<name>/` (i.e. `~/.agent-toolkit/agents/<name>/`).
  `--path <dir>` provisions into a project directory instead.
- **Overrides only.** The generated `agent.yaml` contains only fields that differ
  from the baseline. Never copy the resolved config into it — that would break
  reference-based inheritance and the agent would stop tracking baseline edits.
- **File creation is deterministic, not prose.** All of it goes through
  `scaffold-agent.py`; never copy, create or edit a scaffolded file directly.
- **Web access is a question, not a vocabulary.** Ask whether the agent needs
  to look things up online and pass `--web` or `--no-web`. Never ask the user
  to name a capability, and never hand-write the `capabilities` array — it
  replaces the inherited one wholesale, so a partial list removes access
  nobody meant to remove.
- **Composed modules come from the library, never from memory.** `--compose
  <kind/name>` takes a role or routine that exists in `library/`. Offer the
  user the list from `library/README.md` rather than inventing a name; a
  module that is not there is an error, not a prompt to write one.
- This command is run from within `agent-toolkit/`. That is the invocation
  location only.
