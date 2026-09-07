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
* **Model**: Default LLM model to utilise
* **Permissions/scope**: What the agent is and isn't allowed to touch (files, tools, external calls)
* **Safety/compliance profile**: Regulatory or org-specific guardrails to inherit
* **Cost/performance budget**: Token limits, preferred model tier, latency tolerance

### Knowledge & memory
* **Default context sources**: Which skills/docs/knowledge base the agent should pull from on init
* **Memory behaviour**: Whether it persists state across runs or starts fresh each time

### Interop
* **Output format contract**: Expected shape of results (JSON schema, plain text, file type) so downstream agents/tools can consume it reliably
* **Escalation path**: Who/what it hands off to when it hits its limits (another agent, a human)

## Usage
New agents inherit this profile as a baseline at creation time. Updating a characteristic here updates the default inherited by any agent that hasn't explicitly overridden it — giving a single point of control for baseline behaviour across the toolkit.

See `bootstrap-agent.yaml.example` as an exemplar.