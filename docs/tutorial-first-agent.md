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

That risk profile matters. It is why the baseline below takes the middle risk
posture rather than the strictest, and why this particular agent ends up
overriding almost nothing.

## Prerequisites

```bash
git clone <repo> && cd agent-toolkit
pip install pyyaml jsonschema
export ANTHROPIC_API_KEY="sk-ant-..."
bash scripts/verify-toolkit.sh
claude
```

Expect three warnings on a clean install: no baseline yet, possibly no API key,
and four patterns without a process skeleton. The first two get resolved below
and the third needs nothing from you. A **FAIL** is different — stop and fix it
before going on.

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
| Risk posture | `Balanced` | One answer, several fields: `filesystem: workspace_only`, a capability set that can read, write and search the web, and `output_validation: true` |

Everything else — locale, model, pattern, output location — is inferred or
defaulted. You never see a question for them.

Risk posture is one question that sets six fields, which is why you are not
asked to name a capability. The three answers are Cautious, Balanced and
Autonomous; all three grant web *search*, and all but Cautious grant page
*fetching*, because an agent that silently cannot look anything up is a worse
failure than the risk it avoids.

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
  model: "claude-sonnet-5"         # default
  pattern: "standalone"            # default
  guardrails:
    output_validation: true        # you (risk posture)
    human_in_the_loop: false       # you (risk posture)
  permissions_scope:
    filesystem: "workspace_only"   # you (risk posture)
    capabilities:                  # you (risk posture)
      - file.read
      - file.search
      - file.write
      - web.search
      - web.fetch
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
  model:      claude-sonnet-5
  pattern:    standalone
  output:     ./output
```

Express mode asks up to five questions:

| Question | Our answer | Why |
|---|---|---|
| Description | `Turns rough meeting notes into a clean team summary — decisions, action items, open questions.` | One line, used in the scaffolded README |
| Pattern | *keep* `standalone` | One input, one output, no reason for anything fancier |
| Model | *keep* `claude-sonnet-5` | Summarising notes doesn't need a top-tier model |
| Web access | *neither* | It summarises what you paste in; it has no reason to browse. Saying nothing leaves the baseline's answer in place |
| Anything else to override? | *no* | The baseline already fits this agent |

That last "no" is the normal answer. A short `agent.yaml` is the goal, not a
failure to customise.

### Confirm

You're shown the file about to be written — which should be almost empty —
and the fully resolved configuration with provenance:

```yaml
# agent.yaml to be written
schema_version: 2
extends: "~/.agent-toolkit/baseline.yaml"
name: "meeting-notes-agent"
description: "Turns rough meeting notes into a clean team summary — decisions, action items, open questions."
```

```
model: claude-sonnet-5        # baseline
pattern: standalone             # baseline
tone_of_voice: friendly, direct # baseline
output_validation: true         # baseline
```

Accept it. **Result:** `~/.agent-toolkit/agents/meeting-notes-agent/`:

```
meeting-notes-agent/
├── agent.yaml            # exactly the four lines above
├── CLAUDE.md             # generated region + a seeded process, one step ours
├── README.md
├── steering.md           # empty
├── run.sh / run.ps1      # start Claude Code in this directory
├── .claude/
│   └── settings.json     # generated: the tools this agent may use
├── .agent/
│   └── render.json       # generated: what config the above came from
└── output/
```

Open `CLAUDE.md` before going further. The top of it was written *for* you,
from the baseline you just made:

```markdown
## Operating context
You work in internal operations.
Your output is for an internal team audience.
Use en-AU spelling, date and currency conventions.

## Voice
Write in a friendly, direct register.
Be concise. Prefer bullets to prose, and stop when the point is made.
```

That is the personalisation actually reaching the model. It sits between
`BEGIN GENERATED` and `END GENERATED` markers and is rewritten on every
render, so do not edit inside them — everything below is yours.

---

## Step 3 — Write what it actually does

`/create-agent` seeds the process from the agent's pattern and leaves exactly
one step for you:

```markdown
1. Restate the task in one line and confirm you have the inputs it needs.
2. TODO: the work this agent does. Replace this step.
3. Check the result against the constraints above before returning it.
4. Write the output per the contract above.
```

Steps 1, 3 and 4 are properties of the `standalone` pattern, so the toolkit can
write them. Step 2 is intent — and guessing at intent produces confident
nonsense, so it stays yours. Until you replace it, `/list-agents` reports this
agent as unfinished and validation warns; that is deliberate.

Open `~/.agent-toolkit/agents/meeting-notes-agent/CLAUDE.md` and replace step 2
with the real work. For this agent, something like:

```markdown
## Process

1. Restate the task in one line and confirm you have the inputs it needs.
2. Read the raw notes from this session and sort them into three categories:
   decisions made, action items with an owner where one was stated, and open
   questions nobody resolved. Never invent an owner, a decision or a deadline
   that was not in the notes — write "owner unclear" instead of guessing.
   Write the summary under those three headers, in that order, and say so in
   one line when a category is empty rather than dropping the header.
