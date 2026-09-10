# Backlog

Prioritised and numbered, ordered by recommended implementation sequence. Every
numbered section is now closed; what is left is section 10, which is deferred
by design.

Design record: [`docs/decisions.md`](docs/decisions.md), all nineteen decisions
settled. How the pieces fit: [`docs/architecture.md`](docs/architecture.md).
The three proposals in [`docs/proposals/`](docs/proposals/) are all implemented
— read them for *why* a thing is shaped the way it is, not for what to do next.

## Status

**Every numbered section is complete.** See Recently closed.

An agent has a full life: created, run, listed, refreshed, migrated, edited,
reviewed and validated. A resolved configuration reaches it both as tool
permissions it cannot exceed and as the generated region of the one file the
model reads. A baseline edit reaches every agent that did not pin the field,
and any agent left behind reports as stale rather than drifting quietly. There
is a unit of reuse below "whole agent", checked against what each agent is
actually allowed to do.

**Two known gaps**, both recorded in section 10 and worth knowing before
relying on the toolkit:

- The per-domain web rule form in `runtimes/claude-code.yaml`
  (`WebFetch(domain:...)`) was written from memory, not from Claude Code's
  documentation. If it is wrong those rules are inert, which fails *open* for
  a blocked domain.
- The assumption that the Agent SDK loads an agent directory the way the CLI
  does is unverified. D18's structured render output is the fallback if it
  does not hold.

## What was found along the way

Kept because it explains why several decisions look the way they do. When this
backlog was written, the configuration layer and the behaviour layer were not
connected: a resolved config was produced and consumed by nothing, the only
artefact reaching a model was a `CLAUDE.md` the toolkit left nearly empty, and
permissions were declared in YAML that nothing enforced. Sections 3 to 6 closed
that gap in dependency order, which is why they had to run in that order.

## Item format

Every item carries **Objective**, **Why**, **Files**, **Approach**,
**Acceptance**, **Depends on**. Do not start an item whose dependencies are
open. Anything promoted out of section 10 should be written the same way —
the format is most of why these were executable one session at a time.

---

# 10.0 — Deferred

Not scheduled. Revisit when something above is finished or a real use case
arrives.

- **Remaining builders.** Design, Doco, TOV, Ops, Optimisation, Tool, Security,
  Refinement, Agent Skills. Status is tracked in the table in `README.md`, per
  2.4 — do not maintain a second list here. Each needs a real use case before it
  is built; the toolkit does not need nine more builders, it needs the two it
  has to produce agents that work.
- **Other runtimes.** Codex, AWS and Azure AI Foundry, and the OpenWebUI
  wrapper. The capability vocabulary (4.1) and the runtime mapping file (4.2)
  are the groundwork; a second runtime is a second mapping file plus a second
  renderer target. Do not start before one runtime is genuinely finished.
- **Subagent export.** `--export subagent` producing a
  `.claude/agents/<name>.md` for use inside another project, per OD1 option B.
  Wait until someone wants to run a toolkit agent inside an existing repo.
- **Verify Claude Code's per-domain permission rule syntax.**
  `runtimes/claude-code.yaml` renders `permissions_scope.web.allowed_domains`
  and `blocked_domains` as `WebFetch(domain:...)` rules. That form was written
  from memory, not from Claude Code's documentation. If it is wrong the rules
  are inert, which fails open for a *blocked* domain — the direction that
  matters. Everything else in that file (the capability-to-tool map, allow and
  deny) is straightforward and exercised by tests; this one line is not.
- **Verify the Agent SDK's handling of an agent directory.** D10 and the
  local-UI review both assume the Claude Agent SDK loads an agent directory's
  `CLAUDE.md` and `.claude/settings.json` when pointed at it as a working
  directory. That is the CLI's behaviour and the SDK is the same harness, but
  it is unverified. Confirm against the SDK's own documentation before anything
  is built on it. D18's structured render output is the fallback if it does not
  hold.
