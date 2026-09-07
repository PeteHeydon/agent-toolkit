

Agentic patterns initial summary · MD
# Agentic Patterns — Initial Summary
 
*Purpose: a first-pass survey across vendors and community sources, to identify a shortlist worth a proper deep-dive later. Not exhaustive — a map of the territory, not the territory itself.*
 
## 1. Foundational patterns (Andrew Ng / DeepLearning.AI)
The most widely-referenced starting vocabulary — four capability-level patterns, not tied to any one vendor:
- **Reflection** — agent critiques its own output against criteria and revises (self-review, tool-backed check like unit tests, or a separate critic agent)
- **Tool Use** — agent calls external functions/APIs to act, not just generate text
- **Planning** — agent breaks a task into sub-steps and adapts the plan as it goes
- **Multi-Agent Collaboration** — specialised agents split a complex task between them
## 2. Anthropic — workflow vs. agent distinction, five composable patterns
Anthropic's core distinction: **workflows** (predefined code paths orchestrating LLMs/tools) vs. **agents** (the LLM dynamically directs its own process). Their guidance: start with workflows — they're more predictable and cheaper — and only graduate to autonomous agents when the task genuinely needs open-ended decision-making.
 
Five composable workflow patterns, plus autonomous agents as a sixth:
- **Prompt Chaining** — sequential LLM calls, output of one feeds the next
- **Routing** — classify input, direct to a specialised path
- **Parallelization** — split into parallel LLM calls, then aggregate
- **Orchestrator–Workers** — one agent delegates to worker agents and synthesises results
- **Evaluator–Optimizer** — one agent generates, another evaluates and sends back for revision (a structured form of Reflection)
- **Autonomous Agents** — full dynamic control, used sparingly
## 2a. Anthropic — "Architecture Patterns and Implementation Frameworks" whitepaper (this is the source you meant)
This is a distinct, more detailed Anthropic document (an enterprise-facing whitepaper, not the original research post) that expands the picture considerably:
 
**Single-agent systems** — a perceive→decide→act loop, extended with **Agent Skills**: modular capability packages (domain expertise, standardised workflows, tool integrations) that a single agent can call on to punch above a generalist's weight, without needing to graduate to multi-agent. Skills themselves are composable — one skill can invoke another (e.g. a compliance skill calling a document-analysis skill).
 
**Multi-agent systems** — split into two coordination philosophies:
- **Centralized/hierarchical (supervisory)** — a supervisor delegates to specialist sub-agents, treating them as callable tools; sub-agents can have their own sub-agents, abstracted from the supervisor. Also called orchestrator or router patterns depending on emphasis. This is the same idea as OpenAI's Manager pattern and Google's Coordinator/Dispatcher — now confirmed as one concept under (at least) four names.
- **Decentralized/collaborative** — agents communicate peer-to-peer, negotiate roles, and share a "blackboard" or event stream rather than reporting to a supervisor. Also called swarm or federated. Early benchmarking cited in the whitepaper found swarm architectures slightly outperforming supervisor architectures on some tasks, though at the cost of predictability.
**Agentic workflows** (the static/predefined counterpart to dynamic multi-agent systems) — sequential and parallel, matching what's already listed above, but with sharper guidance on **when to avoid** each: sequential when stages need to run out of order or agents must collaborate rather than hand off; parallel when agents need to build on each other's work or lack a clear conflict-resolution strategy for contradictory results.
 
**Decision framework** — four questions to pick a pattern by, rather than by technical preference:
1. Control needed (audit/regulatory → single agent or sequential; low control tolerance → collaborative is viable)
2. Problem domain complexity (single domain → single agent; multi-domain but predictable → workflows; open-ended → multi-agent)
3. Resource constraints (multi-agent systems use roughly **10–15x more tokens** than single-agent — a concrete cost figure worth keeping)
4. Depth of domain expertise needed (single domain → single agent + Skills; multiple coordinating domains → multi-agent + Skills per agent)
**Hybrid strategies** — production systems rarely stay in one pattern: hierarchical supervisors delegating to specialists who then run parallel sub-workflows; sequential workflows with dynamic AI-driven routing at each stage; and notably **single agents with multi-agent escalation** — a simple agent handles routine cases and triggers a heavier multi-agent system only for edge cases, to control cost.
 
**Context management** (called out as a first-class concern, not an implementation detail) — context editing to clear stale tool calls/results as token limits approach, memory tools for state that persists outside the context window, and capping tool responses (pagination, filtering, truncation with sensible defaults) to prevent context exhaustion.
 
