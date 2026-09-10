# refinement-agent

## Intent
Say how an existing agent is actually doing, and propose what should change.

The specific job — and the reason this is a builder rather than a script — is
**promotion**. `steering.md` accumulates the corrections you keep giving an
agent. A correction you have written three times should stop being a
correction and become part of the agent: a config value, a composed module, or
a process step. Deciding which of those it is takes judgment, not computation.

## Usage

```bash
cd agent-toolkit && claude

/review-agent my-agent
```

Read-only. It proposes `/edit-agent` invocations; it never writes.

## What it can and cannot see

It reads what the toolkit already records:

| Source | What it tells you |
|---|---|
| `steering.md` | What you keep having to tell this agent |
| `agent-status.py` | Overrides, validity, render freshness, unfinished intent |
| `validate-agent.py` | Hygiene warnings, composition against granted capabilities |
| `output/` | Whether it has produced anything, and when |

**There is no run history**, deliberately — see
`docs/proposals/local-ui-readiness.md`, which reserves the namespace and builds
nothing. So this cannot tell you an agent gave a wrong answer last Tuesday. It
can tell you that you have corrected the same thing four times and that the
correction belongs in the config.

That bound is worth stating plainly rather than implying a depth of evaluation
the toolkit cannot support.

## Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | The process — gather, judge, propose, stop |

No scripts. Everything computable is already computed by `agent-status.py` and
`validate-agent.py`; a second evidence-gatherer would drift from the first.
