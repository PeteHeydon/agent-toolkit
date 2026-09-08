# Tutorial: Your First Agent

A worked example, start to finish: one baseline profile, one real agent, built
with sample answers you can follow along with or substitute your own.

This is a walkthrough of one concrete build. For the command reference —
every flag, every mode, the full options table — see
[`getting-started.md`](getting-started.md). Read this one first if you'd
rather watch something get built than skim a reference.

## What we'll build

**meeting-notes-agent** — takes someone's rough, half-formed meeting notes and
turns them into a clean summary for the team: decisions, action items, open
questions. Internal use, nothing client-facing, low risk if it gets something
wrong — a reviewer reads the output before it goes anywhere.

That risk profile matters. It's why the baseline we set up below stays
conservative by default and why this particular agent doesn't need to override
much of anything.

## Prerequisites

```bash
git clone <repo> && cd agent-toolkit
pip install pyyaml jsonschema
export ANTHROPIC_API_KEY="sk-ant-..."
bash scripts/verify-toolkit.sh
claude
```

Expect two warnings on a clean install — no baseline yet, and possibly no API
key. Both get resolved below.

---

## Step 1 — Bootstrap the baseline

Everything downstream inherits from this, so it comes first, even though this
tutorial is nominally about the agent. Run:

```
/bootstrap-profile
```

No baseline exists yet, so you land straight in the interview. Take **Express**
— five questions, defaults for everything else:

> **Express** — I'll ask ~5 questions, infer or default the rest, then show you
> everything for review before writing.

Here's what we answer, and why:

| Question | Our answer | Why |
|---|---|---|
| Domain | `internal operations` | Broad enough to cover more than just meeting notes later |
| Audience | `internal_team` | This never leaves the building |
| Tone of voice | `friendly, direct` | Summaries for colleagues, not a client deliverable |
| Verbosity | `concise` | Nobody wants a five-paragraph recap of a 15-minute standup |
| Risk posture | `low — always validate output, keep it workspace-only` | Maps to `guardrails.output_validation: true` and `permissions_scope.filesystem: workspace_only` |

Everything else — locale, model, pattern, output location — is inferred or
defaulted. You never see a question for them.

### Confirm

Before anything is written, the tool renders the complete profile back to
you, with a marker on every line showing where the value came from:

```yaml
identity_context:
  locale: "en-AU"                  # inferred from system
  domain: "internal operations"    # you
  audience: "internal_team"        # you

voice_style:
  tone_of_voice: "friendly, direct"  # you
  verbosity: "concise"                # you

operating_constraints:
  model: "claude-sonnet-4-6"       # default
  pattern: "standalone"            # default
  guardrails:
    output_validation: true        # you (risk posture)
    human_in_the_loop: false       # default
  permissions_scope:
    filesystem: "workspace_only"   # you (risk posture)
```

Say yes. **Result:** `~/.agent-toolkit/baseline.yaml`.

Nothing is written until this point — if something looks wrong, this is where
you catch it, not after.

---

## Step 2 — Create the agent

```
/create-agent meeting-notes-agent
```

The tool checks the baseline exists and is valid (it does — you just made it),
then shows you what you're about to inherit before asking anything:

```
Inherited configuration:
  domain:     internal operations
  audience:   internal_team
  tone:       friendly, direct
  verbosity:  concise
  model:      claude-sonnet-4-6
  pattern:    standalone
  output:     ./output
```

Express mode asks four questions:

| Question | Our answer | Why |
|---|---|---|
| Description | `Turns rough meeting notes into a clean team summary — decisions, action items, open questions.` | One line, used in the scaffolded README |
| Pattern | *keep* `standalone` | One input, one output, no reason for anything fancier |
| Model | *keep* `claude-sonnet-4-6` | Summarising notes doesn't need a top-tier model |
| Anything else to override? | *no* | The baseline already fits this agent |

That last "no" is the normal answer. A short `agent.yaml` is the goal, not a
failure to customise.

### Confirm

You're shown the file about to be written — which should be almost empty —
and the fully resolved configuration with provenance:

```yaml
# agent.yaml to be written
schema_version: 1
extends: "~/.agent-toolkit/baseline.yaml"
name: "meeting-notes-agent"
description: "Turns rough meeting notes into a clean team summary — decisions, action items, open questions."
```

