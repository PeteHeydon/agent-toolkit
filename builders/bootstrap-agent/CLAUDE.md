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
bash builders/bootstrap-agent/scripts/detect-profile.sh
```

It returns one of five states. Branch accordingly:

| State | Meaning | Action |
|---|---|---|
| `NONE` | No profile found | Go to **Step 2 — Interview** |
| `VALID` | Profile found, current schema, passes validation | Go to **Step 5 — Review** |
| `STALE` | Profile found, older `schema_version` | Go to **Step 4 — Migrate** |
| `INVALID` | Profile found, current schema, fails validation | Go to **Step 4b — Repair** |
| `UNREADABLE` | File exists but is not parseable YAML | Show the parse error. Offer: (a) repair by hand, (b) back up and start fresh. Never overwrite without an explicit yes. |

If the user passed a mode argument (`express`, `full`, `review`, `migrate`),
honour it and skip the detection branch where it conflicts — except `NONE`,
where `review` and `migrate` are meaningless and you fall through to the interview.

---

## Step 2 — Interview

Offer two modes. Ask this first, before any characteristic questions:

> **Express** — I'll ask ~5 questions, infer or default the rest, then show you
> everything for review before writing.
> **Full** — I'll walk through every characteristic one at a time.

### Express mode (default)

**Infer silently, do not ask:**
- `locale` — from system locale / timezone
- `model` — the sensible mid-tier default (see example file); never default to a
  top-tier model
- `pattern` — always `standalone`
- `output_location`, `context_management`, `guardrails`, `evaluation_loop` —
  take the example file defaults

**Ask these five, and only these:**
1. **Domain** — what industry or subject area will your agents mostly work in?
2. **Audience** — who is the output usually for? (internal team / external client /
   technical / non-technical)
3. **Tone of voice** — how should agents write by default?
4. **Verbosity** — concise, standard, or expansive?
5. **Risk posture** — how much should agents be allowed to do unsupervised?
   (maps to `permissions_scope` + `guardrails.output_validation`)

Then go to **Step 3 — Confirm**.

### Full mode

Walk every characteristic in `builders/bootstrap-agent/README.md`, in the order
listed there, grouped by section. One question at a time. Offer the default as
the accept-by-default answer at each step so the user can move quickly. Then go
to **Step 3 — Confirm**.

### Interview conduct
- Show the default alongside each question so "just use the default" is one word.
- Do not ask about anything you can infer from the environment.
- Do not ask for secrets. If a characteristic needs credentials, ask only for the
  **env var name**.

---

## Step 3 — Confirm

Render the complete resolved profile back to the user as YAML, with a marker on
each line showing where the value came from:

```
domain: "financial services"     # you
locale: "en-AU"                  # inferred from system
model: "claude-sonnet-4-6"       # default
```

Ask: accept, or which fields to change. Loop until accepted. **Do not write
before acceptance.**

---

## Step 4 — Migrate (state: STALE)

1. Show the user their current `schema_version` and the current one.
2. List what changed between versions — new fields with their defaults, renamed
   fields, removed fields.
3. Back up the existing file to `baseline.yaml.bak-<schema_version>`.
4. Apply the migration, carrying every existing value forward unchanged. Only
   new fields get defaults.
5. Go to **Step 3 — Confirm** with the migrated profile.

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

Any consumer of this profile resolves values in this order, lowest to highest:

```
1. Baseline profile     ~/.agent-toolkit/baseline.yaml     (this file)
2. Agent profile        <agent-dir>/agent.yaml             (per-agent overrides)
3. CLI flag             --model=... --pattern=...
4. In-session instruction  "for this run, use expansive verbosity"
```

Higher always wins for the field it sets, and **only** for that field. Nothing
inherits wholesale from a higher layer. Agents reference the baseline at runtime
rather than copying it — so a baseline edit propagates without regenerating
anything.

## Related
- `README.md` — the characteristics themselves
- `bootstrap-agent-example.yaml` — annotated example with all defaults and options
- `schema/baseline-profile.schema.json` — machine-readable schema
- `../../docs/environment-variables.md` — how to set up secrets correctly
