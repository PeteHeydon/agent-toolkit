# Architecture

How a configuration becomes a running agent. Read this before changing
anything that touches config, scaffolding, or what an agent sees at run time.

Design rationale for each call below: [`decisions.md`](decisions.md).

## The pipeline

```
  baseline.yaml  ──┐
                   ├──► resolve ──► resolved config ──► render ──► run
  agent.yaml     ──┘
  CLI flags      ──┘
                                                            │
                                              ┌─────────────┴─────────────┐
                                              ▼                           ▼
                                     CLAUDE.md                    .claude/settings.json
                                  (generated region)             (tool permissions)
```

Four stages. Three exist today; `run` is a documented command rather than
machinery the toolkit owns.

| Stage | What it does | Where it lives |
|---|---|---|
| **resolve** | Merge the precedence layers into one config, annotated with where each value came from | `builders/create-agent/scripts/resolve-config.py` |
| **render** | Compile the resolved config into artefacts a runtime actually reads | `render-agent.py` + `runtimes/claude-code.yaml` |
| **run** | `cd <agent-dir> && claude` | The user's shell |

The thing to understand: **a resolved configuration changes nothing on its
own.** It is data. Render is the step that turns a declared model, permission
set or tone into something that reaches a running agent. A field that render
does not consume is documentation, however well validated.

## Resolve

Four layers, lowest to highest. Higher wins for the field it sets, and only
that field.

```
4. In-session instruction    "for this run, be expansive"      highest
3. CLI flag                  --set operating_constraints.model=…
2. Agent override            <agent-dir>/agent.yaml
1. Baseline profile          ~/.agent-toolkit/baseline.yaml     lowest
```

Nested maps merge at the leaf, so sibling keys survive. Arrays replace
wholesale, so a permission list is never silently extended. Agents reference
the baseline at runtime rather than copying it, which is why editing the
baseline changes every agent that hasn't pinned that field.

Full rules, including why: [`precedence-and-inheritance.md`](precedence-and-inheritance.md).

```bash
python3 builders/create-agent/scripts/resolve-config.py <agent.yaml> --explain
```

`--explain` annotates every value with the layer it came from. Any behaviour
that surprises you starts here.

## Render

Render reads a resolved config and writes two artefacts into the agent's own
directory. Never into a parent project, including under `--path`.

**`CLAUDE.md`** — the file Claude Code loads as project memory, and the only
artefact that reaches the model. Everything derivable from the config is
generated into a marked region: identity and domain, voice and verbosity,
capability limits, the output contract, and any composed library modules. The
process section outside that region belongs to the user, seeded from the
agent's pattern.

**`.claude/settings.json`** — tool permissions, mapped from the agent's
capability set through `runtimes/claude-code.yaml`. This is the step that
makes a permission field real rather than decorative.

Allow and deny are not symmetric, and the difference is the whole point.
Allowing a tool stops Claude Code prompting for it. Denying one stops it
running. An un-allowed tool still prompts, and a prompt at the wrong moment
gets answered yes — so a capability that was deliberately withheld and is
expensive to misuse is denied outright rather than merely left off the allow
list. Which tools those are is per-runtime data (`high_consequence`), not a
toolkit-wide judgement.

Filesystem posture is applied after capabilities and wins over them: a config
granting `file.write` under `filesystem: read_only` is contradictory, and the
safe reading of a contradiction is the restrictive one. A tool that would land
in both lists is dropped from `allow`, because a settings file that grants and
forbids the same tool decides nothing.

Two rules govern what render writes:

- **Machine-owned regions are regenerated wholesale.** Content between the
  `BEGIN GENERATED` and `END GENERATED` markers is replaced on every render;
  content outside them is never touched. Edits inside the region are lost.
- **Rendered output carries a hash of the config it came from.** That is what
  keeps D11 honest: the baseline is still the source of truth, and an agent
  whose rendered files have fallen behind a baseline edit reports as stale
  rather than drifting silently.

## Run

An agent is a directory you run Claude Code in.

```bash
cd ~/.agent-toolkit/agents/my-agent && claude
```

The working directory is load-bearing. It is what loads the agent's
`CLAUDE.md` as memory, applies its `.claude/settings.json` permissions, and
puts `output/` where the agent expects it. Running from elsewhere gives you a
plain Claude Code session that has never heard of the agent.

## An agent directory

```
my-agent/
├── agent.yaml              # source of truth: extends + identity + overrides only
├── CLAUDE.md               # generated region + user-owned process
├── README.md               # what this agent does, for humans
├── steering.md             # bulk feedback: offline guidance, applied on request
├── .claude/
│   └── settings.json       # generated: tool permissions from the capability set
├── .agent/
│   └── render.json         # generated: the config hash the rendered files came from
└── output/                 # where results land
```

### Who owns what

An agent directory holds two kinds of file, and a toolkit script may only
touch one of them.

| Path | Owner | May a script rewrite it? |
|---|---|---|
| `agent.yaml` | toolkit | Yes — regenerated from your answers |
| the marked region inside `CLAUDE.md` | toolkit | Yes — replaced wholesale, per D11 |
| `.claude/` | toolkit | Yes — derived from the capability set |
| `.agent/render.json` | toolkit | Yes — what config the rendered files came from |
| `CLAUDE.md` outside the markers | you | Never |
| `README.md` | you | Created once, never rewritten |
| `steering.md` | you | Created once, never rewritten |
| `output/` | you | Never |
| anything else you put there | you | Never |

**Nothing outside the toolkit-owned set is ever written or deleted by a
toolkit script.** That includes `--force`, which replaces what the toolkit
owns and creates whatever is missing, but never removes your work: re-running
`/create-agent` over an existing agent updates its configuration and leaves
the process you wrote, the guidance you recorded, and the results it produced
exactly where they were.

Two things follow from the rule. `output/` stays a flat directory of your
results, so any per-run bookkeeping the toolkit ever needs goes in `.agent/`
rather than accumulating alongside them. And `.agent/` is reserved now, while
reserving it is free — a name claimed after someone has already used it is a
migration.

`agent.yaml` is written by hand or by `/create-agent`. `CLAUDE.md`'s generated
region and `.claude/settings.json` are written by render, and regenerating
them is always safe.

## Where the toolkit's own machinery lives

| | What | Executes in place? |
|---|---|---|
| `builders/` | The toolkit's own agents — bootstrap, create-agent, validation | Yes |
| `templates/` | Copied into a new agent, then edited | No |
| `library/` | Reusable behaviour modules, inlined at render time. User library shadows this one | No — read by render |
| `runtimes/` | Capability-to-tool mappings, one file per target runtime | No — read by render |
| `scripts/` | Shared helpers and the pre-flight check | — |

The test for `builders/` versus `templates/`: does it run where it sits, or
get copied somewhere else and modified? Layout detail:
[`repository-structure.md`](repository-structure.md).

## Extending to another runtime

The capability vocabulary and `runtimes/*.yaml` exist so that supporting Codex
or Foundry is a second mapping file and a second render target, not a rewrite.
`extends` is an explicit path rather than a convention for the same reason: an
agent describes where its defaults come from without assuming who is reading
it.

Nothing above the render step is Claude Code specific. That is deliberate, and
worth preserving.
