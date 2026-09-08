# Getting Started

## Prerequisites

```bash
python3 --version          # 3.8+
pip install pyyaml jsonschema
```

Set your API key — see [`environment-variables.md`](environment-variables.md):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## 0. Verify the install

```bash
cd agent-toolkit
bash scripts/verify-toolkit.sh
```

Checks every required file, both schemas, all three scripts, and runs a resolver
round-trip that confirms leaf-level merging and cycle detection actually work.

Expect two warnings on a fresh install: no API key set (if you skipped it) and no
baseline profile yet. Both are resolved by the next steps.

## 1. Launch Claude Code

```bash
cd agent-toolkit
claude
```

Commands live in `.claude/commands/`, so Claude Code needs to be running from
inside this directory for `/bootstrap-profile` and `/create-agent` to exist.

You run *from* here; nothing you create lands *in* here.

## 2. Create your baseline profile

```
/bootstrap-profile
```

Two modes:

**Express** (default) asks five questions and infers or defaults the rest:
1. Domain — what area will your agents mostly work in?
2. Audience — who is the output for?
3. Tone of voice — how should agents write?
4. Verbosity — concise, standard, or expansive?
5. Risk posture — how much unsupervised action is acceptable?

**Full** walks every characteristic, showing the default at each step.

```
/bootstrap-profile express
/bootstrap-profile full
```

You'll see the complete profile with the source of each value before anything is
written:

```
domain: "financial services"     # you
locale: "en-AU"                  # inferred from system
model: "claude-sonnet-4-6"       # default
```

Nothing is written until you accept.

**Result:** `~/.agent-toolkit/baseline.yaml`

Inspect it any time:

```bash
python3 builders/create-agent/scripts/resolve-config.py --baseline-only --summary
```

### Re-running

```
/bootstrap-profile review     # show and edit the existing profile
/bootstrap-profile migrate    # upgrade after a schema_version bump
```

Detection handles five states, so a stale, malformed, or unparseable profile gets
the right treatment rather than being silently overwritten.

## 3. Create your first agent

```
/create-agent my-first-agent
```

Four questions in Express mode: description, pattern, model, and anything else to
override. For a first agent, accepting the defaults on all but the description is
the right answer.

**Result:** `~/.agent-toolkit/agents/my-first-agent/`

```
my-first-agent/
├── agent.yaml       # extends + identity + overrides only
├── CLAUDE.md        # process skeleton — yours to fill in
├── README.md
├── steering.md      # empty; your bulk-feedback file
└── output/
```

The `agent.yaml` will be short — five or six lines. That's correct. Absence means
*inherit*, not *unset*.

### Options

```bash
/create-agent my-agent --full                              # every overridable field
/create-agent my-agent --pattern evaluator-optimizer       # pre-set the pattern
/create-agent contract-reviewer --path ~/projects/legal    # project-scoped instead
```

Use `--path` when the agent belongs to a specific repo and should be committed
with it. Otherwise the default keeps it alongside your baseline, available from
anywhere.

## 4. Write what the agent does

`/create-agent` deliberately leaves the process section of `CLAUDE.md` empty. It
scaffolds structure, not intent — guessing produces confident nonsense.

Open `~/.agent-toolkit/agents/my-first-agent/CLAUDE.md` and fill in the numbered
process steps.

## 5. Inspect what it resolves to

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/my-first-agent/agent.yaml --explain
```

```
model: claude-sonnet-4-6                # baseline
pattern: standalone                     # baseline
output_validation: true                 # agent (my-first-agent)
input_filtering: true                   # baseline
```

Every value annotated with the layer it came from. Test a change without editing
anything:

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/my-first-agent/agent.yaml \
  --set operating_constraints.model=claude-opus-5 --explain
```

## 6. Steering

`steering.md` in the agent's directory is for guidance you've thought about
offline, as opposed to turn-by-turn correction in chat. Write into it, then ask
the agent to apply it.

## The thing to internalise

Editing `~/.agent-toolkit/baseline.yaml` changes the defaults for **every** agent
that hasn't explicitly overridden that field. No regeneration, no migration.

That's the point of the design — one place to update your voice, model, or output
conventions across everything.

The trade-off is real: a baseline edit can change an agent you wrote months ago
and haven't thought about since. To pin a value against baseline drift, set it
explicitly in that agent's `agent.yaml`. An explicit override is the pin.

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `/bootstrap-profile` not found | Claude Code launched from the wrong directory | `cd agent-toolkit && claude` |
| "No baseline profile found" | `/create-agent` run before `/bootstrap-profile` | Create the profile first |
| `pyyaml is required` | Missing dependency | `pip install pyyaml` |
| Validator warns about a redundant override | `agent.yaml` restates a baseline value | Delete the line — it's pinning the field |
| Agent ignores a baseline edit | It overrides that field explicitly | Check with `resolve-config.py --explain` |