- **Pattern research deep-dive.** The shortlist at the end of
  `docs/research/agentic-patterns-initial-summary.md`. Worth doing when the
  library (6.0) has enough use to show which patterns are actually reached for.

---

---

# Recently closed

## Section 9.0 - the platform floor is real

- **9.1 Detection is Python; bash is the interpreter probe.** `detect-profile.py`
  carries the six-state logic and both builders call it, like every other script
  they run. `detect-profile.sh` stays, and the item's "then remove it" is the
  one instruction here worth not following.
  The reason is that the acceptance — "no builder process invokes bash" — and
  the wrapper are answering different questions. A Python script cannot report
  its own absence, and on Windows `python3` is routinely the Microsoft Store
  stub, which prints an install prompt and exits without being an interpreter.
  That is the failure 2.6 was written to fix. So the wrapper keeps the one job
  only it can do: find a working interpreter, then delegate.
  What settled the builder question was counting: the two process files already
  invoke `python3` nine times between them. The wrapper was protecting the first
  command while the next nine failed anyway, so its protection there was
  illusory — and consistency with every other script is worth more. D11 asserts
  the two entry points agree, because a port that quietly disagreed with its
  wrapper would be worse than either alone. Tests D10-D12.
- **9.2 The Windows path is written down.** A short section in
  `getting-started.md` placed *before* the first command, because a first-run
  failure at the first command is the worst place to have one. It names the
  Store-stub alias explicitly — the command appears to exist, which is what
  makes it confusing — and says what to do about it.
  Four rows added to Common Issues, including `NO_PYTHON`, whose whole point is
  that **the profile has not been read**: the fix is the interpreter, and
  editing the profile in response is the wrong move.

## Section 8.0 - validation says what it knows and what it thinks

- **8.1 The semantic checks.** New `scripts/semantic_checks.py`, shared by both
  validators so a baseline is held to the same standard as an agent. Six checks:
  a pattern that needs a loop it has switched off, a loop with nobody to review,
  unsupervised full access, a budget that cannot cover the passes the pattern
  implies, context sources that are not there, and the composition checks moved
  out of `validate-agent.py` so every semantic check lives in one place. The
  loop-reviewer check moved out of the structural layer too, which is what the
  acceptance asked for.
  **Severity was the whole design problem, and the toolkit's own defaults
  settled it.** Full filesystem access plus shell plus no approval gate is
  exactly the Autonomous risk posture that ships — so erroring on it would fail
  the toolkit's own defaults, and the fix would have been to weaken the check.
  It warns. That fixed the line: an error means two fields contradict each
  other; a warning means the combination is coherent but worth a second look.
  N2 runs all three shipped postures through the checks to keep it honest.
  Two stale things fell out. `default_context_sources` defaulted to
  `skills/core`, a path in the `skills/` directory that 2.6's cleanup removed
  in favour of `library/` — a default nobody could satisfy, and the new check
  would have fired on every profile. It is now `[]`, with the example and every
  fixture updated. And `agent-minimal.yaml` turned out to pin
  `evaluator-optimizer` against a baseline whose loop is off: the fixture used
  as "a clean minimal override" was itself the contradiction N4 exists to
  catch. It now overrides something coherent, and the incoherent case is kept
  deliberately as `agent-incoherent-pattern.yaml`.
  Two tests were also quietly coupled to that fixture's exact shape — one
  appended YAML after whatever key happened to come last, so a fixture edit
  moved its block somewhere harmless and it would have passed while testing
  nothing. Both now build their own configuration. Tests N1-N8.
- **8.2 The validation builder.** `builders/validation-agent/` with the
  structure the others have, and `/validate-agent`. It runs the mechanical
  checks first and reports them verbatim, then does what no rule expresses:
  whether the process matches the description, whether the hand-written steps
  need capabilities the agent was not granted, whether the voice suits the
  audience.
  **Mechanical and judgment findings are reported separately and never merged.**
  One is a fact, the other is a reading that might be wrong, and running them
  together teaches the user to discount both. It has no scripts of its own —
  duplicating the checks would give two answers to one question — and it never
  edits, because a validator that fixes what it finds cannot be trusted to
  report what was broken.
  The line against `/review-agent` is stated in both READMEs, because the two
  are easy to confuse: validation asks *is this right*, refinement asks *should
  this become something else*. An agent can be perfectly valid and still be the
  wrong agent.

