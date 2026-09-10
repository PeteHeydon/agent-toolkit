# validation-agent

## Intent
Say whether an agent is *correct* — mechanically, and in the ways a rule
cannot express.

Three layers already run without a model:

| Layer | Asks | Where |
|---|---|---|
| Structural | Is this field legal? | `validate-agent.py` |
| Resolution | Does the extends chain reach a real baseline? | `resolve-config.py` |
| Semantic | Do these fields make sense *together*? | `scripts/semantic_checks.py` |

This builder runs those first and then does the part they cannot: reading the
agent as a whole and asking whether it hangs together. Tone against audience.
Whether the process the user wrote matches the description they gave it.
Whether the capabilities granted match what the process actually asks the
agent to do.

## Not the same as `/review-agent`

They are easy to confuse and the line is worth holding:

- **`/validate-agent` asks "is this right?"** — about the agent as configured,
  now.
- **`/review-agent` asks "should this become something else?"** — about the
  agent as *used*, from the corrections accumulated in `steering.md`.

An agent can be perfectly valid and still be the wrong agent.

## Usage

```bash
cd agent-toolkit && claude

/validate-agent my-agent
```

Reports only. It never edits an agent — a validator that fixes things is a
validator you cannot trust to tell you what was wrong.

## Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | The process — run the mechanical checks, then judge, then report |

No scripts of its own. The mechanical checks belong to the validators that
already run in `/create-agent` and `/refresh-agent`; duplicating them here
would give two answers to the same question.
