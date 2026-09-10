# create-agent

## Intent
Scaffold a new agent that inherits from your baseline profile, writing only the
values that differ.

## Usage

Run from within the `agent-toolkit/` directory:

```bash
cd agent-toolkit && claude

/create-agent my-agent                              # -> ~/.agent-toolkit/agents/my-agent/
/create-agent my-agent --full                       # walk every overridable field
/create-agent contract-reviewer --path ~/projects/legal-tool
/create-agent research-bot --pattern evaluator-optimizer
```

Requires an existing baseline — run `/bootstrap-profile` first. This command
will not create one as a side effect.

## What gets created

```
<agent-name>/
├── agent.yaml       # extends + identity + overrides ONLY
├── CLAUDE.md        # the agent's process — skeleton, yours to fill in
├── README.md        # what it does, what it inherits
├── steering.md      # empty; your bulk-feedback file
└── output/          # its output_location
```

Default destination is `$AGENT_TOOLKIT_HOME/agents/<name>/`. Use `--path` for an
agent that belongs to a specific project and should be committed with it.

Nothing is ever written into the toolkit repository.

## Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | The process — preconditions, interview, confirm, scaffold, report |
| `agent-example.yaml` | Annotated reference showing every overridable field and option |
| `schema/agent-override.schema.json` | Machine-readable schema for `agent.yaml` |
| `scripts/scaffold-agent.py` | Deterministic file creation — copies the template, writes `agent.yaml`, validates |
| `scripts/resolve-config.py` | The precedence resolver — merges layers, reports provenance |
| `scripts/validate-agent.py` | Structural + resolution + hygiene validation |

## Overrides only

The generated `agent.yaml` is deliberately near-empty. Absence of a field means
*inherit it*, not *unset it*.

This matters more than it looks. An override that restates the baseline value is
not harmless duplication — it **pins** that field, so future baseline edits stop
reaching the agent. `validate-agent.py` warns on every one it finds.

```yaml
# A complete, legal agent.yaml
schema_version: 1
extends: "~/.agent-toolkit/baseline.yaml"
name: "my-agent"
description: "Reviews contracts against the house playbook."

operating_constraints:
  pattern: "evaluator-optimizer"
```

Everything else tracks the baseline.

## Inspecting resolution

```bash
# What will this agent actually run with, and where did each value come from?
python3 scripts/resolve-config.py ~/.agent-toolkit/agents/my-agent/agent.yaml --explain

# What would this baseline give a new agent?
python3 scripts/resolve-config.py --baseline-only --summary

# Try a CLI-layer override without writing anything
python3 scripts/resolve-config.py <agent.yaml> --set operating_constraints.model=claude-opus-5 --explain
```

Output annotates every line with its source:

```
model: claude-opus-5          # agent (my-agent)
pattern: standalone           # baseline
verbosity: expansive          # CLI flag
```

Without this, a four-layer precedence chain becomes unexplainable the first time
something behaves unexpectedly.

## Merge rules

Higher precedence wins for the field it sets, and only that field. The one rule
worth carrying in your head while editing an `agent.yaml`: **arrays replace
wholesale.** To keep the baseline's tools and add one, list them all.

Everything else — leaf merging, cycle handling, provenance — is in
[`docs/precedence-and-inheritance.md`](../../docs/precedence-and-inheritance.md).

## Validation

`validate-agent.py` runs four layers:

1. **Structural** — required fields, slug format, legal enums on whatever is
   present, no secrets
2. **Resolution** — the `extends` chain reaches a real baseline, no cycles, no
   runaway depth
3. **Hygiene** — warns on overrides that restate the baseline (see above)
4. **Semantic** — stub; hook for the Validation Agent

## Related
- `../bootstrap-agent/` — creates the baseline this inherits from
- [`docs/repository-structure.md`](../../docs/repository-structure.md) — builders vs. profile vs. agents
