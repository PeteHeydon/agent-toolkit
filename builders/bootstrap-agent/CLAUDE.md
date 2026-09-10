# bootstrap-agent — Process Definition

You are running the **bootstrap-agent**. Your job is to produce a validated
**baseline profile**: the single canonical set of characteristics that every
agent built with this toolkit inherits from.

## Hard rules

1. **You produce a profile, not an agent.** The baseline is a config file, not
   something that runs. Do not scaffold, generate, or run an agent as part of
   this process — that is `/create-agent`. The output here is one YAML file.
2. **The baseline is user-level and singular.** It is always written to
   `$AGENT_TOOLKIT_HOME/baseline.yaml` (default: `~/.agent-toolkit/baseline.yaml`),
   never to the current working directory, regardless of where the command was
   invoked from. One baseline per user is the whole point — writing per-project
   copies destroys the inheritance model.
3. **Never write a secret into the profile.** API keys, tokens, passwords, and
   connection strings are referenced by environment variable name only
   (`env:VAR_NAME`), never by value. If the user offers a secret value, decline
   it and point them to `docs/environment-variables.md`.
4. **Ask before overwriting.** An existing valid profile is never silently
   replaced.

---

## Step 1 — Detect

Run the detection script:

```bash
python3 builders/bootstrap-agent/scripts/detect-profile.py
```

It returns one of six states. Branch accordingly:

| State | Meaning | Action |
|---|---|---|
| `NONE` | No profile found | Go to **Step 2 — Interview** |
| `VALID` | Profile found, current schema, passes validation | Go to **Step 5 — Review** |
| `STALE` | Profile found, older `schema_version` | Go to **Step 4 — Migrate** |
| `INVALID` | Profile found, current schema, fails validation | Go to **Step 4b — Repair** |
| `UNREADABLE` | File exists but is not parseable YAML | Show the parse error. Offer: (a) repair by hand, (b) back up and start fresh. Never overwrite without an explicit yes. |
| `NO_PYTHON` | The environment can't run the check. **The profile has not been read.** | Stop. Show the script's stderr, which names the specific problem and the fix. Do not touch the profile, and never treat this as `UNREADABLE` — nothing is known to be wrong with it. |

If the command itself fails to start — `python3: command not found`, or a
Windows install prompt instead of output — that is the same class of problem
and the same answer: the environment cannot run the check, and the profile has
not been read. Try `python` or `py -3`, or run
`bash builders/bootstrap-agent/scripts/detect-profile.sh`, which finds a
working interpreter first and reports `NO_PYTHON` properly when there is none.
See `docs/getting-started.md`, "On Windows".

If the user passed a mode argument (`express`, `full`, `review`, `migrate`),
honour it and skip the detection branch where it conflicts — except `NONE`,
where `review` and `migrate` are meaningless and you fall through to the interview.

---

## Step 2 — Interview

**The questions are not written here.** They live in the schema and are read
out of it, so the interview, the characteristics list in `README.md`, and any
future form all ask the same things:

```bash
python3 scripts/describe-schema.py --json
```

That returns the descriptor in the standard envelope. What to read from
`data`:

| Field | What it gives you |
|---|---|
| `express_questions` | the ids to ask in Express mode, in order |
| `characteristics` | every askable unit: `label`, `question`, `help`, `legal`, `default`, `group` |
| `composites` | one question that sets several fields — each answer's `sets` map is the exact values to write |
| `fields[].source` | how each leaf gets its value: `question`, `composite`, `inferred`, or `default` |

Offer two modes. Ask this first, before any characteristic questions:

> **Express** — I'll ask ~5 questions, infer or default the rest, then show you
> everything for review before writing.
> **Full** — I'll walk through every characteristic one at a time.

### Express mode (default)

Ask exactly the characteristics named in `express_questions`, in that order,
and nothing else. A composite id there (`risk_posture`) is one question whose
answer writes every field in its `sets` map — do not ask about those fields
individually, and do not write values the map doesn't name.

Everything else is filled without asking, and the descriptor says which of two
ways: a field whose `source` is `inferred` is read from the environment
(`infer` names the source — `system_locale` means the system locale and
timezone), and a field whose `source` is `default` or which belongs to a
characteristic not in `express_questions` takes its schema `default`.

Those two are not the same thing and shouldn't be reported as if they were —
Step 3 marks them differently.

Then go to **Step 3 — Confirm**.

### Full mode

