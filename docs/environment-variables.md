# Environment Variables & Secrets

## The rule

No secret — API key, token, password, connection string — is ever written into
a profile, an agent override, or any other file this toolkit reads or writes.
`credentials` fields in `baseline.yaml` and `agent.yaml` hold **environment
variable references only**, in the form `env:VAR_NAME`:

```yaml
credentials:
  anthropic_api_key: "env:ANTHROPIC_API_KEY"
```

Both validators (`validate-profile.py`, `validate-agent.py`) reject anything
in a `credentials` block that isn't a bare `env:VAR_NAME` reference, and scan
the rest of the file for text that looks like a literal key or token, as a
second line of defence.

If the bootstrap or create-agent interview asks for a credential, it asks for
the **environment variable's name**, never its value. If you paste a literal
secret when asked, the agent should decline it and point back here.

## Setting values

Values live in your shell environment or a local `.env` file — never in the
repo, never in `~/.agent-toolkit/`.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

or, using `.env.example` as a starting point:

```bash
cp .env.example .env
# edit .env with real values
```

`.env` is gitignored. Load it however your shell setup already does (a
`direnv` hook, `source .env`, your process manager) — the toolkit itself
doesn't load it for you; it only reads the resolved environment at runtime.

## Required

| Variable | Used for |
|---|---|
| `ANTHROPIC_API_KEY` | Running any agent (baseline default: Claude, mid-tier model) |

Add a row here whenever a builder or agent introduces a new credential —
`credentials.<name>` in a profile is the signal to update this table.

## Why this matters

A baseline or agent file gets copied around, diffed, and potentially committed
to a project repo (agents provisioned with `--path` are meant to be shared).
A literal secret in either file leaks the moment that happens. An `env:`
reference is safe to commit, diff, and share — the value stays wherever your
secrets already live.
