# bootstrap-agent

## Intent
Every agent starts from a profile covering localisation and tone of voice, so new agents inherit sensible defaults rather than being configured from zero.

## Characteristics
While these can be extended, the following are the base characteristics that can be used repeatedly to build your agents — as well as update a baseline of inheritance for agents to be updated from.

### Identity & context
* **Locale**: Language, region, and date/number/currency formatting conventions
* **Domain**: Industry or subject area the agent will operate from
* **Audience**: Who the agent's output is for (internal team, external client, technical vs non-technical)

### Voice & style
* **Tone of voice**: Formal/casual, terse/expansive
* **Persona**: Whether the agent has a name/character, or stays neutral/utilitarian
* **Verbosity**: Default output length/density (concise bullets vs full prose)
* **Formatting conventions**: House style for markdown headers, tables, code blocks, etc.

### Operating constraints
* **Model**: Default LLM model to utilise — baseline is a mid-tier model (e.g. Sonnet) to avoid cost blowouts from defaulting every agent to the highest-tier model; agents can override up where a task genuinely needs it
* **Pattern**: Default agent pattern from a small enumerated set (not free text) — baseline is `standalone`; other values to introduce as needed: `pipeline`, `router`, `parallel`, `orchestrator-workers` (aka hierarchical-supervisory), `evaluator-optimizer`, `collaborative` (aka peer-to-peer/swarm). Keep the default simple; expand the set only when a real use case needs it
* **Guardrails**: Input filtering, tool-use limits, and output validation to apply — recurs as its own concern across every pattern, separate from the pattern itself
* **Evaluation/quality loop**: Whether the agent self-reviews or is checked by a second pass before returning output (off by default for a standalone agent; on for patterns like evaluator-optimizer)
* **Permissions/scope**: What the agent is and isn't allowed to touch (files, tools, external calls)
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

## Usage
New agents inherit this profile as a baseline at creation time. Updating a characteristic here updates the default inherited by any agent that hasn't explicitly overridden it — giving a single point of control for baseline behaviour across the toolkit.

See `bootstrap-agent.yaml.example` as an exemplar. The **Pattern**, **Guardrails**, and **Evaluation/quality loop** characteristics were added following a first-pass review of agentic patterns across Anthropic, OpenAI, Google, and Andrew Ng/DeepLearning.AI — see `agentic-patterns-initial-summary.md`. Consistent finding across all of them: start with the simplest pattern (a standalone agent, no extra loop), and only add pattern complexity, guardrails, or a quality loop when a real use case demands it.