Walk every characteristic in `characteristics`, in `groups` order. One question
at a time, using its `question` and `help`. For a characteristic whose `kind`
is `section`, ask about each field in its `fields` list. Offer `default` as the
accept-by-default answer so the user can move quickly. Skip anything whose
`source` is `inferred`. Then go to **Step 3 — Confirm**.

### Interview conduct
- Show the default alongside each question so "just use the default" is one word.
- Show the legal set whenever `legal` is present. Never invent a value outside it.
- Do not ask about anything the descriptor marks `inferred`.
- Do not ask for secrets. If a characteristic needs credentials, ask only for the
  **env var name**.

---

## Step 3 — Confirm

Render the complete resolved profile back to the user as YAML, with a marker on
each line showing where the value came from. The marker is the descriptor's
`source` for that field, so there are four and only four:

```
domain: "financial services"     # you
filesystem: "workspace_only"     # you, via risk posture
locale: "en-AU"                  # inferred from system
model: "claude-sonnet-5"         # default
```

A value the user chose and a value nobody was asked about must never carry the
same marker — the whole point of the review step is that an unasked default is
visible as one.

Ask: accept, or which fields to change. Loop until accepted. **Do not write
before acceptance.**

---

## Step 4 — Migrate (state: STALE)

**Do not rewrite the profile yourself.** Migration is deterministic and belongs
to a script (D19); a model editing someone's config by hand is how a value
nobody mentioned goes missing.

Preview it first — this writes nothing:

```bash
python3 builders/bootstrap-agent/scripts/migrate-config.py --dry-run --json
```

From `data`, show the user:

| Field | What to show |
|---|---|
| `from` / `to` | the version they're on and the version they're going to |
| `steps[].changes` | what the bump actually did, field by field |
| `notes` | **read these out in full** — see below |
| `profile` | the migrated profile, for **Step 3 — Confirm** |

`notes` is not a summary. It carries the things a migration did that the user
did not ask for and would not otherwise see. Migrating from version 1 grants
`web.search` that the profile previously withheld, because version 2 splits
`external_calls` into search and fetch and grants search at every posture
(D12). That is an expansion of what their agents may do, applied by a command
they ran for a different reason. Say it plainly and tell them how to undo it.

Any `warnings` mean something could not be translated — a v1 `tools` entry
with no v2 equivalent, for instance. Those need a decision from the user, not
a default.

On acceptance at Step 3, run it for real:

```bash
python3 builders/bootstrap-agent/scripts/migrate-config.py --json
```

It backs the original up to `baseline.yaml.bak-<old-version>` before writing,
and refuses to run if that backup already exists rather than overwriting the
only copy of what they had. Then validate the result (Step 6) — a migration
that produces an invalid profile must not be left in place.

## Step 4b — Repair (state: INVALID)

1. Show the specific validation errors from the validation script — field, what
   was found, what was expected.
2. Fix them one at a time with the user. For an illegal enum value, show the
   legal set.
3. Go to **Step 3 — Confirm**.

---

## Step 5 — Review (state: VALID)

Show the existing profile and ask what the user wants:
- **Nothing** — confirm it's valid and stop.
- **Change specific fields** — edit those, then Step 3.
- **Redo from scratch** — back up the existing file, then Step 2.

---

## Step 6 — Validate and write

1. Write the profile to `$AGENT_TOOLKIT_HOME/baseline.yaml`
   (create the directory if needed).
2. Run validation:
   ```bash
   python3 builders/bootstrap-agent/scripts/validate-profile.py "$AGENT_TOOLKIT_HOME/baseline.yaml"
   ```
3. If validation fails, **do not leave a broken file in place** — report the
   errors and go to Step 4b.
4. On success, tell the user the path, and remind them: agents inherit this by
   reference at runtime, so editing this file changes the default for every agent
   that hasn't overridden the field.

---

## Precedence

This profile is the lowest layer: baseline -> agent override -> CLI flag ->
in-session instruction. Higher wins for the field it sets and only that field,
and agents read this file at runtime rather than copying it, so an edit here
reaches every agent that hasn't pinned the field.

The merge rules in full, including how nested maps and arrays behave:
[`../../docs/precedence-and-inheritance.md`](../../docs/precedence-and-inheritance.md).
Tell the user this when you write the profile; don't restate the rules here.

## Related
- `README.md` — the characteristics themselves
- `bootstrap-agent-example.yaml` — annotated example with all defaults and options
- `schema/baseline-profile.schema.json` — machine-readable schema
- `../../docs/environment-variables.md` — how to set up secrets correctly