## Section 7.0 - an agent has a life after creation

- **7.1 + 7.2 + 7.3 `/list-agents`, `/refresh-agent`, and running one.** All
  three were mostly wiring over machinery 5.4 already built. `render-agent.py`
  gained `--all`, which walks every agent and **does not stop at the first
  failure** — one agent whose baseline has gone missing should not leave the
  other nine stale — and `agent-status.py` now shares that walk, so "which
  directories are agents" has one answer rather than two that can disagree.
  7.3 turned out to hide a real defect. The template copy is text-mode, so
  `run.sh` arrived without its executable bit and `./run.sh` — the command the
  agent's own README tells you to type — would have failed on Linux. The
  scaffolder now copies the template's mode. `getting-started.md` also still
  claimed the process section is left empty, which 5.3 stopped being true;
  fixed while there.
- **7.4 Agent files migrate too.** The migrator written for baselines turned
  out to handle `agent.yaml` unchanged, because the v1-to-v2 change lives in
  `operating_constraints.permissions_scope`, which both schemas shared. So the
  work was naming rather than building: `migrate-profile.py` became
  `migrate-config.py`, because a misnamed tool is one nobody finds. A v1 agent
  now validates as **stale rather than malformed**, with a message saying it
  needs migrating and naming the command — "does not match the current schema"
  left the user to guess a migration existed at all. Tests M13-M14.
- **7.6 `/edit-agent`, and the trap it closes.** Confirmed before building:
  an agent with a model override and a composed module, re-scaffolded with a
  single `--set` for verbosity, came back with **both silently gone**. Correct
  for the flow `--force` was built for, where `/create-agent` supplies every
  answer fresh from the interview; data loss the moment anything calls itself
  an edit, and the same family as the `rmtree` 3.5 removed.
  `--merge` starts from the agent's existing overrides and deep-merges the
  change, so a sibling leaf survives too. `--force` alone is deliberately
  unchanged and S16 pins that, rather than quietly altering behaviour someone
  may rely on. The command shows a **resolved** diff before writing, not a
  file diff, because values are what the user is deciding about.
- **7.5 `/review-agent`.** The `agent-refinement-agent` slot on the builder
  list finally earns itself, on the D9 test: promoting a correction takes
  judgment, not computation.
  Its job is deliberately narrow, because the obvious framing — evaluate how
  the agent performed — is not supportable. There is no run history and
  `local-ui-readiness.md` says to keep it that way. What *is* available is
  `steering.md`, which quietly accumulates the corrections the user keeps
  repeating. So the question the builder asks is promotion: a correction
  written three times should stop being a correction and become config, a
  composed module, or a process step.
  It writes nothing and proposes exact `/edit-agent` invocations. It has no
  scripts — everything computable is already computed by `agent-status.py` and
  `validate-agent.py`, and a second gatherer would drift from the first. Its
  README states plainly what it cannot see, rather than implying a depth of
  evaluation the toolkit cannot support.

## Section 6.0 - there is a unit of reuse below an agent

