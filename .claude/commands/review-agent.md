---
description: Review an existing agent and propose what should change
argument-hint: "<agent-name>"
allowed-tools: Read, Bash, Glob
---

# /review-agent

Review one agent and propose changes. Writes nothing.

Agent: **$ARGUMENTS**

Read and follow the process defined in:
@../../builders/refinement-agent/CLAUDE.md

## Notes for the invoking agent

- **This command does not change anything.** It proposes `/edit-agent`
  invocations and stops. Separating the diagnosis from the change is what
  gives the user somewhere to disagree.
- **There is no run history.** Do not imply you can see how the agent
  performed. What you can see is what the user kept telling it, what it pins,
  and whether it still validates.
- Be willing to conclude that nothing needs changing. A review that
  manufactures findings to look thorough costs more than it saves.
