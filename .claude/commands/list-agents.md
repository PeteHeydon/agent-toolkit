---
description: Show every agent you have built, with what it pins and whether it has drifted
argument-hint: ""
allowed-tools: Bash
---

# /list-agents

Report on every agent under `$AGENT_TOOLKIT_HOME/agents/`.

```bash
python3 builders/create-agent/scripts/agent-status.py
```

That is the whole command. The script prints the table; add `--json` if you
need to act on the result rather than show it.

## Reading the result

| Column | What it means |
|---|---|
| `VALID` | `agent.yaml` resolves and validates. `n warn` is valid with warnings |
| `RENDERED` | `fresh`, `STALE`, or `never`. Stale means the baseline moved on after this agent was last rendered |
| `FINISHED` | Whether anyone has replaced the seeded `TODO:` step with what the agent actually does |
| `OVERRIDES` | What this agent pins — and therefore the fields a baseline edit will **not** reach |

The last column is the one people misread. An override is not just a setting:
it is a decision to stop tracking the baseline for that field. When someone
asks why a baseline change did not affect an agent, this column is the answer.

`STALE` is fixed by `/refresh-agent`. Do not fix it by hand.
