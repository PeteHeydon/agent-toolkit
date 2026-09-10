# create-agent — Process Definition

You are running **create-agent**. Your job is to scaffold a new agent that
inherits from the user's baseline profile.

## Hard rules

1. **A baseline must exist.** Run the detection script first. If the state is
   `NONE`, stop and tell the user to run `/bootstrap-profile`. Do not create a
   baseline as a side effect — it is a deliberate artefact.
2. **Write overrides only.** The generated `agent.yaml` contains `extends`,
   identity fields, and *only* the values that differ from the baseline. Never
   flatten the resolved config into the file. An agent that copies its baseline
   stops tracking baseline edits, which defeats the whole inheritance model.
3. **Never write into the toolkit repository.** Default destination is
   `$AGENT_TOOLKIT_HOME/agents/<name>/`. `--path <dir>` overrides it.
4. **Never write a secret.** Credentials are `env:VAR_NAME` references only.
5. **Never overwrite an existing agent** without an explicit confirmation.
6. **Never hand-create or hand-edit a scaffolded file.** All file creation
   goes through `scaffold-agent.py`. If its output is wrong, the fix belongs
   in the script or in `templates/agent/`, then a re-run — not a patch applied
   here. A builder that corrects its own script's output stops being
   deterministic, which is the whole reason the script exists.

---

## Arguments

```
/create-agent <agent-name> [--path <dir>] [--pattern <pattern>]
                          [--web|--no-web] [--express|--full]
```

| Argument | Default | Meaning |
|---|---|---|
| `<agent-name>` | *required* | Slug: lowercase, hyphenated. Becomes the directory name |
| `--path <dir>` | `$AGENT_TOOLKIT_HOME/agents/` | Provision into a project directory instead |
| `--pattern <p>` | from baseline (`standalone`) | Pre-set the agent pattern |
| `--web` / `--no-web` | inherit from the baseline | Grant or withhold web access for this agent |
| `--compose <kind/name>` | none | Compose a library module; repeatable |
| `--express` | default | ~4 questions |
| `--full` | | Walk every overridable characteristic |

If `<agent-name>` is missing, ask for it. `scaffold-agent.py` is the slug
authority (Step 1 checks it); don't duplicate the rule here.

---

## Step 1 — Preconditions

```bash
python3 builders/bootstrap-agent/scripts/detect-profile.py
```

| State | Action |
|---|---|
| `NONE` | Stop. "No baseline profile found — run `/bootstrap-profile` first." |
| `VALID` | Continue |
| `STALE` | Warn, offer to run `/bootstrap-profile migrate` first. Allow the user to proceed if they insist |
| `INVALID` / `UNREADABLE` | Stop. The agent would inherit a broken baseline. Point at `/bootstrap-profile` |
| `NO_PYTHON` | Stop, and report the script's stderr verbatim. This says nothing about the baseline — the environment can't run the check. Do not tell the user to fix their profile |

If the command will not start at all (`python3: command not found`, or a
Windows install prompt), try `python` or `py -3`. Every other command in this
process uses the same interpreter, so it is worth settling once rather than
per command.

Note the baseline path detection printed — it's what Step 4 passes as
`--extends`. Never hardcode `~/.agent-toolkit/baseline.yaml`.

Then dry-run the scaffold before asking anything else, so a bad slug or a name
collision surfaces before the user has answered four questions:

```bash
python3 builders/create-agent/scripts/scaffold-agent.py \
  --name <agent-name> --dest <dest-dir> --dry-run
```

The script always prints the toolkit's one JSON envelope (`ok`, `errors`,
`warnings`, `data` — see `scripts/cli_output.py`), never plain text.

| Result | Action |
|---|---|
| `ok: true` | Continue to Step 2 |
| `errors[0].field == "name"` | Show `errors[0].message`, ask for a corrected name, dry-run again |
| `errors[0].message` says the directory already exists | Ask: overwrite, pick a different name, or cancel. On overwrite, remember to pass `--force` in Step 4 |

---

## Step 2 — Interview

Show the user what they'll inherit before asking anything, so the questions have
context:

```bash
python3 builders/create-agent/scripts/resolve-config.py --baseline-only --summary
```

### Express mode (default)

**Ask up to five questions:**
1. **Description** — one line on what this agent does
2. **Pattern** — confirm the baseline default (`standalone`) or pick another.
   Show the enumerated set. Nudge toward standalone: multi-agent patterns cost
   roughly 10–15x the tokens
3. **Model** — confirm the baseline default, or override up if this agent's work
   genuinely needs it
4. **Web access** — only ask if the user hasn't already passed `--web` or
   `--no-web`, and only as a plain question: does this agent need to look
   things up on the internet? Never make them name a capability. "It should
   research" means `--web`; "it must not reach the network" means `--no-web`;
   anything else means neither flag, and the baseline decides
5. **Anything else to override?** — offer the resolved baseline summary and let
   them name fields. Most agents override nothing here

Anything not raised is inherited, not written.

### Full mode

Walk every overridable characteristic, grouped as in
`builders/bootstrap-agent/README.md`. At each one, show the inherited value and
offer: keep (inherit, writes nothing) or override. **Keep must be the default
answer** — an override written for a value identical to the baseline is noise
that silently pins the field against future baseline edits.

