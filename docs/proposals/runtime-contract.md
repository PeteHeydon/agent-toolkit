# Proposal: the runtime contract

Status: **accepted**. Recorded as D10 to D13 in [`../decisions.md`](../decisions.md).
Referenced by `TODO.md` items 3.x, 4.x and 5.x.

## The problem in one line

The configuration layer and the behaviour layer are not connected: a resolved
configuration is produced by `resolve-config.py` and consumed by nothing, while
the only artefact that reaches a model is a `CLAUDE.md` the toolkit
deliberately leaves nearly empty.

Every symptom traces back to that. Agents have no web access because
permissions are declared in YAML that nothing enforces. New agents feel empty
because the one file that reaches the runtime is the one file the toolkit
doesn't write. There is no reuse below "whole agent" because there is nothing
for a reusable unit to be composed *into*.

## The pipeline

```
  baseline.yaml  ──┐
                   ├──► resolve ──► resolved config ──► render ──► run
  agent.yaml     ──┘   (exists)                        (missing)   (manual)
                                                            │
                                              ┌─────────────┴─────────────┐
                                              ▼                           ▼
                                     CLAUDE.md (generated region)   .claude/settings.json
```

`resolve` exists and works. `render` is the missing step. `run` is
`cd <agent-dir> && claude`, per OD1.

## Capabilities

### Vocabulary

`operating_constraints.permissions_scope.tools` is replaced by
`capabilities`, a closed set. Small on purpose — it grows when a runtime
mapping needs a distinction it cannot express.

| Capability | Grants |
|---|---|
| `file.read` | Reading files in scope |
| `file.search` | Searching file contents and paths |
| `file.write` | Creating and editing files in scope |
| `shell` | Running commands |
| `web.search` | Searching the web |
| `web.fetch` | Retrieving a named URL |
| `subagent` | Delegating to a sub-agent |

`filesystem` (`workspace_only` / `read_only` / `full`) keeps its current
meaning and bounds the `file.*` capabilities. `external_calls` is removed — it
said less than `web.*` and `subagent` say together.

### Shape

```yaml
operating_constraints:
  permissions_scope:
    filesystem: workspace_only
    capabilities:
      - file.read
      - file.search
      - file.write
      - web.search
      - web.fetch
    web:
      allowed_domains: []     # empty means any
      blocked_domains: []
```

`capabilities` is an array, so D4 applies: an agent that overrides it lists
every capability it wants, including the inherited ones. The `web` block holds
parameters only, never grants — a domain list with no `web.fetch` capability is
a validation warning.

### Runtime mapping

One data file per runtime, at `runtimes/claude-code.yaml`, so the mapping is
auditable and a second runtime is a second file rather than a code change.

| Capability | Claude Code tools |
|---|---|
| `file.read` | `Read`, `Glob` |
| `file.search` | `Grep`, `Glob` |
| `file.write` | `Write`, `Edit`, `NotebookEdit` |
| `shell` | `Bash` |
| `web.search` | `WebSearch` |
| `web.fetch` | `WebFetch` |
| `subagent` | `Task` |

Rendered into `<agent-dir>/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["Read", "Glob", "Grep", "Write", "Edit", "WebSearch", "WebFetch"],
    "deny": ["Bash"]
  }
}
```

`deny` is written for withheld high-consequence tools (`Bash` without `shell`;
`Write` and `Edit` under `filesystem: read_only`) so the absence of a grant is
explicit rather than dependent on the user's global settings.

**This file is always written inside the agent's own directory**, including
under `--path`. The toolkit never merges into a host project's
`.claude/settings.json`.

### Defaults, and the web access question

The risk-posture question in `/bootstrap-profile` already exists and already
claims to set `permissions_scope` and `guardrails`. Give it a defined mapping
rather than adding a sixth Express question:

