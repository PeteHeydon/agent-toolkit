# {{AGENT_NAME}}

{{AGENT_DESCRIPTION}}

## Running it

```bash
cd <this directory> && claude
```

or `./run.sh` on macOS and Linux, `.\run.ps1` on Windows — both are two-line
wrappers that do the `cd` for you and can be launched from anywhere.

The working directory is load-bearing. Claude Code reads `CLAUDE.md` and
`.claude/settings.json` from wherever it starts, so a session opened somewhere
else is a plain Claude Code session: no operating context, no capability
limits, no process. If the agent seems to have forgotten everything about
itself, this is almost always why.

## Inherits from

`~/.agent-toolkit/baseline.yaml`, by reference at runtime. Editing the baseline
changes this agent's defaults for any field it hasn't overridden — no
regeneration needed.

## Overrides

See `agent.yaml`. Absence of a field there means *inherit*, not *unset*.

Inspect the resolved configuration at any time:

```bash
python3 <path-to-agent-toolkit>/builders/create-agent/scripts/resolve-config.py \
  agent.yaml --explain
```

## Files

| File | Purpose | Yours to edit? |
|---|---|---|
| `agent.yaml` | Overrides on top of the baseline — `extends` + identity + only what differs | Yes, but the toolkit rewrites it |
| `CLAUDE.md` | What this agent knows and does. The marked region is generated from `agent.yaml` and the baseline; the Process and Notes sections are yours | Partly — everything outside the markers |
| `README.md` | This file: what the agent does, for humans | Yes |
| `steering.md` | Bulk feedback file — offline guidance the agent reads and applies on request | Yes |
| `output/` | Where this agent's results land | Yes |
| `run.sh` / `run.ps1` | Two-line wrappers that start Claude Code in this directory | Yes |
| `.claude/settings.json` | Tool permissions, compiled from this agent's capabilities | No — regenerated |
| `.agent/` | Toolkit bookkeeping, including what config the permissions came from | No — regenerated |

`README.md`, `steering.md`, `output/` and the Process and Notes sections of
`CLAUDE.md` are yours. Re-running `/create-agent` over this directory updates
the configuration and leaves them alone, so a process you have written here
survives.

`agent.yaml`, `.claude/`, `.agent/` and the marked region inside `CLAUDE.md`
are regenerated — record intent in the Process or Notes sections rather than
in comments there.

Two of those are worth reading even though you don't edit them. The generated
region of `CLAUDE.md` is what this agent is actually told about itself, and
`.claude/settings.json` is what decides which tools it can use. To change
either, change `agent.yaml` or the baseline and re-render.

Full rule: `docs/architecture.md`, "Who owns what".