**Emerging/experimental patterns** — dynamic agent generation (agents assembled at runtime from a library of prompts/tools/configs, then dissolved after the task — no production systems do this yet, but it's directly relevant to what this toolkit is trying to build) and network/peer-to-peer architectures (the "many-to-many" version of collaborative systems above).
 
## 3. OpenAI — practical guide to building agents
Emphasises starting with a **single agent**, evolving to multi-agent only when needed, and treats **guardrails as a first-class concern at every stage** (input filtering, tool-use limits, output checks, human-in-the-loop). Two multi-agent orchestration shapes stand out:
- **Manager (centralized)** pattern — a manager agent owns the conversation and delegates via tool calls to specialist agents
- **Decentralized (handoff)** pattern — agents hand off control to each other directly, better suited to dynamic routing (e.g. support triage)
Composable primitives: models, tools, state/memory, orchestration, guardrails.
 
## 4. Google — multi-agent design patterns (Agent Development Kit)
Google frames multi-agent systems as the AI equivalent of microservices — decentralisation and specialisation over one bottlenecked agent. Built from three foundational execution primitives (sequential, loop, parallel), combined into patterns including:
- **Sequential pipeline** — linear hand-off, easy to debug
- **Coordinator/Dispatcher** — one agent triages and routes to specialists
- **Parallel fan-out/gather** — concurrent agents, results collected and merged
- (Google's fuller catalogue runs to ~8–12 patterns spanning single-agent through swarm architectures — worth the deep-dive)
## 5. Community shorthand (seen across multiple blogs/practitioners)
A simpler, practical naming layer that maps closely onto the above:
- **Pipeline** — A → B → C → D
- **Gate** — pipeline with a checkpoint agent deciding continue vs. escalate to human
- **Fan-Out/Fan-In** — parallel branches converging on a collector
- **Router** — classify and dispatch to different downstream chains
- **Retry Loop** — producer/reviewer pair iterating until quality passes (a Reflection variant)
## Cross-cutting insights (consistent across all sources)
- **Start simple.** Every vendor's guidance converges: begin with a single agent or workflow; only add multi-agent complexity when the task demands it — reinforced with a concrete number from Anthropic's whitepaper: multi-agent systems run **10–15x the token cost** of a single agent.
- **Guardrails belong at every stage**, not bolted on at the end — input filtering, tool-use constraints, output validation, human-in-the-loop checkpoints.
- **Evaluation/quality loops** (Reflection, Evaluator-Optimizer, Retry Loop) are a recurring second-order pattern layered on top of a base pattern, not a separate category.
- **State/memory placement** — where conversation/task state lives — is called out repeatedly as a design decision, not an implementation detail. Anthropic's whitepaper is explicit about *how*: context editing (clear stale tool calls near the token limit), external memory tools, and capped/paginated tool responses.
- **Observability and debuggability** are treated as architectural requirements, not nice-to-haves (linear/sequential patterns are favoured partly because they're easiest to trace).
- **Escalate, don't default to heavy.** The single-agent-with-multi-agent-escalation hybrid (Anthropic whitepaper) is a distinct, named pattern for exactly the cost discipline this toolkit's bootstrap defaults are trying to enforce.
## Shortlist for deep-dive
- Orchestrator–Workers (Anthropic) / Coordinator–Dispatcher (Google) / Manager pattern (OpenAI) / Hierarchical-Supervisory (Anthropic whitepaper) — now confirmed as one concept under four names; worth one canonical treatment
- Evaluator–Optimizer / Reflection / Retry Loop / Gate — same underlying quality-loop concept, worth one canonical treatment
- Decentralized handoff (OpenAI) / Collaborative-peer-to-peer / Network-swarm (Anthropic whitepaper) — relevant to the toolkit's own sub-agent-to-sub-agent handoffs
- Google's full 8–12 pattern catalogue — not yet reviewed in depth here
- Dynamic agent generation (Anthropic whitepaper, experimental) — directly relevant to this toolkit's own composable-agent premise; worth tracking even though no production system does it yet
- The whitepaper's four-question decision framework (control / domain complexity / resources / expertise depth) — worth adapting into a lightweight checklist for the toolkit's own Design Agent
## Implications for bootstrap-agent
See the companion README update. Key takeaways, now reinforced by a second source:
- **Pattern** shouldn't stay a single free-text field; it should be a small enumerated set, and the whitepaper's own terms (single-agent, sequential, parallel, evaluator-optimizer, hierarchical-supervisory, collaborative) map directly onto what's already there
- **Guardrails** and an **evaluation/quality-loop** toggle are recurring separate concerns across every source, not part of the pattern itself — already added
- **Context management** deserves its own characteristic under Knowledge & memory — context editing/truncation defaults and a memory-tool reference — since the whitepaper treats it as a named, first-class design decision rather than an implementation detail
- **Agent Skills** as composable capability packages (skills invoking skills) is close to what's already sketched in the toolkit's own "Agent Skills Agent" — this whitepaper is independent confirmation the idea holds up in production, not just in your notes
 
