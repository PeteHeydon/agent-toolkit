# Precedence & Inheritance

## The four layers

Values resolve lowest to highest. Higher always wins — but **only for the field
it sets**.

```
4. In-session instruction    "for this run, be expansive"        highest
3. CLI flag                  --model=claude-opus-5
2. Agent override            <agent-dir>/agent.yaml
1. Baseline profile          ~/.agent-toolkit/baseline.yaml       lowest
```

The baseline is named explicitly by each agent, not assumed:

```yaml
# agent.yaml
extends: "~/.agent-toolkit/baseline.yaml"
```

This keeps the agent self-describing and lets you point different agents at
different baselines — a work profile and a personal one, say — without changing
the resolver.

## Field-level, not wholesale

This is the rule that matters most. An agent that overrides `model` still
inherits `tone_of_voice`, `output_location`, `guardrails`, and everything else
from the baseline. There is no "this agent has its own config now, stop
inheriting" state.

```yaml
# agent.yaml — a complete, legal agent override
schema_version: 1
extends: "~/.agent-toolkit/baseline.yaml"
name: "my-agent"

operating_constraints:
  model: "claude-opus-5"
  pattern: "evaluator-optimizer"
```

Everything else comes from the baseline. Two overridden fields is a valid file.

## Reference, not copy

Agents **reference** the baseline at runtime. They do not snapshot it at
creation time.

The consequence, which is the whole point: edit `~/.agent-toolkit/baseline.yaml`
and every agent that hasn't overridden that field picks up the change on its
next run. No regeneration, no migration, no hunting through directories for
stale copies.

The trade-off is real and worth naming: a baseline edit can change the behaviour
of an agent you wrote six months ago and haven't thought about since. If you need
an agent pinned against baseline drift, override the fields explicitly in its
`agent.yaml` — an explicit override is the pin.

## Nested values

Nested maps merge at the leaf, not the branch. This:

```yaml
# baseline.yaml
operating_constraints:
  guardrails:
    input_filtering: true
    output_validation: false
    human_in_the_loop: false
```

```yaml
# agent.yaml
operating_constraints:
  guardrails:
    output_validation: true
```

resolves to `input_filtering: true`, `output_validation: true`,
`human_in_the_loop: false`. The agent override does **not** wipe the sibling keys.

## Arrays replace, they don't merge

`permissions_scope.tools` and `default_context_sources` are replaced wholesale by
a higher layer, not appended to. If an agent needs the baseline tools plus one
more, it lists all of them. Merging arrays silently is how an agent ends up with
permissions nobody granted it.

## Resolution debugging

Every consumer should be able to answer "where did this value come from?" — the
confirm step in the bootstrap process renders exactly this, and agent runtimes
should expose the same:

```
model: "claude-opus-5"        # agent override
tone_of_voice: "neutral"      # baseline
verbosity: "expansive"        # in-session instruction
```

Without this, a four-layer precedence chain becomes unexplainable the first time
something behaves unexpectedly.

The resolver implements this:

```bash
python3 builders/create-agent/scripts/resolve-config.py <agent.yaml> --explain
```

It walks the `extends` chain, merges by the rules above, and annotates every
resolved value with the layer it came from. `--set key.path=value` applies a
CLI-layer override so you can test one without editing a file.
