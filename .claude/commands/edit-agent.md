---
description: Change an existing agent's configuration without recreating it
argument-hint: "<agent-name> [--set key.path=value] [--compose kind/name] [--web|--no-web]"
allowed-tools: Read, Bash, Glob
---

# /edit-agent

Change one thing about an agent that already exists.

Target and change: **$ARGUMENTS**

## Hard rules

1. **Always pass `--merge`.** Without it the scaffolder rewrites `agent.yaml`
   from the flags it was given, silently dropping every override you did not
   restate. An agent with a model override and a composed module, "edited" for
   verbosity alone, comes back with neither.
2. **Show the resolved diff before writing.** The user is deciding about
   values, not about a file.
3. **Never write outside the toolkit-owned set.** The Process section of
   `CLAUDE.md`, `steering.md` and `output/` are the user's. A change that
   belongs in one of them is advice, not an edit.
4. **Write only what actually differs from the baseline.** An override equal
   to the inherited value pins that field against every future baseline edit,
   which is the thing D3 exists to prevent.

---

## Step 1 — Read the current state

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  "$AGENT_TOOLKIT_HOME/agents/<name>/agent.yaml" --explain
```

Note what is already overridden. Those are the fields a baseline edit will
never reach, and they are the ones most likely to be the real cause of
whatever prompted this edit.

## Step 2 — Preview

Same flags as the real run, plus `--dry-run`:

```bash
python3 builders/create-agent/scripts/scaffold-agent.py \
  --name <name> --dest "$AGENT_TOOLKIT_HOME/agents" \
  --description "<existing description>" --extends "<baseline path>" \
  --merge --dry-run \
  [--set <key.path>=<value> ...] [--compose <kind/name> ...] [--web|--no-web]
```

Show the user the change as resolved values, one line each:

```
verbosity:  concise  ->  expansive     (this agent)
model:      unchanged, claude-sonnet-5 (baseline)
```

A field that ends up equal to the baseline should be reported as "no override
written" rather than as a change.

## Step 3 — Confirm, then apply

Drop `--dry-run`. The same invocation writes `agent.yaml`, re-renders the
generated region and `.claude/settings.json`, and re-validates — so an edit
never leaves an agent stale.

Report what `data.written` and `data.preserved` actually say. `preserved`
naming the user's `CLAUDE.md` and `steering.md` is the evidence that rule 3
held.

## Notes for the invoking agent

- `--compose` **replaces** the composed list rather than adding to it, because
  arrays replace everywhere in this toolkit (D4). To add one module, pass all
  of them. Say so rather than letting the user discover a module vanished.
- If the change is really "this agent needs different steps", say so and stop.
  Editing the Process section is the user's to do, and this command must not.
- If validation fails after the edit, the agent is left changed and invalid.
  Report the errors and offer to revert by re-running with the previous values
  — do not leave that state unremarked.
