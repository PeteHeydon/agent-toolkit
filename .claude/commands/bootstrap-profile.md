---
description: Create or update the personalised baseline profile that all agents inherit from
argument-hint: "[express|full|review|migrate]"
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /bootstrap-profile

Invoke the bootstrap-agent to create, review, or update the user's **baseline
profile** — the single canonical set of characteristics every agent built with
this toolkit inherits from.

Mode requested: **$1** (if empty, ask; see the process below)

Read and follow the process defined in:
@../../builders/bootstrap-agent/CLAUDE.md

## Notes for the invoking agent

- **This command produces a profile, not an agent.** The baseline is a config
  file. Do not scaffold, generate, or run an agent here — that is `/create-agent`.
- The profile is always written to `$AGENT_TOOLKIT_HOME/baseline.yaml`
  (default `~/.agent-toolkit/baseline.yaml`), never into this repository. A
  single canonical location is what makes inheritance work.
- This command is run from within `agent-toolkit/`. That is the invocation
  location only — nothing is created inside the repo.