Then ask about composition, which Express skips entirely. Show the index from
`library/README.md` — name, kind and one-line summary, grouped by kind — and
let the user pick roles and routines. Do not offer patterns: the pattern
question already asked that, and naming it twice is two ways to disagree.

Keep the answer short. More than four composed modules warns, and an agent
that needs six is usually two agents. If a module's `requires_capabilities`
are not granted, say so at this point rather than letting validation catch it
in Step 4 — the fix is usually `--web`, and it is cheaper to decide here.

---

## Step 3 — Confirm

Render two things:

**The overrides to be written** — as `key.path: value` pairs, which should be
short. This is what becomes the `--set` flags in Step 4, so state them in that
form now rather than reformatting later.

**The resolved configuration** — with provenance per line, so the user sees what
the agent will actually run with:

```
model: "claude-opus-5"        # this agent
pattern: "standalone"         # baseline
verbosity: "concise"          # baseline
```

**What the agent will be allowed to do.** Dry-run the scaffold with the final
flags and show `data.capabilities` from the result:

```bash
python3 builders/create-agent/scripts/scaffold-agent.py \
  --name <agent-name> --dest <dest-dir> --extends "<baseline>" \
  [--web|--no-web] [--set ...] --dry-run
```

List the capabilities with their provenance, using `inherited`, `added` and
`removed` — "inherited from the baseline" versus "added by `--web`" is the
distinction that matters, and `source` names it. A capability list is the one
part of a config a user is likely to have got wrong without noticing, so show
it in full rather than summarising it as a posture label.

Ask for acceptance. Do not proceed to Step 4 before acceptance.

---

## Step 4 — Scaffold

One invocation does all the file creation:

```bash
python3 builders/create-agent/scripts/scaffold-agent.py \
  --name <agent-name> \
  --dest <dest-dir> \
  --description "<description>" \
  --extends "<baseline path from Step 1>" \
  --set operating_constraints.pattern=<pattern> \
  --set operating_constraints.model=<model> \
  [--set <key.path>=<value> ...] \
  [--web|--no-web] \
  [--compose <kind/name> ...] \
  [--force]
```

Include a `--set` only for a field the user actually chose to override in
Step 2 or 3 — not for a value that merely confirms the baseline default. Add
`--force` only if Step 1's dry run found an existing directory and the user
chose to overwrite it.

Pass `--web` or `--no-web` rather than writing a capability list by hand. The
flags expand to the agent's *whole* inherited set plus or minus the two web
entries, because arrays replace wholesale — a hand-written list naming only
the web capabilities would silently strip the agent's file access. The script
also declines to write an override at all when the flag changes nothing, which
keeps a redundant override from pinning the field against later baseline edits.
Passing a web flag and `--set ...capabilities=` together is refused.

`--force` replaces what the toolkit owns and creates whatever is missing. It
does not delete the user's work: their process section in `CLAUDE.md`, their
`steering.md`, and their `output/` results all survive. `data.written` and
`data.preserved` in the result say which files went each way — report them
rather than describing `--force` as an overwrite.

Parse the envelope.

| `result.ok` | Meaning | Action |
|---|---|---|
| `true` | Files written, validated, and permissions rendered | Continue to Step 5 |
| `false` | Either nothing was written, or files were written but failed validation — both surface the same way | Show each entry in `result.errors` (`message`, and `legal` when it's an enum). Check `result.data.target`: if it's present, files exist on disk and must not be left broken — fix the inputs (usually a bad override value) and re-run with `--force`. If `data` is empty, nothing was written; fix and retry without `--force` |

The same invocation also renders `.claude/settings.json` from the agent's
capability set. That file, not `agent.yaml`, is what actually decides which
tools the agent can use, so `result.data.permissions` is worth reporting in
Step 5: it is the difference between a declared capability and a real one.

Never edit anything the script wrote — see Hard Rule 6.

---

## Step 5 — Report

Show the resolved config one final time, for the record:

```bash
python3 builders/create-agent/scripts/resolve-config.py <dest>/<agent-name>/agent.yaml --explain
```

Then tell the user:
- Where the agent was created
- **What it can and cannot do** — the allow and deny lists from
  `result.data.permissions`. An agent that cannot reach the network, or cannot
  write files, should learn that here rather than mid-run
- Which fields it overrides, and that everything else tracks the baseline
- That editing `~/.agent-toolkit/baseline.yaml` will change this agent's
  defaults for any field it hasn't overridden
- That `CLAUDE.md` has an empty process section waiting for them

**End with the command that runs it.** Creation and execution are separate
steps, but the user should not have to work out the second one:

```bash
cd <dest>/<agent-name> && claude        # or: ./run.sh   /   .\run.ps1
```

The `cd` is load-bearing and worth one sentence: Claude Code loads the agent's
`CLAUDE.md` and `.claude/settings.json` from the directory it starts in, so
running from anywhere else gives a plain session that has never heard of this
agent. Give the path for the user's platform, and do not offer to run it for
them.

## Related
- `README.md` — what this builder does
- `agent-example.yaml` — annotated example with all overridable fields and options
- `schema/agent-override.schema.json` — machine-readable schema
- `scripts/scaffold-agent.py` — deterministic file creation
- `scripts/resolve-config.py` — the precedence resolver
- `scripts/validate-agent.py` — override validation
- `../../docs/precedence-and-inheritance.md` — the resolution rules
