---
description: Re-render an agent's generated files after a baseline change
argument-hint: "<agent-name> | --all [--check]"
allowed-tools: Bash
---

# /refresh-agent

Re-render the generated region of an agent's `CLAUDE.md` and its
`.claude/settings.json` from its current resolved configuration.

Target: **$ARGUMENTS**

```bash
# one agent
python3 builders/create-agent/scripts/render-agent.py \
  "$AGENT_TOOLKIT_HOME/agents/<agent-name>"

# all of them
python3 builders/create-agent/scripts/render-agent.py --all
```

Add `--check` to report staleness without writing anything. `--check` exits
non-zero when something is stale, so it works in a pre-commit hook or CI.

## Notes for the invoking agent

- **Show what will change before changing several agents.** For a single
  agent, just refresh it. For `--all` against more than one stale agent, run
  `--check` first and report which agents are affected, so the user sees the
  scope before it happens.
- **Nothing outside the markers is touched**, so the process the user wrote,
  their `steering.md` and their `output/` all survive. Say so if they hesitate:
  refreshing is safe by construction, not by care.
- `--all` does not stop at the first failure. One agent whose baseline has
  gone missing should not leave the other nine stale. Report per-agent
  outcomes rather than only the first error.
- This re-renders; it does not **change** the configuration. To change what an
  agent is, use `/edit-agent`.

## Migrating a stale-schema agent

`--migrate` is a different thing from a refresh. A refresh re-renders from the
current config; a migration changes the config itself because the *schema*
moved, not the baseline.

`/list-agents` shows a v1 agent as invalid, and validation says which version
it is on and that it needs migrating rather than repairing.

```bash
python3 builders/bootstrap-agent/scripts/migrate-config.py \
  "$AGENT_TOOLKIT_HOME/agents/<name>/agent.yaml" --dry-run --json   # preview
python3 builders/bootstrap-agent/scripts/migrate-config.py \
  "$AGENT_TOOLKIT_HOME/agents/<name>/agent.yaml" --json             # apply
python3 builders/create-agent/scripts/render-agent.py \
  "$AGENT_TOOLKIT_HOME/agents/<name>"                               # then refresh
```

The same script migrates baselines and agents, because the change that needed
migrating lives in a block both schemas shared. It backs up to
`agent.yaml.bak-<old-version>` first and refuses to overwrite an existing
backup — that file is the only copy of what the agent was.

Preview before applying, and read the `notes` out in full. Migration from v1
**grants** `web.search` that the agent did not have, which is a change to what
it may do, made by a command run for another reason.
