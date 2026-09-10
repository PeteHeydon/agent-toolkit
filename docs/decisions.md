# Decisions

The canonical design record. Every architectural call the toolkit rests on is
stated here once, in full, with its rationale.

`HANDOFF.md` carries the few a newcomer needs in the first ten minutes and
points here for the rest. `TODO.md` sequences the work that follows.

## Development environment

Development happens on **both Windows and Linux**. Neither is the primary and
neither is the afterthought: a change that works on one and silently
misbehaves on the other is a defect, not a portability gap. This is the
context for D15, and the reason `detect-profile` reporting `UNREADABLE` on
Windows was a blocking bug rather than an inconvenience.

---

## Settled

Don't relitigate without a reason. Where a decision is not yet fully
implemented, the backlog section that implements it is named.

### The model

| # | Decision | Why |
|---|---|---|
| D1 | The baseline profile is user-level and singular — `~/.agent-toolkit/baseline.yaml` | Per-project copies destroy the inheritance model |
| D2 | Inheritance is by reference at runtime, never a snapshot at creation | A baseline edit reaches every agent that hasn't pinned the field |
| D3 | `agent.yaml` carries overrides only | Restating a baseline value silently pins it against future edits |
| D4 | Arrays replace wholesale, they never merge | Silently appending permission arrays grants access nobody approved |
| D5 | `extends` is explicit, not convention | Self-describing agents; portable to other runtimes; multiple baselines |
| D6 | Commands run from inside `agent-toolkit/` | Self-contained, no install step, no copies drifting from the repo |
| D7 | Defaults are conservative on cost and autonomy — mid-tier model, `standalone` pattern, no evaluation loop | Multi-agent patterns cost 10–15x the tokens; every vendor's guidance converges on starting simple |
| D8 | No secrets in any config file — `env:VAR_NAME` references only | Config files get copied, diffed and committed |
| D9 | `builders/` is not named `agents/` | `agents/` means "agents you built" everywhere else |

D7 is about cost and autonomy, not capability. Withholding read-only web
access was never a considered decision — see D12.

### The runtime

**D10 — An agent is a directory you run Claude Code in.**

`cd <agent-dir> && claude`. The agent's `CLAUDE.md` is project memory, its
`.claude/settings.json` grants tools, and `output/` is the working directory.

Chosen over installing agents as Claude Code subagents (`.claude/agents/*.md`),
which loses the per-agent working directory and has to install into someone
else's project, and over owning an Agent SDK runtime, which is a whole
execution environment to maintain before the toolkit has proved its
composition model. Subagent export remains available later as a second output
target; a real runtime waits for the Codex and Foundry milestone.

*Consequence:* the toolkit gains a **render** step. A resolved configuration
compiles into runtime artefacts inside the agent directory. Without it,
`permissions`, `guardrails` and `model` are decorative fields.

*Implemented by:* TODO 4.2, 5.1, 7.3.

**D11 — A rendered artefact is a cache with a validity check, not a copy.**

Rendering writes derived files, which looks like the snapshot D2 forbids. It
is reconciled by three rules, all of which are required:

1. `agent.yaml` and the baseline remain the only source of truth.
2. Rendered content lives in a marked, machine-owned region, regenerated
   wholesale and never hand-edited. Content outside the markers is never
   touched.
3. The region carries a hash of the resolved config, so drift from the
   baseline is detectable and reportable rather than silent.

Drop rule 3 and the toolkit has quietly become the copy-at-creation system the
design exists to avoid.

*Implemented by:* TODO 5.1, 5.4, 7.2.

**D12 — Capability is granted from a controlled vocabulary, and web search and
fetch are granted by default.**

`permissions_scope.tools` used an undefined vocabulary that mapped to no
runtime, and `external_calls` conflated web search, page fetching, MCP and
arbitrary egress into one boolean. Both are replaced by a `capabilities` array
over a closed set, plus a `web` block carrying parameters only.

The baseline grants `web.search` at every risk posture and `web.fetch` at all
but the strictest. Read-only network access is a lower risk than the
`file.write` the baseline already grants, and the failure mode of withholding
it — an agent that silently cannot check anything, discovered at run time — is
worse than the risk it avoids.

*Consequence:* a breaking schema change, `schema_version` 1 to 2. Deliberate:
the migration path has never been exercised and this is a change small enough
to prove it on.

*Detail:* [`proposals/runtime-contract.md`](proposals/runtime-contract.md).
*Implemented by:* TODO 4.1 to 4.5.

**D13 — The generated `CLAUDE.md` renders everything derivable; intent stays
the user's, but is seeded.**

The original call — that `/create-agent` scaffolds structure, not intent, and
guessing produces confident nonsense — was half right. It holds for *what the
agent does*. It does not hold for identity, voice, capability limits or the
output contract, all of which are resolvable from the baseline and currently
reach the model only if the user retypes them by hand.

So the file splits: a generated region for everything derivable, and a process
section that stays the user's but is seeded from the agent's pattern rather
than shipped as an empty numbered list. The intent step carries a literal
`TODO:` marker, and validation warns while it is present — an unfinished agent
becomes a reportable state rather than a surprise at run time.

Two rules keep it lightweight. **Render a line only where it changes
behaviour**: guardrail booleans and formatting conventions at their default
value render nothing, because a line saying `input_filtering: true` costs
tokens and changes no behaviour a competent agent wouldn't already exhibit.
And target the generated region at 80 lines, warning above 150.

*Implemented by:* TODO 5.1 to 5.3.

**D14 — One `library/` of typed markdown modules is the unit of reuse below an
agent.**

