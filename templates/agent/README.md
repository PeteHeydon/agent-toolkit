# {{AGENT_NAME}}

{{AGENT_DESCRIPTION}}

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

| File | Purpose |
|---|---|
| `agent.yaml` | Overrides on top of the baseline — `extends` + identity + only what differs |
| `CLAUDE.md` | The process this agent follows |
| `steering.md` | Bulk feedback file — offline guidance the agent reads and applies on request |
| `output/` | Where this agent's results land |