- **6.1 + 6.2 + 6.3 + 6.4 The module library.** Markdown with YAML
  frontmatter, three kinds in one directory (`pattern`, `role`, `routine`)
  rather than three parallel vocabularies, per D14. `scripts/module_utils.py`
  resolves `kind/name` user-library-first, so a personal module shadows a
  shipped one and `git pull` cannot overwrite it — and the shadowing is
  *reported*, because "why is my guidance not taking effect" is a miserable
  thing to debug.
  Nine modules ship, not ninety. The three patterns already existed: 5.3
  created `library/pattern/` early because it needed somewhere to put the
  process skeletons, so 6.1's format had to absorb four files rather than
  design for a greenfield, which is the right constraint to have had.
  **Composition is the point, and validation is what makes it safe.** Roles
  and routines are inlined into the generated region at render time — inlined,
  not linked, so the agent directory stays portable to a runtime that has never
  heard of this toolkit. Patterns are deliberately *not* composable: the
  `pattern` field already names one, and both `--compose pattern/x` and a
  `compose:` entry naming a pattern are refused with a pointer to that field.
  6.4 gave `run_semantic_checks()` its first real content, and it catches the
  exact failure this toolkit used to produce in silence: composing
  `routine/web-research` onto an agent without `web.fetch` now fails naming the
  module, the capability and the fix, rather than producing an agent that has
  been told to do something it cannot do. Above four modules warns — an agent
  that needs six is usually two agents.
  Tests L1-L14. `verify-toolkit.sh` gained a check that every shipped module
  loads, since a module that fails to load is not merely absent: an agent
  composing it breaks at render, having been configured to use guidance it
  never received. Adding `compose` to the baseline schema also added a 23rd
  characteristic, which the 3.4 drift check caught immediately — the README
  index was regenerated rather than hand-patched.

## Section 5.0 - the behaviour layer is connected

- **5.1 + 5.2 + 5.3 + 5.4 `CLAUDE.md` is generated, seeded, and checkable.**
  Done as one pass: 5.2 restructures the file 5.1 writes into, 5.3 fills the
  section 5.2 declares, and 5.4 checks what 5.1 rendered.
  **One renderer, not two.** The deferred question from 4.2 came due, and
  `render-permissions.py` became `render-agent.py`, which writes the generated
  region *and* `.claude/settings.json` in one pass from one resolved config.
  There is deliberately no flag to render one without the other: they share a
  config hash, and a half-rendered agent would carry two records of what it was
  built from and no way to say which is right. That is also what makes
  staleness a single question with a single answer.
  **Structure first, markdown second** (D18). `build_sections()` returns the
  region as data, each section naming the config fields it came from, and the
  markdown is one renderer over that — asserted by a test, so the structured
  output cannot quietly become a lie.
  **The size rule bites, and that is the point** (D13). A default baseline
  renders about 25 lines, under the 30 the acceptance guessed at. Every line
  that would have padded it out describes a value sitting at its schema
  default, which changes no behaviour. The upper bounds — 80 target, 150 warn —
  are the ones worth holding.
  **The open question this file carried from the start is answered.** Guessing
  at *intent* does produce confident nonsense, but "confirm the inputs" and
  "check the result against the constraints" are properties of the pattern, not
  intent. So `library/pattern/*.md` seeds the process, the intent step stays
  marked `TODO:`, and `validate-agent.py` warns until someone writes it — an
  unfinished agent is now a reportable state rather than a run-time surprise.
  **Staleness reconciles rendering with D2.** `agent-status.py` reports every
  agent's overrides, validity, render freshness and whether its intent was ever
  written. The convincing case is the negative one: editing the baseline's
  verbosity makes an inheriting agent stale but leaves an agent that *pinned*
  verbosity fresh, because staleness follows what an agent resolves to rather
  than whether the baseline file was touched.
  Tests G1-G8, T1-T7, S11-S13; `verify-toolkit.sh` gained a check that every
  pattern in the schema has a skeleton, which currently warns for four that
  fall back to standalone.

## Section 4.0 - capabilities reach the runtime

