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

---

## Arguments

```
/create-agent <agent-name> [--path <dir>] [--pattern <pattern>] [--express|--full]
```

| Argument | Default | Meaning |
|---|---|---|
| `<agent-name>` | *required* | Slug: lowercase, hyphenated. Becomes the directory name |
| `--path <dir>` | `$AGENT_TOOLKIT_HOME/agents/` | Provision into a project directory instead |
| `--pattern <p>` | from baseline (`standalone`) | Pre-set the agent pattern |
| `--express` | default | ~4 questions |
| `--full` | | Walk every overridable characteristic |

If `<agent-name>` is missing, ask for it. Validate it as a slug
(`^[a-z][a-z0-9-]*$`) and offer a corrected version if it isn't.

---

## Step 1 — Preconditions

```bash
bash builders/bootstrap-agent/scripts/detect-profile.sh
```

| State | Action |
|---|---|
| `NONE` | Stop. "No baseline profile found — run `/bootstrap-profile` first." |
| `VALID` | Continue |
| `STALE` | Warn, offer to run `/bootstrap-profile migrate` first. Allow the user to proceed if they insist |
| `INVALID` / `UNREADABLE` | Stop. The agent would inherit a broken baseline. Point at `/bootstrap-profile` |

Then check the destination. If `<dest>/<agent-name>/` already exists, ask before
touching it: overwrite, pick a different name, or cancel.

---

## Step 2 — Interview

Show the user what they'll inherit before asking anything, so the questions have
context:

```bash
python3 builders/create-agent/scripts/resolve-config.py --baseline-only --summary
```

### Express mode (default)

**Ask four questions:**
1. **Description** — one line on what this agent does
2. **Pattern** — confirm the baseline default (`standalone`) or pick another.
   Show the enumerated set. Nudge toward standalone: multi-agent patterns cost
   roughly 10–15x the tokens
3. **Model** — confirm the baseline default, or override up if this agent's work
   genuinely needs it
4. **Anything else to override?** — offer the resolved baseline summary and let
   them name fields. Most agents override nothing here

Anything not raised is inherited, not written.

### Full mode

Walk every overridable characteristic, grouped as in
`builders/bootstrap-agent/README.md`. At each one, show the inherited value and
offer: keep (inherit, writes nothing) or override. **Keep must be the default
answer** — an override written for a value identical to the baseline is noise
that silently pins the field against future baseline edits.

---

## Step 3 — Confirm

Render two things:

**The `agent.yaml` to be written** — overrides only, which should be short.

**The resolved configuration** — with provenance per line, so the user sees what
the agent will actually run with:

```
model: "claude-opus-5"        # this agent
pattern: "standalone"         # baseline
verbosity: "concise"          # baseline
```

Ask for acceptance. Do not write before acceptance.

---

## Step 4 — Scaffold

Copy `templates/agent/` to `<dest>/<agent-name>/` and populate:

```
<agent-name>/
├── agent.yaml       # extends + identity + overrides only
├── CLAUDE.md        # {{AGENT_NAME}}, {{AGENT_DESCRIPTION}} substituted
├── README.md        # same substitutions
├── steering.md      # created empty, with a one-line header
└── output/          # created empty, with .gitkeep
```

Substitute `{{AGENT_NAME}}` and `{{AGENT_DESCRIPTION}}` throughout. Leave the
process section of `CLAUDE.md` as the empty numbered skeleton — that's the
user's to write, and guessing at it produces confident nonsense.

Set `extends` to the absolute-or-`~` path of the baseline actually detected in
Step 1, not a hardcoded default.

---

## Step 5 — Validate

```bash
python3 builders/create-agent/scripts/validate-agent.py <dest>/<agent-name>/agent.yaml
```

Checks the override file's own structure, plus that it resolves cleanly against
its baseline. On failure, fix and re-run — do not leave a broken agent in place.

Then show the resolved config one final time:

```bash
python3 builders/create-agent/scripts/resolve-config.py <dest>/<agent-name>/agent.yaml --explain
```

---

## Step 6 — Report

Tell the user:
- Where the agent was created
- Which fields it overrides, and that everything else tracks the baseline
- That editing `~/.agent-toolkit/baseline.yaml` will change this agent's
  defaults for any field it hasn't overridden
- That `CLAUDE.md` has an empty process section waiting for them

Do not offer to run the agent. Creation and execution are separate.

## Related
- `README.md` — what this builder does
- `agent-example.yaml` — annotated example with all overridable fields and options
- `schema/agent-override.schema.json` — machine-readable schema
- `scripts/resolve-config.py` — the precedence resolver
- `scripts/validate-agent.py` — override validation
- `../../docs/precedence-and-inheritance.md` — the resolution rules
