# Repository Structure

Where everything lives and why. For how a configuration becomes a running
agent, see [`architecture.md`](architecture.md); for the reasoning behind these
choices, [`decisions.md`](decisions.md).

## The three things, kept separate

Most confusion in a toolkit like this comes from collapsing these. They are not
the same category:

| | What it is | Where it lives | Executes? | Committed? |
|---|---|---|---|---|
| **Builders** | The toolkit's own agents (Bootstrap, Validation, Design, …) | `agent-toolkit/builders/` | Yes | Yes — part of the toolkit |
| **Baseline profile** | A YAML config file. Your personalised defaults. | `~/.agent-toolkit/baseline.yaml` | **No — it's data** | No — personal, gitignored |
| **Your agents** | Things composed from the baseline | `~/.agent-toolkit/agents/` or a project dir | Yes | Depends where they live |

There is no such thing as a "baseline agent". The baseline is configuration.
Agents are what get composed from it.

`builders/` is deliberately not called `agents/` — `agents/` means "agents you
built" everywhere else in this system, and reusing the word for the toolkit's own
machinery is the fastest way back into the confusion above.

---

## User flow

```bash
git clone <repo> && cd agent-toolkit
claude

/bootstrap-profile            # interview -> writes ~/.agent-toolkit/baseline.yaml
/create-agent my-agent        # scaffolds -> ~/.agent-toolkit/agents/my-agent/
```

**Commands are invoked from inside `agent-toolkit/`.** They are registered in
`.claude/commands/`, which Claude Code loads from the working directory. This
keeps the toolkit self-contained — no install step, no copies drifting out of
sync with the repo.

Invocation location and output location are separate concerns: you run *from*
agent-toolkit, but nothing you create lands *in* it.

---

## Layout

```
agent-toolkit/                          # the toolkit — cloned, updated with git pull
├── .claude/
│   └── commands/                       # the invocable surface
│       ├── bootstrap-profile.md
│       └── create-agent.md
│
├── builders/                           # the toolkit's own agents. Run in place, never copied.
│   ├── bootstrap-agent/                # creates the baseline profile
│   │   ├── CLAUDE.md
│   │   ├── README.md
│   │   ├── bootstrap-agent-example.yaml
│   │   ├── schema/baseline-profile.schema.json
│   │   └── scripts/
│   │       ├── detect-profile.py
│   │       ├── detect-profile.sh      # interpreter probe, then delegates
│   │       └── validate-profile.py
│   └── create-agent/                   # scaffolds agents from the baseline
│       ├── CLAUDE.md
│       ├── README.md
│       ├── agent-example.yaml
│       ├── schema/agent-override.schema.json
│       └── scripts/
│           ├── resolve-config.py       # the precedence resolver
│           └── validate-agent.py
│
├── templates/                          # copied into new agents, then edited. Never run in place.
│   └── agent/
│       ├── agent.yaml
│       ├── CLAUDE.md
│       ├── README.md
│       ├── steering.md
│       └── output/.gitkeep
│
├── library/                    [6.0]   # reusable behaviour modules, composed into agents
│   ├── pattern/                        #   process skeletons: standalone, pipeline, …
│   ├── role/                           #   stance and expertise: researcher, reviewer, …
│   └── routine/                        #   procedures: web-research, structured-extract, …
│
├── runtimes/                   [4.2]   # capability-to-tool maps, one file per runtime
│   └── claude-code.yaml
│
├── scripts/
│   ├── schema_utils.py                 # schema-derived enums, known-model list
│   └── verify-toolkit.sh               # pre-flight check: files, deps, schemas, resolver
│
├── docs/
│   ├── architecture.md                 # how a config becomes a running agent
│   ├── decisions.md                    # the design record
│   ├── getting-started.md
│   ├── testing.md
│   ├── repository-structure.md         # this file
│   ├── precedence-and-inheritance.md
│   ├── environment-variables.md
│   ├── vision.md
│   ├── proposals/
│   └── research/
│
├── .gitignore
├── .env.example
├── HANDOFF.md                          # context for picking this up
└── README.md
```

**`[n.n]` marks a directory that does not exist yet**, with the `TODO.md` item
that creates it. Everything unmarked is on disk today. A layout diagram that
quietly includes directories nobody has built is the first thing a new
contributor trusts and the first thing that misleads them.

There is deliberately no `skills/`, `tools/` and `patterns/` split. One
`library/` of small typed modules replaced all three: three parallel
vocabularies is three things to maintain before anything uses one. See
`decisions.md` D14.

**`builders/` vs `templates/` — the test:** does it execute in place, or get
copied and edited? `bootstrap-agent` runs and stays put. `templates/agent/` is
scaffolding that lands somewhere else and gets modified. Never move a builder
into templates.

---

## Where your work lands

Outside the repo, always. `git pull` on the toolkit must never collide with
your agents.

```
~/.agent-toolkit/                       # personal, per-machine, never committed
├── baseline.yaml                       # your profile — written by /bootstrap-profile
├── baseline.yaml.bak-<version>         # migration backups
└── agents/                             # your agents — written by /create-agent
    └── my-agent/
        ├── agent.yaml                  # overrides only; extends the baseline
        ├── CLAUDE.md
        ├── README.md
        ├── steering.md                 # your bulk-feedback file
        └── output/
```

### Two provisioning destinations

**Default — personal agents** -> `~/.agent-toolkit/agents/<name>/`

Sits next to the baseline it inherits from. Available from any project, on this
machine, for you.

```
/create-agent my-agent
```

**`--path` — project-scoped agents** -> wherever you point it

For an agent that belongs to a specific repo, gets committed with it, and is
shared with a team.

```
/create-agent contract-reviewer --path ~/projects/legal-tool
```

Override `~/.agent-toolkit` itself with `$AGENT_TOOLKIT_HOME` if you want it
elsewhere.

---

## Explicit inheritance

Every generated `agent.yaml` names what it extends:

```yaml
schema_version: 1
extends: "~/.agent-toolkit/baseline.yaml"

name: "my-agent"
```

Not left to convention. Three reasons: the agent is self-describing about where
its defaults come from; you can point an agent at a different baseline (work vs.
personal) without touching the resolver; and a future runtime — Codex, Foundry,
the OpenWebUI wrapper — can read the YAML and know where to look without
inheriting a hardcoded assumption from Claude Code.

---

## Naming conventions

- Directories: lowercase, hyphenated — `bootstrap-agent`, not `bootstrapAgent`
- One directory per builder under `builders/`, named for the builder
- Schemas versioned by the `schema_version` field inside them, not in the
  filename — `baseline-profile.schema.json`, never `…-v1.schema.json`

## .gitignore essentials

```gitignore
output/
.env
baseline.yaml          # in case one is ever dropped in the repo by mistake
*.local.yaml
*.bak-*                # migration backups are still profiles
```