- **4.1 + 4.3 Schema v2: the capability vocabulary, and the risk posture that
  sets it.** Done as one item; see Status for why. Both schemas go to
  `schema_version: 2`. `permissions_scope.tools` (names that mapped to no
  runtime) and `external_calls` (one boolean conflating web search, page
  fetching and arbitrary egress) are replaced by `capabilities`, a closed
  enum of `file.read`, `file.search`, `file.write`, `shell`, `web.search`,
  `web.fetch` and `subagent`, plus a `web` block carrying `allowed_domains`
  and `blocked_domains`.
  The risk-posture composite now carries the three rows from
  `runtime-contract.md` in that vocabulary: Cautious grants read-only plus web
  search, Balanced adds `file.write` and `web.fetch`, Autonomous adds `shell`
  and `subagent`. So web search is granted at every posture and fetching at all
  but the strictest, per D12. The mapping exists in exactly one place, and
  `describe-schema.py --json` returns it. The shipped example baseline is now
  the Balanced row, which moved `output_validation` to `true` by default.
  Three things needed care. `capabilities` is an array whose items are an enum,
  which `extract_enums` does not see, so a new `extract_array_enums` feeds both
  a per-element validator check and the drift check — this is the one enum
  where drift grants access nobody defined. Both validators now error on a v1
  `tools`/`external_calls` key **naming the v2 replacement**, because whoever
  reads that message is mid-migration. And a domain list with `web.fetch`
  withheld is an error rather than accepted, since a config that looks like it
  bounds egress but cannot is worse than one that says nothing. Tests P10-P12,
  a second drift check, and R2 rewritten around capabilities.

- **4.2 Capabilities now reach the runtime.** New
  `builders/create-agent/scripts/render-permissions.py` compiles an agent's
  resolved capability set into `.claude/settings.json`, and
  `scaffold-agent.py` calls it, so creating an agent now produces one whose
  tool access is decided by its config rather than by whatever the user's
  global settings happen to allow. The capability-to-tool map is data
  (`runtimes/claude-code.yaml`), so a second runtime is a second file.
  Three calls in it were judgement rather than transcription. **Allow and deny
  are not symmetric**: an un-allowed tool prompts, and a prompt at the wrong
  moment gets answered yes, so a withheld high-consequence capability is denied
  outright — which tools those are is per-runtime data, not a toolkit-wide
  rule. **Filesystem posture wins over capability**: `file.write` under
  `filesystem: read_only` is contradictory and the restrictive reading is the
  safe one, so the tool is denied *and* dropped from allow rather than
  appearing in both lists. **The render carries a config hash** in
  `.agent/render.json` — D11 rule 3, and the first real use of the `.agent/`
  namespace 3.5 reserved. No timestamp, so an unchanged config re-renders
  byte-identically.
  `verify-toolkit.sh` gained a check that every capability in the schema is
  mapped by every runtime file; an unmapped one renders to no tool at all, so
  the agent would silently lose access it was granted. Tests W1-W10, including
  the `--path` case that proves a project's own `.claude/settings.json` is
  never touched.
  **One thing is unverified and flagged in 10.0:** the per-domain rule form
  `WebFetch(domain:...)` was written from memory rather than from Claude
  Code's documentation. If it is wrong those rules are inert, which fails open
  for a blocked domain.

- **4.4 Web access is a question, not a vocabulary.** `scaffold-agent.py`
  gains `--web` and `--no-web`, and `/create-agent` asks about web access in
  plain terms rather than making anyone name a capability.
  The flags expand to the agent's *whole* inherited capability set plus or
  minus the two web entries. That expansion is the item, not a detail:
  `capabilities` replaces the inherited array wholesale (D4), so a hand-written
  list naming only the web entries would leave an agent with no file access at
  all. Doing it in the script rather than in prose is what makes that
  impossible to get wrong. Two smaller calls came with it — a flag that changes
  nothing writes no override, because restating an inherited value pins the
  field against later baseline edits (D3); and a web flag alongside an explicit
  `--set` of the same array is refused rather than silently resolved.
  **One real gap surfaced while testing.** With `--no-web`, `WebFetch` was
  denied but `WebSearch` was merely un-allowed — so an agent the user had said
  must not reach the network could still search, given a prompt answered yes.
  `WebSearch` is now `high_consequence` in `runtimes/claude-code.yaml`, on a
  narrower argument than the other entries: D12 grants `web.search` at every
  posture, so its absence can only ever mean a deliberate withdrawal, and a
  deliberate withdrawal should be enforced rather than prompted. Tests S7-S10.
  *Note on the acceptance text:* it said `--web` on a Cautious baseline "adds
  both and nothing else". Since 4.1 settled that Cautious already grants
  `web.search`, only `web.fetch` is ever added. The result is the same set; the
  acceptance was written before that row existed.