| Risk posture | filesystem | capabilities | guardrails |
|---|---|---|---|
| Cautious | `read_only` | `file.read`, `file.search`, `web.search` | `output_validation: true`, `human_in_the_loop: true` |
| **Balanced** (default) | `workspace_only` | the above plus `file.write`, `web.fetch` | `output_validation: true` |
| Autonomous | `full` | the above plus `shell`, `subagent` | `output_validation: false` |

So web search is granted at every posture and page fetching at all but the
strictest. Per-agent, `/create-agent` gains `--web` and `--no-web`, and shows
the granted capability set on its confirm screen — the point at which a missing
grant is cheapest to notice.

### Schema impact

This is a breaking change to both schemas: `schema_version` 1 to 2. That is
deliberate. The migration path (`detect-profile` returning `STALE`, then
bootstrap Step 4) has never been exercised, and this is a change small enough
to prove it on. The mapping is mechanical:

| v1 | v2 |
|---|---|
| `tools: ["read"]` | `capabilities: [file.read]` |
| `tools: ["write"]` | `capabilities: [file.read, file.write]` |
| `tools: ["search"]` | `capabilities: [file.search]` |
| `external_calls: true` | `capabilities: [web.search, web.fetch]` |
| `external_calls: false` | `capabilities: [web.search]`, plus a migration note that the default changed |

## The generated `CLAUDE.md`

### Structure

```markdown
# <agent-name>

<description>

<!-- BEGIN GENERATED render:v1 config-hash:sha256:… -->
## Operating context
## Voice
## Capabilities and limits
## Output
## Composed modules          (only when modules are composed)
<!-- END GENERATED -->

## Process
1. …                          user-owned, seeded from the pattern

## Notes
                              user-owned, free
```

Everything between the markers is machine-owned and regenerated wholesale.
Everything outside them is never touched by the renderer.

### What each section renders from

| Section | Source fields | Rendered as |
|---|---|---|
| Operating context | `identity_context` | "You work in <domain>. Your output is for <audience>. Use <locale> spelling, dates and currency." |
| Voice | `voice_style` | Directives: tone, verbosity, and formatting conventions only where non-default |
| Capabilities and limits | `permissions_scope`, `guardrails` | What the agent may and may not do, stated positively then negatively |
| Output | `interop`, `steering` | Format contract, destination, escalation path, and the instruction to read `steering.md` when it is non-empty |
| Composed modules | `compose` | Module bodies, inlined |

### The rule that keeps it small

**Render a line only where it changes behaviour.** Identity, voice, capability
limits and the output contract always render, because they are personalised by
definition. Guardrail booleans at their default value, and formatting
conventions at their default value, render nothing: a line saying
`input_filtering: true` costs tokens and changes no behaviour a competent agent
would not already exhibit.

Target the generated region at 80 lines. Warn above 150.

### The process section

Seeded from `library/pattern/<pattern>.md`, not left blank. For `standalone`:

```markdown
## Process

1. Restate the task in one line and confirm you have the inputs it needs.
2. TODO: the work this agent does. Replace this step.
3. Check the result against the constraints above before returning it.
4. Write the output per the contract above.
```

`validate-agent.py` warns while the `TODO:` marker is present. An agent whose
intent has never been written becomes a known, reportable state rather than a
surprise at run time.

### Staleness

The `config-hash` in the BEGIN marker is a hash of the resolved configuration
at render time. `render-claude-md.py --check` recomputes it and exits non-zero
on a mismatch. This is what reconciles a rendered artefact with D2: the
baseline is still the source of truth, and drift from it is detectable rather
than silent.

## Scripts

| Script | Responsibility |
|---|---|
| `scaffold-agent.py` | Create the directory, copy the template, write `agent.yaml`, call the renderer, call the validator. All the deterministic file work. |
| `render-claude-md.py` | Render the generated region and `.claude/settings.json` from a resolved config. `--check` for staleness, `--stdout` for a dry run. |

Both exist so that the deterministic half of `/create-agent` is executable and
testable rather than prose in a builder's `CLAUDE.md`. The builder keeps the
interview and the confirm step, which genuinely need a model.
