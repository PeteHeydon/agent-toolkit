# Proposal: local UI readiness

Status: **accepted** 2026-09-10. Recorded as D16 to D19 in
[`../decisions.md`](../decisions.md); the backlog deltas below are applied in
`TODO.md` as items 3.3 to 3.5 and amendments to 3.1, 4.3, 5.1, 7.1 and 10.0.

An architecture review against a future goal: a local UI where an end user
creates agents and interacts with them, without a CLI. Not a plan to build it.
The question is narrower and more urgent — **which v1 decisions, made now,
would be expensive to unmake then?**

## The short answer

Nothing in v1 is hostile to a UI. The direction of travel is right: config in
files, deterministic work in scripts, a render step that writes into the
agent's own directory.

Four things are missing, all cheapest to add now, and all of which improve v1
on their own merits:

| | Gap | Cost now | Cost later |
|---|---|---|---|
| G1 | Machine-readable output is inconsistent across scripts | Small: 4 scripts | Every consumer screen-scrapes prose |
| G2 | No single source for "what to ask the user" | Small: extend the schema | A fourth copy of the question set |
| G3 | Render's output exists only as markdown prose | Small: design it into 5.1 | Retrofit, or every host parses markdown |
| G4 | No reserved namespace for toolkit-managed state | Trivial: a naming rule | A UI's state files collide with the user's |

The rest of this document is the reasoning.

## A UI is two products, not one

They have almost nothing in common, and conflating them is how this gets
mis-scoped.

**Authoring** is CRUD over configuration. Create a baseline, create an agent,
edit fields, see what an agent resolves to, validate, compose modules. It is a
form over a schema, and it needs no model at all.

**Interacting** is a chat surface with an agent loop behind it: streaming,
tool-use display, permission prompts, history, cancellation.

Authoring is close to solved by work already in the backlog. Interacting is a
genuine open question, and it is the one D10 touches.

---

## Authoring

### What the UI needs

For each operation, something it can call and parse:

| Operation | Exists today |
|---|---|
| Read the baseline, resolved, with provenance | Yes: `resolve-config.py --json` |
| List agents with status | 5.4, 7.1 (`agent-status.py`) |
| Create an agent | 3.1 (`scaffold-agent.py`) |
| Re-render after an edit | 5.1, 7.2 |
| Validate and show errors against fields | Partly: validators exist, output is prose |
| **Know what to ask, and what the legal answers are** | **Nowhere** |

The first five are on the backlog. The sixth is the gap that matters.

### G1 — one output contract for every script

`resolve-config.py` takes `--json` and emits a clean envelope. The two
validators parse `sys.argv` by hand and print `ERROR:` and `WARN:` lines meant
for a person. `detect-profile.sh` prints a single word.

A UI consuming that has to screen-scrape, and every message reworded later
becomes a UI bug. Worse, a validation error is exactly the thing a form wants
to attach to a field, and the field name is currently only recoverable by
string-splitting the message.

**Proposed:** every script that a front-end could call takes `--json` and emits
one envelope.

```json
{
  "ok": false,
  "errors":   [{"field": "operating_constraints.pattern",
                "message": "'pipelines' is not a legal value",
                "legal": ["standalone", "pipeline", "..."],
                "fix": "Use one of the legal values"}],
  "warnings": [{"field": "operating_constraints.model", "message": "..."}],
  "data": {}
}
```

The validators already compute `field`, `legal` and a suggested fix — they
currently flatten all three into a sentence. This is mostly a refactor of the
last ten lines of each script, and it makes the CLI output better too, because
the renderer for humans becomes one function instead of scattered `print`
calls.

Four scripts today. Ten by the end of the backlog. Do it at four.

### G2 — the question set has three homes already

This is the highest-regret item in the review.

To ask a user for a baseline you need, per field: a question, help text,
whether it is asked in Express mode, its group, its default, and its legal
values. That knowledge is currently split:

| Source | Holds | Count |
|---|---|---|
| `baseline-profile.schema.json` | types, enums, defaults | 36 leaf fields, 10 enums, 24 defaults, **5 descriptions** |
| `builders/bootstrap-agent/README.md` | prose descriptions, Express markers | 22 characteristics, 6 marked `[E]` |
| `builders/bootstrap-agent/CLAUDE.md` | the interview script | 5 Express questions |

Three sources, and they already disagree: the README marks six characteristics
as Express, the process asks five questions. They are reconcilable — risk
posture covers both guardrails and permissions — but nothing states the
mapping, so the reconciliation lives in whoever last read both files.

A UI would be a fourth home, and the first one that cannot read prose.

**Proposed:** the schema carries the interview, via `x-` extension keywords.
JSON Schema ignores unknown keywords, and `additionalProperties: false`
constrains the *data*, not the schema document, so this is additive and breaks
nothing.

```json
"verbosity": {
  "type": "string",
  "enum": ["concise", "standard", "expansive"],
  "default": "concise",
  "description": "Default output length and density.",
  "x-question": "How much should agents write by default?",
  "x-help": "Concise means bullets over prose. You can override per agent.",
  "x-express": true,
  "x-group": "Voice & style",
  "x-infer": null
}
```

`x-infer` names an environment source for fields that should never be asked
(`locale` from the system). A field with neither `x-question` nor `x-infer`
takes its default silently, which is the current behaviour made explicit.

Then `describe-schema.py --json` emits the descriptor, and **three consumers
read the same one**: the bootstrap interview, a UI form, and the documentation
in the builder README, which becomes generated rather than maintained.

For the risk-posture case, where one question sets several fields, the
descriptor needs a composite question type: one question, a mapping from answer
to a set of field values. That mapping is being written anyway in item 4.3.
Putting it in the descriptor instead of in prose is the same work.

### G3 — the model must never be load-bearing for deterministic work

Today, creating an agent requires a model, because the file operations live in
`builders/create-agent/CLAUDE.md` as prose. Items 3.1 and 3.2 fix that, and the
backlog justifies them by testability. There is a second, larger reason.

**A form-only UI, making no model call at all, must be able to produce a valid
agent.** That is the acceptance test for the whole authoring half. If it
passes, the model-driven interview becomes an accelerator — "describe what you
want and I'll fill the form in" — rather than the only way in.

This is worth recording as a decision because it constrains future work in a
way that is easy to violate one item at a time. Every deterministic operation
gets a script; the builder prose orchestrates and interviews, and does nothing
a script could do.

---

## Interacting

### The fork D10 creates, and why it isn't a dead end

D10 says an agent is a directory you run Claude Code in. A UI cannot run a
directory. So the question is whether D10 has to be revisited.

It does not, provided one thing holds: **the agent directory stays the unit,
and render keeps writing files into it.** Four ways to drive one:

| Approach | Local? | Structured interaction | Effort |
|---|---|---|---|
| Shell out to the `claude` CLI in the agent dir | Yes | Poor: no per-turn control, awkward streaming | Low |
| **Claude Agent SDK** (`claude-agent-sdk`) | Yes | Full: agent loop, tools, permissions, sessions, hooks | Medium |
| Managed Agents | No, hosted | Full | Medium |
| Raw Messages API and own loop | Yes | Full, but you build everything | High |

The Agent SDK is Claude Code packaged as a library, with the same built-in
tools and permission model. That makes it the natural bridge: the same agent
directory serves `cd && claude` for CLI use and a programmatic host for the UI,
with no second definition of what the agent is.

**One assumption to verify before committing.** The recommendation rests on the
SDK loading an agent directory's `CLAUDE.md` and `.claude/settings.json` when
pointed at it as a working directory. That is the behaviour the CLI has, and
the SDK is the same harness, but it should be confirmed against the SDK's own
documentation rather than assumed. If it turns out the host must supply the
system prompt and tool policy itself, G3 below covers it — which is why that
gap is worth closing regardless.

### G3b — render should emit structure, not only prose