3. Check the result against the constraints above before returning it.
4. Write the output per the contract above.
```

Note what step 2 does *not* say. It does not say "be concise", or "write for an
internal team", or "check your output before returning it" — those are in the
generated region above, inherited from the baseline. The process only carries
what is specific to this agent.

That is the inheritance model doing its job: an agent's steps reflect
constraints they never had to restate.

---

## Step 4 — Try it

```bash
cd ~/.agent-toolkit/agents/meeting-notes-agent && claude
```

The `cd` matters more than it looks. Claude Code loads `CLAUDE.md` and
`.claude/settings.json` from the directory it starts in — that is what makes
this a *meeting-notes agent* rather than a plain session. There is a `run.sh`
and a `run.ps1` in the directory that do the same thing from anywhere.

Give the agent a real (or realistic) set of rough notes in a session and see
what comes back. If the summary is too long, too formal, or missing something
structural, you have three places to fix it, and picking the right one matters:

- **Something specific to this agent** (it should always flag action items
  without an owner more loudly, say) → edit `CLAUDE.md`'s process steps.
- **Something specific to this agent that you are still working out** → write
  it in `steering.md` instead. That file is for corrections you have not yet
  decided are permanent, and `/review-agent` later reads it back to you.
- **Something about voice or verbosity that you'd want from *every* agent**
  (too formal, too long, wrong tone entirely) → edit the baseline instead.

That third option is the whole point of the baseline existing. If "concise"
turns out to mean something different than you expected, fix it once at
`~/.agent-toolkit/baseline.yaml` and every agent that hasn't overridden
`verbosity` inherits the change — not just this one. Step 5 shows exactly what
that does and does not move on its own.

---

## Step 5 — Inspect what it resolves to

Whenever something behaves unexpectedly, ask where the value actually came
from before guessing:

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/meeting-notes-agent/agent.yaml --explain
```

It prints the whole resolved configuration, every line annotated with the
layer it came from, under a header naming the files it merged:

```
# Resolution chain (lowest precedence first):
#   ~/.agent-toolkit/baseline.yaml
#   ~/.agent-toolkit/agents/meeting-notes-agent/agent.yaml

...
voice_style:
  tone_of_voice: friendly, direct                    # baseline
  verbosity: concise                                 # baseline
operating_constraints:
  model: claude-sonnet-5                             # baseline
  pattern: standalone                                # baseline
  permissions_scope:
    filesystem: workspace_only                       # baseline
...
name: meeting-notes-agent                            # agent (meeting-notes-agent)
description: Turns rough meeting notes...            # agent (meeting-notes-agent)
```

Only `name` and `description` say `# agent (meeting-notes-agent)`. Everything
else says `# baseline` — which is exactly what the near-empty `agent.yaml`
from Step 2 predicted. It is long, so pipe it through `grep` when you are
chasing one field:

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/meeting-notes-agent/agent.yaml --explain | grep verbosity
```

### Prove the inheritance model to yourself — and find its second half

Open `~/.agent-toolkit/baseline.yaml`, change `verbosity: "concise"` to
`verbosity: "expansive"`, and ask the resolver what the agent is now:

```bash
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/meeting-notes-agent/agent.yaml --explain | grep verbosity
#   verbosity: expansive                                   # baseline
```

`agent.yaml` never changed. The baseline moved, nothing pinned this agent
against it, and the resolved configuration followed.

**Now look at what the agent will actually read:**

```bash
grep -A2 '## Voice' ~/.agent-toolkit/agents/meeting-notes-agent/CLAUDE.md
# ## Voice
# Write in a friendly, direct register.
# Be concise. Prefer bullets to prose, and stop when the point is made.
```

Still concise. This is the part worth understanding, and it is not a bug:
**configuration resolves live, but the instructions the model reads are
rendered once.** Ask the toolkit and it will tell you:

```bash
python3 builders/create-agent/scripts/agent-status.py
```

```
AGENT                VALID      RENDERED   FINISHED    OVERRIDES
meeting-notes-agent  yes        STALE      yes         none (tracks the baseline)

1 stale: the baseline has moved on since these were rendered. Re-render with
render-agent.py <agent-dir>.
```

`FINISHED` says `yes` because you replaced step 2 back in Step 3. Had you left
the `TODO:` in place, that column would read `TODO left` and `VALID` would read
`1 warn`.

`/refresh-agent meeting-notes-agent` closes the gap. Run the same `grep` again
and the second line now reads "Explain fully, including the reasoning behind
the answer." Nothing is lost while an agent is stale — your process, notes and
results are untouched — but it runs on out-of-date instructions until you
refresh.

So the rule has two halves, and both matter:

- **Config inherits by reference.** Edit the baseline, every agent that has not
  pinned that field resolves differently, immediately.
- **Rendered instructions are a cache with a validity check.** They go stale
  visibly rather than drifting silently, and `/refresh-agent --all` is how you
  catch them up after a baseline edit.

---

## What you built

- One baseline (`~/.agent-toolkit/baseline.yaml`) encoding your defaults —
  domain, tone, verbosity, and a risk posture that set six fields from one
  answer
- One agent (`meeting-notes-agent`) that inherits almost all of it, overriding
  nothing but its own description
- A `CLAUDE.md` whose top half was generated from that baseline and whose
  process carries only what is specific to this agent
- A `.claude/settings.json` you never edited, which decides what tools the
  agent may actually use — the capability set made real

## Next

- Build a second agent with a genuinely different risk profile — an
  `evaluator-optimizer` pattern, say — and watch how much *more* of its
  `agent.yaml` ends up populated, because now it actually diverges from the
  baseline. It also gets a different seeded process, one that tells it to
  critique and revise. See [`getting-started.md`](getting-started.md) for the
  full command reference.
- Try `/create-agent researcher --compose routine/web-research`, then
  `/validate-agent researcher`. If the baseline you built is Cautious, that
  module will be rejected for needing a capability the agent does not have —
  which is the toolkit refusing to build an agent told to do something it
  cannot do.
- `/review-agent meeting-notes-agent` once you have corrected it a few times in
  `steering.md`. It reads those corrections and says which should stop being
  corrections.
- [`precedence-and-inheritance.md`](precedence-and-inheritance.md) — the merge
  rules behind what you just watched happen in Step 5
- [`testing.md`](testing.md) — if you're editing the toolkit itself, not just
  using it