```
model: claude-sonnet-4-6        # baseline
pattern: standalone             # baseline
tone_of_voice: friendly, direct # baseline
output_validation: true         # baseline
```

Accept it. **Result:** `~/.agent-toolkit/agents/meeting-notes-agent/`:

```
meeting-notes-agent/
├── agent.yaml       # exactly the four lines above
├── CLAUDE.md         # process skeleton — empty, ours to fill in next
├── README.md
├── steering.md       # empty
└── output/
```

---

## Step 3 — Write what it actually does

`/create-agent` deliberately leaves `CLAUDE.md`'s process section empty — this
is the one part nobody can scaffold for you. Open
`~/.agent-toolkit/agents/meeting-notes-agent/CLAUDE.md` and fill in the numbered
steps. For this agent, something like:

```markdown
## Process

1. Read the raw notes provided in this session — no assumed file location,
   they're pasted or attached per run.
2. Identify three categories: decisions made, action items (with an owner if
   one was stated), and open questions nobody resolved.
3. Write the summary in that order, under those three headers. Concise —
   bullet points, not prose. If a category is empty, say so in one line
   rather than omitting the header.
4. Never invent an owner, a decision, or a deadline that wasn't in the notes.
   If it's unclear who owns something, write "owner unclear" rather than
   guessing.
5. Flag anything you're not confident summarised correctly rather than
   smoothing over it — this agent's baseline has `output_validation` on, so
   the output gets checked before it's shared; make that check easy.
```

That last step exists because of a decision made two steps ago and one layer
up — the baseline's risk posture answer. That's the inheritance model working
as intended: the agent's process reflects a constraint it never had to
restate.

---

## Step 4 — Try it

Give the agent a real (or realistic) set of rough notes in a session and see
what comes back. If the summary is too long, too formal, or missing something
structural, you have two places to fix it, and picking the right one matters:

- **Something specific to this agent** (it should always flag action items
  without an owner more loudly, say) → edit `CLAUDE.md`'s process steps.
- **Something about voice or verbosity that you'd want from *every* agent**
  (too formal, too long, wrong tone entirely) → edit the baseline instead.

That second option is the whole point of the baseline existing. If "concise"
turns out to mean something different than you expected, fix it once at
`~/.agent-toolkit/baseline.yaml` and every agent that hasn't overridden
`verbosity` picks it up — not just this one.

---

## Step 5 — Inspect what it resolves to

Whenever something behaves unexpectedly, ask where the value actually came
from before guessing:

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/meeting-notes-agent/agent.yaml --explain
```

```
model: claude-sonnet-4-6                # baseline
pattern: standalone                     # baseline
verbosity: concise                      # baseline
output_validation: true                 # baseline
```

Every line is annotated. Nothing here says `# meeting-notes-agent` because we
accepted every baseline default — which is exactly what the near-empty
`agent.yaml` from Step 2 predicted.

### Prove the inheritance model to yourself

Change one thing in the baseline and watch it move without touching the agent:

```bash
sed -i 's/verbosity: "concise"/verbosity: "standard"/' ~/.agent-toolkit/baseline.yaml

python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/meeting-notes-agent/agent.yaml --explain | grep verbosity
# verbosity: standard                   # baseline
```

`agent.yaml` never changed. The agent's summaries just got a little longer,
because the baseline moved and nothing pinned this agent against it.

---

## What you built

- One baseline (`~/.agent-toolkit/baseline.yaml`) encoding your defaults —
  domain, tone, verbosity, and a conservative risk posture
- One agent (`meeting-notes-agent`) that inherits almost all of it, overriding
  nothing but its own description
- A `CLAUDE.md` process that reflects the baseline's guardrail without
  restating it

## Next

- Build a second agent with a genuinely different risk profile — an
  `evaluator-optimizer` pattern, say — and watch how much *more* of its
  `agent.yaml` ends up populated, because now it actually diverges from the
  baseline. See [`getting-started.md`](getting-started.md) for the full
  command reference.
- [`precedence-and-inheritance.md`](precedence-and-inheritance.md) — the merge
  rules behind what you just watched happen in Step 5
- [`testing.md`](testing.md) — if you're editing the toolkit itself, not just
  using it