Not three parallel `skills/`, `tools/` and `patterns/` directories — that is
three vocabularies to maintain before anything uses one. One directory, with
`kind: pattern | role | routine` in frontmatter, composed by reference from
`agent.yaml` and inlined at render time so the agent directory stays
self-contained.

Patterns are not composed: `operating_constraints.pattern` already names one,
so the renderer loads it automatically and there is only one place a pattern
can be named. Ship nine modules, not ninety; a module earns its place by being
written twice by hand first.

*Detail:* [`proposals/module-library.md`](proposals/module-library.md).
*Implemented by:* TODO 6.1 to 6.4.

**D15 — Python is the platform floor. Bash is developer tooling only.**

Development spans Windows and Linux, and every script in the path a user
actually walks was bash invoking `python3`. On Windows `python3` resolves to
the Microsoft Store stub, so `detect-profile.sh` reported `UNREADABLE` for
valid profiles and agent creation failed while blaming the profile.

Python is already a hard dependency, so making it the floor removes a
requirement rather than adding one. `detect-profile` is ported to Python;
`verify-toolkit.sh` stays bash because it is a developer pre-flight check, not
part of creating an agent. Any script that must resolve an interpreter tries
`python3`, then `python`, then `py -3`, verifies it actually runs, and
distinguishes "could not run Python" from "could not parse the file".

*Implemented by:* TODO 2.6, 9.1, 9.2.

### The interfaces

Four calls settled together, from the local-UI architecture review. They are
about who may call the toolkit and what they get back, not about what an agent
does.

**D16 — Every script a front-end could call is a public interface, with one
JSON envelope.**

`resolve-config.py` emits clean JSON; the two validators print `ERROR:` and
`WARN:` lines meant for a person and parse `sys.argv` by hand; `detect-profile`
prints a single word. Anything consuming that has to screen-scrape, and a
reworded message becomes a caller's bug.

So every such script takes `--json` and emits one envelope of `ok`, `errors`,
`warnings` and `data`, with each error carrying `field`, `message`, `legal` and
`fix` as separate values rather than flattened into a sentence. The validators
already compute all four. Human-readable output becomes one renderer over the
same structure instead of scattered `print` calls, which improves the CLI as
well.

Four scripts today, ten by the end of the backlog. Doing it at four is a
refactor of the last ten lines of each; doing it at ten is a project.

*Detail:* [`proposals/local-ui-readiness.md`](proposals/local-ui-readiness.md), G1.
*Implemented by:* TODO 3.3.

**D17 — The schema carries the interview.**

Asking for a baseline needs, per field, a question, help text, whether it is
asked in Express mode, its group, its default and its legal values. That is
split across the JSON schema, the bootstrap README and the bootstrap process
file, which already disagree — the README marks six characteristics Express,
the process asks five questions — and nothing states the reconciliation.

The schema becomes the one home, via `x-question`, `x-help`, `x-express`,
`x-group` and `x-infer` extension keywords, with `describe-schema.py --json`
emitting the descriptor. `x-infer` names an environment source for fields that
should never be asked; a field with neither `x-question` nor `x-infer` takes
its default silently, which is current behaviour made explicit. Unknown
keywords are ignored by JSON Schema, and `additionalProperties: false`
constrains the data rather than the schema document, so this is additive.

The interview, the builder documentation and any future form then read one
source. Composite questions, where one answer sets several fields, live in the
descriptor too — which is where the risk-posture mapping goes.

*Detail:* [`proposals/local-ui-readiness.md`](proposals/local-ui-readiness.md), G2.
*Implemented by:* TODO 3.4, 4.3.

**D18 — Render produces structure first; markdown is one renderer over it.**

If an agent's instructions exist only as prose inside `CLAUDE.md`, any host
that is not Claude-Code-shaped has to parse markdown to recover them.
`render-agent.py --json` emits the assembled sections, each naming the
config fields it came from, before formatting. (Written as
`render-claude-md.py` here and in the proposals; TODO 5.1 folded it together
with the permissions renderer, since both start from the same resolved config
and a split would mean two config hashes and two answers to "is this stale".)

Designed into the renderer this is nearly free, because the sections are
assembled either way. Retrofitted it is a rewrite of the renderer and of every
test that asserts on markdown.

This also de-risks D10. The expectation that a programmatic host can point the
Agent SDK at an agent directory and have its `CLAUDE.md` and
`.claude/settings.json` load is unverified. If it fails, a host assembles its
own prompt from this structured output instead.

*Detail:* [`proposals/local-ui-readiness.md`](proposals/local-ui-readiness.md), G3b.
*Implemented by:* TODO 5.1.

**D19 — No deterministic operation depends on a model.**

Creating an agent currently requires a model, because the file operations live
in `builders/create-agent/CLAUDE.md` as prose. The testability argument for
moving them into scripts is real but small. The larger one is that a form,
making no model call at all, must be able to produce a valid agent.

That is the acceptance test for the authoring half of the toolkit, and it is
easy to violate one item at a time. Every deterministic operation gets a
script. Builder prose orchestrates and interviews, and does nothing a script
could do — which makes the model-driven interview an accelerator rather than
the only way in.

*Detail:* [`proposals/local-ui-readiness.md`](proposals/local-ui-readiness.md), G3.
*Implemented by:* TODO 3.1, 3.2.

---

## Open

None. All nineteen decisions are settled.

Add a new entry here when a design call is genuinely undecided and blocks
work, with the options, a recommendation, and the backlog items it blocks.
Move it into the settled section once called.