- **4.5 The migration path works, and is a script.** Step 4 of the bootstrap
  process used to tell a model to back up someone's profile and rewrite it by
  hand. Migration is deterministic, so it is now
  `builders/bootstrap-agent/scripts/migrate-config.py` (D19), and the builder
  previews it with `--dry-run`, shows the user, and only writes on acceptance.
  The rule that makes it safe is that it **deep-copies the user's document and
  changes only what the version bump requires**, rather than rebuilding a
  profile from the fields it knows about. The second approach passes almost
  every test and still quietly discards anything it wasn't told about; M3
  holds the first one honest, including checking that a value whose *default*
  changed in v2 keeps the value the user actually had.
  Two things it reports rather than does silently. Migrating from v1 **grants**
  `web.search` that the profile withheld, because v2 splits `external_calls`
  and D12 puts search at every posture — an expansion of what someone's agents
  may do, applied during a command they ran for another reason, so it is a note
  with instructions for undoing it. And comments do not survive a round-trip
  through pyyaml; preserving them would mean a round-trip YAML library the
  toolkit does not otherwise need, so the script says so and points at the
  backup, which keeps them.
  The backup is `baseline.yaml.bak-<old-version>`, byte-identical to the
  original, and a second run refuses rather than overwriting it — it is the
  only copy of what the profile looked like before. Tests M1-M12, including
  the per-value tool mapping the acceptance asked for. `detect-profile.sh`
  needed no change; it has reported `STALE` correctly since 4.1 bumped the
  version constant.

## Section 3.0 - scaffolding is deterministic

- **3.1 `scaffold-agent.py` shipped.** Everything `builders/create-agent/CLAUDE.md`
  Step 4 left to a model's judgement is now a deterministic CLI: `--name`,
  `--dest`, `--description`, repeated `--set key.path=value`, `--extends`,
  `--force` and `--dry-run`. It copies `templates/agent/` with
  `{{AGENT_NAME}}`/`{{AGENT_DESCRIPTION}}` substituted, but writes `agent.yaml`
  itself via `yaml.safe_dump` rather than templating it — schema_version,
  extends, name, description and only the requested overrides — so a Windows
  path in `extends` can't reintroduce the backslash-escape bug 2.6 fixed.
  Output is JSON only, deliberately: the script is meant to be called by a
  builder or a future front-end, not read directly. `--dry-run` computes the
  exact manifest a real run produces without writing anything, which is the
  D19 acceptance test for the authoring half — a form-only caller can preview,
  then produce, a valid agent with no model call anywhere in the path. Tests
  S1-S5. `/create-agent` does not call it yet; that's 3.2.
- **3.2 `/create-agent` rewired around the script.** Steps 4 and 5 of
  `builders/create-agent/CLAUDE.md` no longer instruct a model to copy a
  directory or substitute placeholders — Step 4 is now one invocation of
  `scaffold-agent.py` with the answers gathered in Steps 2 and 3, and Step 5
  is the resolved-config report, unchanged. Step 1 grew a dry run of the same
  script as its existing-directory and bad-slug check, before the interview
  runs rather than after. A new Hard Rule 6 forbids hand-editing anything the
  script writes. Walked by hand end to end — precondition dry run, real
  scaffold with two overrides, `resolve-config.py --explain` — plus the
  existing-directory and validation-failure paths the process table describes;
  all three match what the table says happens.
