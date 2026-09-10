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

Checks every required file, both schemas, every script, the library modules,
and runs a resolver round-trip that confirms leaf-level merging and cycle
detection actually work.

Expect three warnings on a fresh install:

- No API key set, if you skipped it, and no baseline profile yet. The next two
  steps resolve both.
- Four patterns have no process skeleton yet, so agents built on them fall back
  to the `standalone` steps. Harmless, and not something you need to act on.

Anything reported as **FAIL** is different — stop and fix it before going on.

## On Windows

Every command in this guide starts with `python3`, which frequently is not what
works on Windows. Settle this once, before the first command:

```powershell
python3 --version      # if this prints a version, you are fine as written
python  --version      # otherwise try this
py -3   --version      # or this
```

If `python3` opens the Microsoft Store instead of printing a version, that is
the **App Execution Alias** — a stub Windows ships that is not an interpreter.
It is the single most common first-run failure with this toolkit, and it is
confusing because the command appears to exist. Either turn the alias off under
*Settings > Apps > Advanced app settings > App execution aliases*, or use
`python` / `py -3` and read `python3` as "whichever of these worked" throughout
the docs.

Two other things worth knowing:

- **`bash scripts/verify-toolkit.sh` needs Git Bash or WSL.** Only the
  pre-flight check and the interpreter probe are bash; everything in the path
  you actually walk is Python (D15). If you have neither, skip the pre-flight
  and run the test suite instead — it covers more.
- **`$AGENT_TOOLKIT_HOME` defaults to `%USERPROFILE%\.agent-toolkit`**, which
  is `C:\Users\<you>\.agent-toolkit`. Set it if you want your profile and
  agents somewhere else; every script reads it.

If a script cannot find an interpreter at all, tell it which one to use:

```powershell
$env:AGENT_TOOLKIT_PYTHON = "C:\Path\To\python.exe"
```

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
model: "claude-sonnet-5"       # default
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

Detection handles six states, so a stale, malformed, or unparseable profile
gets the right treatment rather than being silently overwritten. `migrate`
backs the original up to `baseline.yaml.bak-<version>` before it writes, and
tells you what the version bump changed on your behalf.

## 3. Create your first agent

```
/create-agent my-first-agent
```

Up to five questions in Express mode: description, pattern, model, whether it
needs web access, and anything else to override. For a first agent, accepting
the defaults on all but the description is the right answer.

**Result:** `~/.agent-toolkit/agents/my-first-agent/`

```
my-first-agent/
├── agent.yaml            # extends + identity + overrides only
├── CLAUDE.md             # generated region + your process + your notes
├── README.md
├── steering.md           # empty; your bulk-feedback file
├── run.sh / run.ps1      # start Claude Code in this directory
├── .claude/
│   └── settings.json     # generated: the tools this agent may use
├── .agent/
│   └── render.json       # generated: what config the above came from
└── output/
```

The `agent.yaml` will be short — four or five lines for an agent that
overrides nothing. That's correct. Absence means *inherit*, not *unset*.

Three of those are generated and will be rewritten: `agent.yaml`, `.claude/`
and `.agent/`, plus the marked region inside `CLAUDE.md`. Everything else is
yours and no toolkit command will touch it. Full rule:
[`architecture.md`](architecture.md), "Who owns what".

### Options

```bash
/create-agent my-agent --full                              # every overridable field
/create-agent my-agent --pattern evaluator-optimizer       # pre-set the pattern
/create-agent researcher --web                             # grant web access
/create-agent redactor --no-web                            # withhold it
/create-agent researcher --compose routine/web-research    # add library guidance
/create-agent contract-reviewer --path ~/projects/legal    # project-scoped instead
```

Use `--path` when the agent belongs to a specific repo and should be committed
with it. Otherwise the default keeps it alongside your baseline, available from
anywhere.

`--compose` pulls in a module from [`library/`](../library/README.md) — a role
or a routine — and inlines its guidance into the agent's generated region. Run
`/create-agent --full` to be offered the list rather than memorising names.

## 4. Write what the agent does

`/create-agent` seeds the process from the agent's pattern and leaves exactly
one step for you:

```markdown
1. Restate the task in one line and confirm you have the inputs it needs.
2. TODO: the work this agent does. Replace this step.
3. Check the result against the constraints above before returning it.
4. Write the output per the contract above.
```

Steps 1, 3 and 4 are properties of the pattern, so the toolkit can write them.
Step 2 is intent, and guessing at intent produces confident nonsense — so it
stays yours. Open `~/.agent-toolkit/agents/my-first-agent/CLAUDE.md` and
replace it.

Until you do, `/list-agents` reports the agent as unfinished and validation
warns. That is deliberate: an agent nobody finished should be a state you can
see, not a surprise on its first run.

## 5. Inspect what it resolves to

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/my-first-agent/agent.yaml --explain
```

```
# Resolution chain (lowest precedence first):
#   ~/.agent-toolkit/baseline.yaml
#   ~/.agent-toolkit/agents/my-first-agent/agent.yaml

