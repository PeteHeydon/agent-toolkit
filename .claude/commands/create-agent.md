---
description: Scaffold a new agent from a template, inheriting your baseline profile
argument-hint: "<agent-name> [--path <dir>] [--pattern <pattern>] [--express|--full]"
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
- This command is run from within `agent-toolkit/`. That is the invocation
  location only.
