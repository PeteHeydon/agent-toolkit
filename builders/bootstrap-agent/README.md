# bootstrap-agent

## Intent
Every agent starts from a profile covering localisation and tone of voice, so new agents inherit sensible defaults rather than being configured from zero.

This module produces **one profile per user** — the personalised baseline that every agent in the toolkit inherits from.

## Usage

Run from within the `agent-toolkit/` directory:

```bash
cd agent-toolkit && claude

/bootstrap-profile              # detect state, then interview or review
/bootstrap-profile express      # ~5 questions, defaults for the rest
/bootstrap-profile full         # walk every characteristic
/bootstrap-profile review       # show and edit the existing profile
/bootstrap-profile migrate      # upgrade a stale profile to the current schema
```

The profile is always written to `$AGENT_TOOLKIT_HOME/baseline.yaml`
(default `~/.agent-toolkit/baseline.yaml`) — outside this repository, never into
it. A single canonical user-level location is what makes inheritance work.

**This produces a profile, not an agent.** The baseline is a config file — it
does not run. Agents are composed from it later via `/create-agent`, and land in
`~/.agent-toolkit/agents/`. See [`docs/repository-structure.md`](../../docs/repository-structure.md)
for the full separation of builders, profile, and agents.

## Files

| File | Purpose |
|---|---|
| `CLAUDE.md` | The process definition — detect, interview, confirm, validate, write |
| `bootstrap-agent-example.yaml` | Annotated example with every default and legal option |
| `schema/baseline-profile.schema.json` | Machine-readable schema |
| `scripts/detect-profile.sh` | Returns profile state: NONE / VALID / STALE / INVALID / UNREADABLE |
| `scripts/validate-profile.py` | Structural validation + no-secrets enforcement; semantic checks stubbed for the Validation Agent |

## Characteristics
While these can be extended, the following are the base characteristics that can be used repeatedly to build your agents — as well as update a baseline of inheritance for agents to be updated from.

Characteristics marked **[E]** are asked in Express mode. The rest are inferred from the environment or take the documented default.

### Identity & context
* **Locale**: Language, region, and date/number/currency formatting conventions *(inferred from system)*
* **Domain** **[E]**: Industry or subject area the agent will operate from
* **Audience** **[E]**: Who the agent's output is for (internal team, external client, technical vs non-technical)

### Voice & style
* **Tone of voice** **[E]**: Formal/casual, terse/expansive
* **Persona**: Whether the agent has a name/character, or stays neutral/utilitarian
* **Verbosity** **[E]**: Default output length/density (concise bullets vs full prose)
* **Formatting conventions**: House style for markdown headers, tables, code blocks, etc.

### Operating constraints
* **Model**: Default LLM model to utilise — baseline is a mid-tier model (e.g. Sonnet) to avoid cost blowouts from defaulting every agent to the highest-tier model; agents can override up where a task genuinely needs it
* **Pattern**: Default agent pattern from a small enumerated set (not free text) — baseline is `standalone`; other values to introduce as needed: `pipeline`, `router`, `parallel`, `orchestrator-workers` (aka hierarchical-supervisory), `evaluator-optimizer`, `collaborative` (aka peer-to-peer/swarm). Keep the default simple; expand the set only when a real use case needs it
* **Guardrails** **[E]**: Input filtering, tool-use limits, and output validation to apply — recurs as its own concern across every pattern, separate from the pattern itself. In Express mode this is asked as a single "risk posture" question
* **Evaluation/quality loop**: Whether the agent self-reviews or is checked by a second pass before returning output (off by default for a standalone agent; on for patterns like evaluator-optimizer)
* **Permissions/scope** **[E]**: What the agent is and isn't allowed to touch (files, tools, external calls) — also covered by the risk posture question
* **Safety/compliance profile**: Regulatory or org-specific guardrails to inherit
* **Cost/performance budget**: Token limits, preferred model tier, latency tolerance

### Knowledge & memory
* **Default context sources**: Which skills/docs/knowledge base the agent should pull from on init
* **Memory behaviour**: Whether it persists state across runs or starts fresh each time
* **Context management**: How the agent keeps its context window under control as a run grows — default truncation/pagination limits on tool output, and whether stale tool calls/results get cleared as token limits approach

### Interop
* **Output format contract**: Markdown by default, for human consumption; JSON or another machine-readable format only where a downstream agent/tool specifically needs it
* **Output location**: Default output directory (e.g. `./output`) that agent results are written to, rather than the project root
* **Escalation path**: Who/what it hands off to when it hits its limits (another agent, a human)

### Steering
* **Feedback mode**: Supports both live chat-based feedback and bulk written feedback — a steering/notes file the agent reads and applies on request, for guidance considered offline and brought back later rather than given turn-by-turn in chat

### Credentials
* **Credentials**: Environment variable *names* only, never values. Validation rejects any literal secret. See [`docs/environment-variables.md`](../../docs/environment-variables.md)

## Inheritance

Agents inherit from this profile **by reference at runtime**, not by copying it at
creation time. Editing the baseline changes the default for every agent that hasn't
explicitly overridden that field — no regeneration needed.

Precedence, lowest to highest: baseline profile → agent override → CLI flag →
in-session instruction. Higher wins for the field it sets and only that field.
Full detail in [`docs/precedence-and-inheritance.md`](../../docs/precedence-and-inheritance.md).

## Provenance
The **Pattern**, **Guardrails**, **Evaluation/quality loop**, and **Context management** characteristics were added following a review of agentic patterns across Anthropic (both the research post and the *Architecture Patterns and Implementation Frameworks* whitepaper), OpenAI, Google, and Andrew Ng/DeepLearning.AI — see [`docs/research/agentic-patterns-initial-summary.md`](../../docs/research/agentic-patterns-initial-summary.md).

Consistent finding across all of them: start with the simplest pattern (a standalone agent, no extra loop), and only add pattern complexity, guardrails, or a quality loop when a real use case demands it. The defaults here encode that.
