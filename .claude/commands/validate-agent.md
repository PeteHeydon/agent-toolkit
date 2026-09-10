---
description: Check an agent for correctness, mechanically and by judgment
argument-hint: "<agent-name>"
allowed-tools: Read, Bash, Glob
---

# /validate-agent

Report whether an agent is correct. Changes nothing.

Agent: **$ARGUMENTS**

Read and follow the process defined in:
@../../builders/validation-agent/CLAUDE.md

## Notes for the invoking agent

- **Mechanical findings and judgment findings are different things** and must
  be reported separately. One is "this is wrong"; the other is "this looks
  inconsistent, and I might be wrong about it".
- **Never edit.** A validator that fixes things cannot be trusted to report
  what was broken. Propose, and let the user run `/edit-agent`.
- This asks whether the agent is *right*. Whether it should become something
  else is `/review-agent`.