If an agent's instructions exist only as prose inside `CLAUDE.md`, then any
host that is not Claude-Code-shaped has to parse markdown to recover them. That
is true for the SDK if the assumption above fails, and certainly true for
Codex, Foundry, or a UI that wants to show "this agent's voice settings" as
fields rather than as a paragraph.

**Proposed:** `render-claude-md.py --json` emits the same content as structured
sections before it is formatted into markdown.

```json
{
  "config_hash": "sha256:...",
  "sections": {
    "operating_context": {"title": "...", "body": "...", "from": ["identity_context"]},
    "voice":             {"title": "...", "body": "...", "from": ["voice_style"]},
    "capabilities":      {"title": "...", "body": "...", "from": ["permissions_scope"]}
  },
  "process_seed": "...",
  "composed_modules": ["role/researcher"]
}
```

The markdown becomes one renderer over that structure rather than the only
representation. A host that needs a system prompt concatenates the sections. A
UI that wants a settings panel reads `from` to know which fields produced which
text.

Designed into 5.1 this is close to free, because the renderer has to assemble
sections either way. Retrofitted, it is a rewrite of the renderer plus every
test that asserts on markdown.

### G4 — reserve the namespace before something needs it

A UI needs per-agent state the CLI has never needed: conversation history, run
records, cached resolutions, draft edits. Today an agent directory has
`agent.yaml`, `CLAUDE.md`, `README.md`, `steering.md`, `output/` and
`.claude/`. Nothing says who owns what, so a UI would invent a layout and
eventually collide with a file the user created.

**Proposed rule, costing nothing to adopt now:**

- The toolkit owns `agent.yaml`, `CLAUDE.md`'s generated region, `README.md`,
  `.claude/`, and a reserved `.agent/` directory for toolkit-managed state.
- The user owns `steering.md`, `output/`, `CLAUDE.md` outside the markers, and
  anything else in the directory.
- Nothing outside that reserved set is ever written or deleted by a toolkit
  script.

`.agent/` need not be created now. Reserving the name, and writing the
ownership rule into `docs/architecture.md`, is the whole of the work. It also
answers a question the current backlog leaves open: whether `output/` is a flat
dump or per-run. Under this rule it stays the user's flat results directory,
and per-run bookkeeping goes in `.agent/` if it is ever needed.

---

## What not to build

Named explicitly, because each is a plausible-sounding way to spend months
before the toolkit produces a working agent.

- **No HTTP API or daemon.** A local UI can invoke scripts. An API is a second
  interface to keep in sync with the first, and the first is not finished.
- **No runtime abstraction layer.** One runtime exists. `runtimes/*.yaml`
  already handles the part that genuinely varies. An abstraction designed
  against a single implementation is a guess.
- **No session or run tracking.** Reserve the namespace, build nothing.
- **No database.** Files are the right substrate for a single-user local tool:
  diffable, git-friendly, portable, and inspectable when something goes wrong.
  D5's portability argument depends on config being files.
- **No UI framework choice.** It constrains nothing upstream, so deciding it
  now buys nothing and dates fastest.

## Backlog deltas

Applied. Small, and mostly amendments rather than new work.

| Item | Change |
|---|---|
| **New 3.3** | JSON envelope across all scripts (G1) |
| **New 3.4** | `describe-schema.py` and `x-` schema keywords (G2) |
| 3.1 | Acceptance adds: a valid agent can be scaffolded with no model call |
| 4.3 | The risk-posture mapping goes into the descriptor, not into prose |
| 5.1 | Acceptance adds: `--json` structured sections (G3b) |
| 7.1 | `agent-status.py` supports `--json` |
| 1.2 follow-up | `docs/architecture.md` gains the directory ownership rule (G4) |
| 10.0 | Add: verify the Agent SDK's handling of an agent directory |

Sequencing does not change. 3.3 and 3.4 sit before section 4 because 4.1 edits
the schema and 4.3 writes the risk-posture mapping — doing those after the
descriptor exists is the same work in the right place, and doing them before
means writing the mapping twice.