- **3.3 One JSON envelope across every script.** New `scripts/cli_output.py`
  holds it — `ok`, `errors`, `warnings`, `data`, each issue carrying `field`,
  `message`, `legal` and `fix` as separate values rather than a formatted
  sentence. `validate-profile.py`, `validate-agent.py` and `resolve-config.py`
  all gained `--json`; the two validators build the same `issue()` dicts their
  plain-text renderer already used to print, so text output is byte-for-byte
  unchanged. `resolve-config.py`'s existing `--json` now nests under `data` —
  a breaking change to that shape, deliberate, and updated in its own tests.
  `detect-profile.sh` (still bash; 9.1 hasn't landed) got a hand-rolled `--json`
  that wraps its state with `errors`/`warnings` always empty — it reports a
  state, not itemized diagnostics, so `ok` can be `false` with no `errors`,
  the one documented exception to `ok == !errors`. `scaffold-agent.py`'s own
  shape moved into the envelope too, and its validation step now calls
  `validate-agent.py --json` and folds that envelope's errors and warnings
  straight into its own, so a caller sees why `ok` is false without reaching
  into a nested result. New `tests/test_cli_output.py`: unit tests on the
  module plus one success and one failure per script (C1-C3); 15 new tests
  total, all previously-flat JSON consumers (`test_resolve.py`, `test_scaffold.py`,
  `scripts/verify-toolkit.sh`'s round-trip check) updated for the `data` nesting.

- **3.4 The schema carries the interview.** `x-question`, `x-help`, `x-express`,
  `x-group`, `x-label` and `x-infer` on the leaf fields of the baseline schema,
  plus `x-groups` and `x-composite-questions` at its root; new
  `scripts/describe-schema.py` reads them out as a descriptor. Three consumers
  now read one source: the bootstrap interview, the characteristics list in the
  builder README (generated into a marked region, `--write` to regenerate), and
  any future form. The three-way disagreement is resolved and, more usefully,
  *stated*: guardrails and permissions_scope carry `x-express-via: risk_posture`,
  which is why the README's six Express characteristics are five questions.
  Risk posture became the first composite question, its three answers each
  carrying the exact field values they set — encoded in **v1 vocabulary**, with
  Balanced reproducing today's defaults exactly, so nothing contradicts the
  shipped example. 4.3 revises those values when v2 capabilities land; that is
  the only place the mapping lives.
  Two things fell out of doing it. Four fields — `max_tokens_per_run`,
  `latency_target_seconds`, `default_context_sources` and `permissions_scope.tools`
  — plus `model` had no schema default and were not asked in Express, so an
  Express run could not have filled them; defaults matching the shipped example
  were added. And the new rule that catches that class of gap (every leaf must
  be inferred, defaulted, or Express-asked) is enforced by the script, tested as
  X6, and run by `verify-toolkit.sh` as a pre-flight. Tests X1-X9.

- **3.5 The agent-directory ownership rule is recorded, and obeyed.**
  `docs/architecture.md` gains a "Who owns what" table: the toolkit owns
  `agent.yaml`, the marked region inside `CLAUDE.md`, `.claude/`, and a newly
  reserved `.agent/`; everything else in an agent directory is the user's and
  is never written or deleted by a toolkit script. `templates/agent/README.md`
  says the same thing to whoever opens the agent.
  Writing the rule down found that `--force` broke it. It called
  `shutil.rmtree` on the whole directory, so re-scaffolding an existing agent
  silently destroyed the process the user had written in `CLAUDE.md`, their
  `steering.md` guidance, and every result in `output/` — confirmed by
  reproducing it before the fix. `--force` now rewrites what the toolkit owns,
  creates whatever is missing, and deletes nothing; the result reports
  `written` and `preserved` so the builder can say which went where. Test S6
  covers it. The rule also settles a question the backlog had left open:
  `output/` stays a flat directory of the user's results, and any per-run
  bookkeeping goes in `.agent/`.

## Section 1.0 - the architecture is settled and recorded

- **1.1 Decisions recorded.** All six open decisions answered and moved into
  `docs/decisions.md` as D10 to D15: an agent is a directory you run Claude
  Code in; a rendered artefact is a cache with a validity check; capability
  comes from a controlled vocabulary with web search and fetch on by default;
  the generated `CLAUDE.md` renders everything derivable and seeds the rest;
  one `library/` is the unit of reuse; Python is the platform floor. The Open
  section is empty.
- **1.2 `docs/architecture.md` written.** The resolve-render-run pipeline, what
  each stage owns, what an agent directory contains, and why the working
  directory is load-bearing. Listed in `verify-toolkit.sh`.
- **1.3 Entry documents point at the record.** `HANDOFF.md` carries the five
  decisions a newcomer needs and links the rest; `README.md` and
  `repository-structure.md` link both new documents.

Also recorded: development spans **Windows and Linux**, both first-class.

## Section 2.0 - the ground is cleared

- **2.1 Model default moved to `claude-sonnet-5`**, which is both newer and
  cheaper than the `claude-sonnet-4-6` it replaced. `scripts/schema_utils.py`
  now owns `KNOWN_MODELS`, `MODEL_ALIASES` and `resolve_model()`; both
  validators warn - never error - on an unknown model, so a model newer than
  the toolkit still works, and resolve the bare aliases `opus`, `sonnet` and
  `haiku`, reporting the resolution. Tests P7 to P9.
- **2.2 `templates/agent/` is complete.** `steering.md` and `output/.gitkeep`
  now ship in the template rather than being created by prose instructions, and
  `.gitignore` carries an exception so the template's `output/` is committed.
  Step 4 of the create-agent builder is now "copy the template, substitute the
  placeholders", with an explicit rule against creating files the template
  doesn't hold.
- **2.3 The layout diagram matches the repository.** `skills/`, `tools/` and
  `patterns/` are gone, replaced by `library/` and `runtimes/` marked with the
  backlog item that creates them. Any directory that doesn't exist yet is
  marked as such.
- **2.4 One builder inventory.** The table in `README.md` is authoritative;
  `docs/vision.md` says explicitly that it describes scope, not status.
- **2.5 Precedence rules canonicalised.** `docs/precedence-and-inheritance.md`
  is marked canonical and is the only full statement. The builder process
  files, the create-agent README and `getting-started.md` are reduced to a
  summary plus a link; the example YAML files keep the arrays-replace warning
  only, because that one is read at the moment of editing.
- **2.6 Windows and Linux both work.** Three instances of the same defect:
  - `detect-profile.sh` ran `python3 ... 2>/dev/null`, and on Windows `python3`
    is the Microsoft Store stub. A valid profile was reported `UNREADABLE` and
    `/create-agent` refused to run. The script now resolves an interpreter that
    actually executes (`python3`, `python`, `py -3`, or `$AGENT_TOOLKIT_PYTHON`)
    and reports a new sixth state, `NO_PYTHON`, which says plainly that the
    profile has not been read. Both builders handle it. A non-numeric
    `schema_version` now reports `INVALID` instead of being read as 0 and
    reported `STALE`.
  - `verify-toolkit.sh` had the same bug and reported nine false failures on
    Windows, including "syntax error" in files that compile. It now resolves an
    interpreter the same way, and translates paths with `cygpath -m` before
    writing them into YAML.
  - The test harness substituted native Windows paths into double-quoted YAML
    scalars, where a backslash starts an escape sequence. 18 of 30 tests failed
    on that alone. `base.as_yaml_path()` now normalises them.

  The suite is 36 tests, green on Windows; `verify-toolkit.sh` reports 15
  passed, 0 failed. Tests D7 to D9 cover the environment-failure path,
  including that an environment failure outranks a genuinely malformed profile
  - with no interpreter, nothing is known about the file either way.

## Earlier

- Schema duplication - `scripts/schema_utils.py` derives `ENUMS` from each JSON
  schema at import time; `verify-toolkit.sh` and `tests/test_schema_sync.py`
  assert the two schemas agree where they share a field.
- Test harness - `tests/`, covering detection, both validators, resolution and
  schema drift.
- bootstrap-agent's missing scripts and docs rebuilt to match `HANDOFF.md`.
- `docs/tutorial-first-agent.md` - worked-example tutorial, separate from the
  `getting-started.md` reference.
- **Is the empty `CLAUDE.md` skeleton still the right call?** Answered as D13:
  no, but only half of it was wrong. Intent stays the user's; everything
  derivable from the resolved config is generated. See 5.1 to 5.3.