...
operating_constraints:
  model: claude-sonnet-5                             # baseline
  pattern: standalone                                # baseline
  permissions_scope:
    filesystem: workspace_only                       # baseline
    capabilities: [file.read, file.search, ...]      # baseline
...
```

The whole resolved configuration, every value annotated with the layer it came
from. An agent that overrode nothing says `# baseline` on all but its `name`
and `description` — which is what a near-empty `agent.yaml` predicts. It runs
to fifty-odd lines, so pipe it through `grep` when chasing one field. Test a
change without editing anything:

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/my-first-agent/agent.yaml \
  --set operating_constraints.model=claude-opus-5 --explain
```

## 6. Run it

```bash
cd ~/.agent-toolkit/agents/my-first-agent && claude
```

or `./run.sh` (`.\run.ps1` on Windows), which does the `cd` for you from
anywhere.

The working directory is load-bearing. Claude Code reads `CLAUDE.md` and
`.claude/settings.json` from wherever it starts, so a session opened elsewhere
is a plain Claude Code session with none of this agent's context or limits.

## 7. Steering

`steering.md` in the agent's directory is for guidance you've thought about
offline, as opposed to turn-by-turn correction in chat. Write into it, then ask
the agent to apply it.

It is also the input to `/review-agent`. A correction you have written three
times should probably stop being a correction and become part of the agent —
a config value, a composed module, or a process step. That command reads the
file and tells you which.

## 8. Living with your agents

Once you have more than one, five commands cover the rest of the life:

| Command | What it does |
|---|---|
| `/list-agents` | Every agent: what it pins, whether it validates, whether it has drifted |
| `/refresh-agent <name>` or `--all` | Re-render after a baseline change |
| `/edit-agent <name> --set <field>=<value>` | Change one thing without restating the rest |
| `/validate-agent <name>` | Is this agent correct? Mechanical findings and judgment, reported apart |
| `/review-agent <name>` | Should this agent become something else? Proposes, never writes |

The last two are easy to confuse. Validation asks *is this right*; review asks
*should this change*. An agent can be perfectly valid and still be the wrong
agent.

## The thing to internalise

Editing `~/.agent-toolkit/baseline.yaml` changes the defaults for **every**
agent that hasn't explicitly overridden that field. That's the point: one place
to update your voice, model, or output conventions across everything.

**But there is a second half, and it is the thing most likely to confuse you.**
Configuration resolves live; the instructions an agent actually reads are
rendered once. So after a baseline edit:

```bash
# the resolved config changes immediately
python3 builders/create-agent/scripts/resolve-config.py <agent.yaml> --explain
#   verbosity: expansive          # baseline

# the agent's CLAUDE.md does not, until you re-render
#   "Be concise. Prefer bullets to prose..."
```

`/list-agents` reports that gap as **STALE**, and `/refresh-agent --all` closes
it. Nothing is lost while an agent is stale — its process, notes and results
are untouched — but it is running on out-of-date instructions until you
refresh, so refresh after a baseline edit.

The trade-off is real in the other direction too. A baseline edit can change an
agent you wrote months ago and haven't thought about since. To pin a value
against that, set it explicitly in the agent's `agent.yaml` — an explicit
override is the pin, and `/list-agents` shows you what each agent pins.

How the layers merge, in full:
[`precedence-and-inheritance.md`](precedence-and-inheritance.md).

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `/bootstrap-profile` not found | Claude Code launched from the wrong directory | `cd agent-toolkit && claude` |
| `python3` opens the Microsoft Store | Windows App Execution Alias, not an interpreter | Use `python` or `py -3`, or turn the alias off — see "On Windows" above |
| `python3: command not found` | Not on PATH under this name | Try `python` or `py -3`; set `$AGENT_TOOLKIT_PYTHON` to pin one |
| `bash: command not found` | Only the pre-flight check and interpreter probe need bash | Install Git Bash or WSL, or skip them and run the test suite |
| `NO_PYTHON` from profile detection | The environment cannot run the check; **your profile has not been read** | Fix the interpreter. Do not edit your profile — nothing is known to be wrong with it |
| "No baseline profile found" | `/create-agent` run before `/bootstrap-profile` | Create the profile first |
| `pyyaml is required` | Missing dependency | `pip install pyyaml` |
| Validator warns about a redundant override | `agent.yaml` restates a baseline value | Delete the line — it's pinning the field |
| Agent ignores a baseline edit | It overrides that field explicitly | Check with `resolve-config.py --explain`; an override is a deliberate pin |
| Agent behaves as if the baseline never changed | Its `CLAUDE.md` was rendered before the edit | `/refresh-agent <name>`. `/list-agents` shows this as **STALE** |
| Validation warns about a `TODO:` step | The agent's process was never written | Replace step 2 of its `CLAUDE.md` with what the agent actually does |
| `compose: routine/web-research` fails validation | The agent lacks a capability the module needs | `/edit-agent <name> --web`, or drop the module |
| An edit dropped my other overrides | `--force` replaces; `--merge` is what an edit needs | Use `/edit-agent`, which passes `--merge` for you |
