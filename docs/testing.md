# Testing

## Pre-flight check

```bash
cd agent-toolkit
bash scripts/verify-toolkit.sh
```

Covers: required files present, dependencies installed, schemas and examples
parse and conform, schema-enum drift, every schema field being askable,
inferrable or defaulted, scripts compile, and a resolver round-trip asserting
leaf-level merge, provenance correctness, and cycle rejection.

Exit 0 means clean. Run it after any change to a script, schema, or required
file — it's the "is the toolkit even in place" check, distinct from the
behavioural test suite below.

## Manual test cases

These were exercised during development. They are the intended fixtures for the
automated harness — each one is a real behaviour that would break silently.

### Profile detection (`detect-profile.py`, `detect-profile.sh`)

| # | Setup | Expected |
|---|---|---|
| D1 | No file at `$AGENT_TOOLKIT_HOME/baseline.yaml` | `NONE` |
| D2 | Valid current profile | `VALID` |
| D3 | `schema_version` lower than current | `STALE` |
| D4 | Illegal enum value present | `INVALID` |
| D5 | Malformed YAML | `UNREADABLE` |
| D6 | `schema_version` *higher* than current | `INVALID` + "update the toolkit" |
| D7 | Valid profile, but no working Python interpreter | `NO_PYTHON`, never `UNREADABLE` |
| D8 | Malformed profile *and* no working interpreter | `NO_PYTHON` - nothing was read, so nothing is known |
| D9 | `$AGENT_TOOLKIT_PYTHON` set to a working interpreter | that interpreter is used |
| D10 | Every state, straight from the Python script | Same answers as the wrapper |
| D11 | Both entry points on the same profile | They agree |
| D12 | `--json` from the Python script | The envelope, with `data.state` |

**Two entry points, deliberately.** The builders call `detect-profile.py`,
like every other script they run. `detect-profile.sh` finds a working
interpreter first and delegates — the one job a Python script cannot do for
itself is report its own absence, and on Windows `python3` is routinely the
Microsoft Store stub rather than an interpreter. D11 exists because a port
that quietly disagreed with its wrapper would be worse than either alone.

```bash
export AGENT_TOOLKIT_HOME=/tmp/tk-test && rm -rf /tmp/tk-test && mkdir -p /tmp/tk-test

# D1
bash builders/bootstrap-agent/scripts/detect-profile.sh        # -> NONE

# D2
cp builders/bootstrap-agent/bootstrap-agent-example.yaml /tmp/tk-test/baseline.yaml
bash builders/bootstrap-agent/scripts/detect-profile.sh        # -> VALID

# D3
sed -i 's/^schema_version: 1/schema_version: 0/' /tmp/tk-test/baseline.yaml
bash builders/bootstrap-agent/scripts/detect-profile.sh        # -> STALE

# D5
printf 'schema_version: 1\n  bad: [unclosed\n' > /tmp/tk-test/baseline.yaml
bash builders/bootstrap-agent/scripts/detect-profile.sh        # -> UNREADABLE
```

### Profile validation (`validate-profile.py`)

| # | Case | Expected |
|---|---|---|
| P1 | Shipped example | valid, 0 warnings |
| P2 | Illegal `pattern` value | ERROR listing the legal set |
| P3 | Missing required field | ERROR naming the field |
| P4 | `evaluation_loop.enabled: true` with `reviewer: null` | ERROR — incoherent |
| P5 | Literal API key in `credentials` | ERROR + secret WARN |
| P6 | `max_tokens_per_run` outside sane range | WARN, not ERROR |
| P7-P9 | Known model / bare alias / unknown model | silent / WARN naming the resolution / WARN, still valid |
| P10 | A v1 profile using `tools` and `external_calls` | ERROR **naming the v2 replacement**, not just rejecting the file |
| P11 | An unknown capability | ERROR listing the legal capability set |
| P12 | A domain list with `web.fetch` not granted | ERROR — the list can never take effect |

**P10 is the migration message.** Rejecting a v1 profile is not enough: whoever
sees the error is mid-migration, so it names `capabilities` and the two web
capabilities that replaced `external_calls`.

### Resolution (`resolve-config.py`)

| # | Case | Expected |
|---|---|---|
| R1 | Agent overrides one leaf in a nested map | Override wins; **sibling keys still inherited** |
| R2 | Agent overrides an array | Array **replaces** wholesale, never appends |
| R3 | `--set key=value` | CLI layer wins over both file layers |
| R4 | `extends` pointing at itself | ERROR, cycle detected, no hang |
| R5 | `extends` chain deeper than 10 | ERROR, depth capped |
| R6 | `extends` target missing | ERROR naming the path |
| R7 | `--explain` output | Every leaf annotated with its source layer |
| R8 | `--baseline-only --summary` | Seven-line human summary |
| R9 | `--json` | The cli_output envelope; `data` contains `resolved`, `provenance`, `chain` |
| R10 | `--json` with a resolution error (missing `extends` target, cycle, ...) | `ok: false`, one entry in `errors` with `field: "extends"`, on stdout — not the stderr line the non-`--json` path prints |

**R1 is the most important test in the suite.** If leaf merging breaks, an agent
overriding `guardrails.output_validation` would silently wipe `input_filtering`
and every other sibling — a security-relevant failure that produces no error.

**R2 is its mirror.** The baseline grants five capabilities and the override
names one. If arrays merged instead of replacing, the agent would keep
`file.write` and `web.fetch` that nobody granted it.

```bash
export AGENT_TOOLKIT_HOME=/tmp/tk-test
mkdir -p /tmp/tk-test/agents/probe
cp builders/bootstrap-agent/bootstrap-agent-example.yaml /tmp/tk-test/baseline.yaml
cat > /tmp/tk-test/agents/probe/agent.yaml <<'EOF'
schema_version: 1
extends: "/tmp/tk-test/baseline.yaml"
name: "probe"
description: "Test probe."
operating_constraints:
  guardrails:
    output_validation: true
EOF

python3 builders/create-agent/scripts/resolve-config.py \
  /tmp/tk-test/agents/probe/agent.yaml --explain | grep -A4 guardrails
# output_validation -> agent (probe)
# input_filtering, tool_use_limits, human_in_the_loop -> baseline
```

### Scaffolding (`scaffold-agent.py`)

| # | Case | Expected |
|---|---|---|
| S1 | Minimal agent — name and description only | Files written, `validate-agent.py` passes with 0 warnings |
| S2 | Agent with two `--set` overrides | Both resolve correctly; validation passes |
| S3 | Target directory already exists | Refused without `--force`; `--force` overwrites |
| S4 | `--name` is not a valid slug | Refused; `errors[0].field == "name"` |
| S5 | `--dry-run` vs. a real run | Same file manifest and overrides; dry run writes nothing |
| S6 | `--force` over an agent with user content in it | `agent.yaml` rewritten; the process in `CLAUDE.md`, `steering.md` and everything in `output/` survives |
| S14 | `--merge` on an agent with other overrides | **Every override it was not asked about survives** |
| S15 | `--merge` on one guardrail | Its siblings survive — leaf merge, as the resolver does it |
| S16 | `--force` without `--merge` | Still replaces, which is right for re-creating from a fresh interview |
| S17 | `--merge` on an agent that does not exist | Behaves as a normal scaffold |
| S7 | `--no-web` | The **whole** inherited set minus the two web entries is written; `WebSearch` and `WebFetch` both denied |
| S8 | `--web` on a Cautious baseline | Adds only what is missing — `web.search` is already granted at every posture |
| S9 | A web flag that changes nothing | No override written at all |
| S10 | A web flag plus an explicit `--set` of `capabilities` | Refused |

**S14 is the edit trap.** `scaffold-agent.py` writes `agent.yaml` from the
flags it is given, so editing one field used to silently drop the rest: an
agent with a model override and a composed module, re-scaffolded for verbosity
alone, came back with neither. Harmless in the flow `--force` was built for,
where the interview supplies every answer fresh; data loss the moment anything
calls itself an edit. `--merge` starts from the existing overrides. S16 keeps
the old behaviour honest rather than quietly changing it.

**S7 is the array-replace trap.** `capabilities` replaces the inherited list
wholesale, so `--no-web` cannot be expressed as a delta. Writing only the web
entries would leave an agent with *no file access*, which nobody asked for.
The expansion belongs in the script for exactly that reason.

**S9 is D3 in miniature.** `--web` on a baseline that already grants both would
write an override identical to what it inherits, pinning the field against
future baseline edits. The flag is honoured by writing nothing.

**S6 is the agent-directory ownership rule, enforced.** `--force` used to
`rmtree` the directory, so re-scaffolding destroyed the process the user had
written, their steering notes, and every result in `output/`. Only `agent.yaml`
is the toolkit's to rewrite; see `docs/architecture.md`, "Who owns what".

**S5 is the one that matters for D19.** A form-only caller previews the exact
manifest a real run will produce before committing to it, with no model call
anywhere in the path.

Unlike the other scripts, `scaffold-agent.py` emits the cli_output envelope
unconditionally — there is no plain-text mode, since it exists to be called by
a builder or a future front-end, not read directly. It always writes
`agent.yaml` itself rather than copying the one in `templates/agent/`, which
carries only commented examples for a human editing by hand; every other
template file is copied with `{{AGENT_NAME}}` and `{{AGENT_DESCRIPTION}}`
substituted. A validation failure surfaces through the same top-level `errors`
array as a pre-write failure (bad slug, existing directory) — `run_validation()`
calls `validate-agent.py --json` and folds its envelope straight into its own,
so a caller never has to reach into a nested result to see why `ok` is false.

### Agent validation (`validate-agent.py`)

| # | Case | Expected |
|---|---|---|
| A1 | Clean minimal override | valid, 0 warnings |
| A2 | Override restates the baseline value | **WARN** — pins the field against baseline drift |
| A3 | `name` not a valid slug | ERROR with the rule |
| A4 | Missing `extends` | ERROR |
| A5 | Illegal enum in an override | ERROR listing the legal set |
| A6 | Cyclic `extends` | ERROR from the resolution layer |
| A7 | Literal secret | ERROR (credentials) or WARN (elsewhere) |
| A8 | Missing `description` | WARN only |

**A2 is the subtle one.** A redundant override is not harmless duplication — it
silently stops that field tracking baseline edits. The warning is the only thing
that surfaces it.

### Permissions (`render-agent.py`)

| # | Case | Expected |
|---|---|---|
| W1 | A Balanced baseline | `WebSearch` and `WebFetch` both in `allow` — D12 made real |
| W2 | Every capability granted | Each maps to its tools from `runtimes/claude-code.yaml` |
| W3 | `shell` withheld | `Bash` in **deny**, not merely absent from `allow` |
| W4 | `file.write` granted, `filesystem: read_only` | `Write`/`Edit`/`NotebookEdit` denied anyway |
| W5 | Any config | `allow` and `deny` never overlap |
| W6 | Rendering twice | Byte-identical; `.agent/render.json` carries the config hash, no timestamp |
| W7 | `--path` into a project that already has `.claude/settings.json` | The project's file is untouched; the agent gets its own one level down |
| W8 | A capability with no runtime mapping | ERROR naming the known set |
| W9-W10 | Scaffolding | Writes `.claude/settings.json` and reports the permissions; `--dry-run` predicts the generated files too |

**W3 and W4 are the pair that matter.** An un-allowed tool prompts the user,
and a prompt at the wrong moment gets answered yes; a denied tool cannot run.
So a capability that was deliberately withheld is denied outright. And
`file.write` under `filesystem: read_only` is a contradiction — the safe
reading of a contradiction is the restrictive one, so the denial wins and the
tool is dropped from `allow` rather than appearing in both lists.

**W7 protects someone else's repository.** `--path` scaffolds into a project
that may already be a Claude Code workspace. Its `.claude/settings.json` is
the user's; the agent gets its own, one directory down.

`verify-toolkit.sh` additionally asserts that every capability in the schema
has a mapping in every runtime file — an unmapped capability renders to no
tool at all, so the agent silently loses access it was granted.

### The generated region and staleness (`render-agent.py`, `agent-status.py`)

| # | Case | Expected |
|---|---|---|
| G1 | A default baseline | Domain, audience, locale, tone, verbosity, format and output location all reach the region |
| G2 | Region size | Within the 80-line target |
| G3 | Hand-written content outside the markers | Survives a re-render byte for byte |
| G4 | A guardrail at its schema default | Renders nothing; the same guardrail flipped renders a line |
| G5 | `web.fetch` withheld | The limits section says so |
| G6 | Two different baselines | Visibly different regions |
| G7 | `--stdout --json` | Every section in the structure appears in the markdown, and names its source fields |
| G8 | Only one of the two markers | Refused rather than guessed at |
| T1 | An empty agents directory | Exits 0 with a clear message |
| T2 | Editing the baseline's verbosity | Every agent that did **not** override it reports stale |
| T3 | The same edit, for an agent that **did** override it | Not stale — its resolved config genuinely did not change |
| T4 | Re-rendering | Clears staleness |
| T5 | `--check` | Exits non-zero on a stale agent, zero on a fresh one |
| T6-T7 | The status report | Names what each agent pins, and whether its intent was ever written |

**G3 is what makes the renderer usable twice.** `CLAUDE.md` is the only
artefact that reaches the model, and everything outside the markers is the
user's. A renderer that cannot be trusted with the rest of the file is one
nobody runs a second time.

**T2 and T3 are the pair that reconcile rendering with D2.** Agents read their
baseline at runtime, but `CLAUDE.md` is rendered once, so a baseline edit
reaches an agent's config immediately and its rendered instructions not at all.
T3 is the more convincing half: staleness follows what an agent *resolves to*,
not whether the baseline file was touched, so an agent that already pinned the
edited field is correctly reported fresh.

**One renderer, not two.** `render-agent.py` writes `CLAUDE.md` and
`.claude/settings.json` in a single pass and there is deliberately no flag to
render one without the other. They share a config hash; a half-rendered agent
would carry two records of what it was built from and no way to say which is
right.

### Semantic checks (`scripts/semantic_checks.py`)

Structural validation asks "is this field legal?". These ask "do these fields
make sense *together*?" — the questions a schema cannot express.

| # | Case | Expected |
|---|---|---|
| N1 | A coherent config | Nothing at all |
| N2 | **Each of the three shipped risk postures** | No errors — a check that fails the toolkit's own defaults is broken, not strict |
| N3 | Full filesystem + shell + no human gate | **WARN**, never ERROR — this is the Autonomous posture |
| N4 | `evaluator-optimizer` with the loop off | ERROR — the pattern and the config say opposite things |
| N5 | A loop enabled with no reviewer | ERROR |
| N6 | A looping pattern on a single-pass budget | WARN; standalone on the same budget does not |
| N7 | A `default_context_sources` path that is not there | WARN, and skipped entirely for a profile, which has no directory to resolve against |
| N8 | Composition against capability | The 6.4 checks, moved here so every semantic check lives in one place |

**N2 is the guard on the whole file.** The severity line is narrow: an error
means two fields contradict each other, a warning means the combination is
coherent but worth a second look. The Autonomous posture is deliberately
unsupervised, so a check that errored on it would fail the toolkit's own
defaults — and the fix would be to weaken the check, which is how a validator
becomes noise people learn to ignore.

Judgment no rule can express — tone against audience, whether the process
matches the description — belongs to `/validate-agent`, not here.

### The module library (`scripts/module_utils.py`, `library/`)

| # | Case | Expected |
|---|---|---|
| L1 | A module with no frontmatter | ERROR naming the file |
| L2 | A missing required field | ERROR naming the field |
| L3 | `kind` disagreeing with the directory | ERROR — `compose` addresses modules by both |
| L4 | A name in neither library | ERROR naming **both** search paths |
| L5 | A user module with a shipped module's name | The user's wins, and the shadowing is reported |
| L6 | A body over 40 lines | WARN |
| L7-L9 | The nine shipped modules | All load and validate; every pattern has one `TODO:` step; `library/README.md` matches the files on disk |
| L10 | An agent composing `routine/web-research` | The guidance is inline in its generated region; removing the entry removes it |
| L11 | An agent composing nothing | No "Composed modules" heading |
| L12 | Composing a module whose capabilities are not granted | **ERROR naming the module, the capability and the fix** |
| L13 | Five composed modules | WARN, still valid |
| L14 | Composing a `pattern/` | Rejected, pointing at `operating_constraints.pattern` |

**L12 is what the section was built for.** A research agent with no web access
is the failure this toolkit used to produce in silence, discovered at run time.
A module the agent cannot run is worse than an absent one, because the agent
has been told to do something it cannot do.

**L5 is the quiet one.** A personal module shadowing a shipped one is the point
— it is what stops `git pull` overwriting your guidance — but a shadow nobody
reports is a miserable thing to debug, so the loader records it.

**L9 keeps the index honest.** `library/README.md` is documentation that goes
stale the moment someone adds a module, so the test asserts it against disk in
both directions: nothing on disk missing from the index, nothing in the index
missing from disk.

### Seeding the process (`library/pattern/`)

| # | Case | Expected |
|---|---|---|
| S11 | A scaffolded standalone agent | Four numbered steps, exactly one marked `TODO:` |
| S12 | An `evaluator-optimizer` agent | A different skeleton, with `max_cycles` substituted |
| S13 | Validation | Warns while the `TODO:` step is present, and stops once it is replaced |

The original call — that `/create-agent` scaffolds structure, not intent — was
half right, and S11 is where the other half lands. "Confirm the inputs" and
"check the result against the constraints" are properties of the *pattern*, so
the toolkit can write them. What the agent actually does is the user's, stays
marked `TODO:`, and is a reportable state until someone writes it.

### Migration (`migrate-config.py`)

| # | Case | Expected |
|---|---|---|
| M1 | A v1 profile | `detect-profile` reports `STALE` |
| M2 | Migrating it | Produces a profile that passes `validate-profile.py` at v2 |
| M3 | Every field the bump does not touch | **Survives unchanged**, including a value whose *default* changed in v2 |
| M4 | Each v1 `tools` value | `read`→`file.read`, `write`→`file.read`+`file.write`, `search`→`file.search` |
| M5 | `external_calls: false` | Grants `web.search`, and **says so** in `notes`; `web.fetch` stays withheld |
| M6 | `external_calls: true` | Grants both web capabilities |
| M7 | The backup | `baseline.yaml.bak-1`, byte-identical to the original |
| M8 | A second migration run | Refused — the backup is the only copy of the pre-migration profile |
| M9 | `--dry-run` | Reports the whole migration and writes nothing |
| M10 | A v1 `tools` entry with no v2 equivalent | WARN naming it, rather than dropping it silently |
| M11 | An already-current profile | Left alone; no backup written |
| M12 | A profile newer than the toolkit | ERROR saying the toolkit is out of date, not the profile |
| M13 | A v1 `agent.yaml` | Migrates with its overrides intact, backup written |
| M14 | Validating a v1 agent | Says it needs **migrating, not repairing**, and names the command |

**M3 is the one that matters.** A migration that rebuilds the profile from the
fields it knows about passes every other case here and still quietly discards
whatever it was not told about. `migrate-config.py` deep-copies the user's
document and changes only what the version bump requires, and M3 is what holds
it to that.

**M5 is the honesty case.** Migrating from v1 *grants* read-only web search the
profile previously withheld, because v2 splits `external_calls` and D12 puts
`web.search` at every posture. Expanding what someone's agents may do, during a
command they ran for another reason, has to be stated rather than folded into
the change list.

Values survive a migration; **comments do not**. Round-tripping through pyyaml
drops them, and preserving them would mean a round-trip YAML library the
toolkit does not otherwise need. The script says so, and the backup keeps them.

### The interview descriptor (`scripts/describe-schema.py`)

| # | Case | Expected |
|---|---|---|
| X1 | Every leaf in the schema | Appears exactly once in `fields`, with a `source` of `question`, `composite`, `inferred`, or `default` |
| X2 | The shipped schema | Descriptor is coherent: `ok: true`, no errors |
| X3 | Express reconciliation | 6 characteristics marked Express, 5 questions asked — risk posture covers two of them |
| X4 | Composite answers | Every value one sets is legal for the field it sets |
| X5 | An inferred field (`locale`) | `source: inferred`, never asked, not in the Express set |
| X6 | A field with no `x-question`, no `x-infer` and no `default` | **Reported as an error**, naming the field |
| X7 | A composite setting a field not in the schema | ERROR naming the field |
| X8 | A composite setting an illegal enum value | ERROR listing the legal set |
| X9 | The builder README's characteristics list | Byte-identical to `--markdown` output |

**X6 is the check the item was written around.** A field that is neither
inferred, nor defaulted, nor asked in Express cannot be filled by an Express
run. Finding it at descriptor level is the difference between a caught schema
edit and a profile silently missing a value. `verify-toolkit.sh` runs the same
check as a pre-flight.

**X3 is the reconciliation itself.** The builder README used to mark six
characteristics `[E]` while the process file asked five questions, with nothing
stating why. The descriptor now says it: guardrails and permissions_scope both
carry `x-express-via: risk_posture`, so one composite question answers both.

X9 is a drift check. The README's characteristics list is generated —
regenerate with `python3 scripts/describe-schema.py --write` after any schema
edit, or that test fails.

### The JSON envelope (`scripts/cli_output.py`)

Per D16, every script above that a front-end could call takes `--json` and
emits one envelope — `ok`, `errors`, `warnings`, `data` — instead of its own
shape. `detect-profile.sh` is the exception worth naming: its `--json` wraps
the state (`data.state`) with `errors`/`warnings` always empty, since it
reports a state rather than itemized diagnostics; `validate-profile.py --json`
is where those diagnostics actually live. Plain-text output is byte-for-byte
unchanged when `--json` is absent everywhere except `scaffold-agent.py`,
which has no plain-text mode at all (see above).

| # | Case | Expected |
|---|---|---|
| C1 | Any script, a success case, `--json` | Validates against the envelope; `ok: true`, `errors: []` |
| C2 | Any script, a failure case, `--json` | `ok: false`; each entry in `errors` carries `field`, `message`, `legal`, `fix` — `legal` populated whenever `field` is an enum |
| C3 | `detect-profile.sh --json` in a non-`VALID` state | `ok: false` with `errors: []` — the documented exception to C2 |

Tested once per script in `test_cli_output.py`, rather than repeated in each
script's own test file — a script's own tests still cover its plain-text
output and domain-specific behaviour.

## Automated harness

```bash
cd agent-toolkit
python3 -m unittest discover -s tests -v     # `python` or `py -3` on Windows
```

On Windows, `python3` is often the Microsoft Store stub rather than an
interpreter — see `getting-started.md`, "On Windows". The suite itself is
platform-agnostic: it runs every script through `sys.executable`, so whichever
interpreter starts it is the one under test.

Plain `unittest` — no `pytest` dependency, consistent with the rest of the
toolkit's no-install-step approach. 152 tests, covering D1-D12, P1-P12, A1-A8,
R1-R10, S1-S17, W1-W10, G1-G8, T1-T7, L1-L14, M1-M14, N1-N8, C1-C3, X1-X9
(plus four unit tests on `cli_output.py` itself), and two schema-drift checks
— one for scalar enums, one for the capability vocabulary, which lives in an
array and so needs its own.

The suite passes on Windows and Linux. Paths substituted into fixtures go
through `base.as_yaml_path()` first: a native Windows path inside a
double-quoted YAML scalar makes `\U` an escape sequence, and the fixture fails
to parse in a way that looks like a resolver bug.

```
tests/
├── base.py                        # ToolkitTestCase: isolates $AGENT_TOOLKIT_HOME
│                                   # per test, wraps subprocess calls to each script
├── fixtures/
│   ├── baseline-valid.yaml        # + stale / malformed / invalid-enum / newer-schema
│   │                                / missing-field / incoherent-loop / literal-secret
│   │                                / budget-out-of-range variants
│   └── agent-minimal.yaml         # + redundant-override / bad-slug / missing-extends
│                                     / illegal-enum / cyclic / literal-secret
│                                     / missing-description / nested-override
│                                     / array-override variants
├── test_detect.py                 # D1-D9
├── test_validate_profile.py       # P1-P12
├── test_validate_agent.py         # A1-A8
├── test_resolve.py                # R1-R10
├── test_scaffold.py               # S1-S17, no fixtures of its own
├── test_cli_output.py             # C1-C3, one success + one failure per script,
│                                     plus unit tests on scripts/cli_output.py
├── test_describe_schema.py        # X1-X9, no fixtures of its own — mutates a
│                                     copy of the real schema to force each error
├── test_render.py                 # W1-W10 permissions, G1-G8 generated region
├── test_agent_status.py           # T1-T7, staleness against a baseline edit
├── test_modules.py                # L1-L14, format, library, composition
├── test_semantic_checks.py        # N1-N8, unit tests on the shared module
├── test_migrate_config.py        # M1-M12, drives the v1 fixture forward
└── test_schema_sync.py            # asserts both schemas' enums agree
```

Each real script (`detect-profile.sh`, `validate-profile.py`,
`validate-agent.py`, `resolve-config.py`) is exercised as a subprocess, the
same way the builders invoke it — these are integration tests over the actual
CLI surface, not unit tests over internal functions. `ToolkitTestCase`
isolates `$AGENT_TOOLKIT_HOME` to a fresh tmpdir per test and asserts on exit
codes as well as stdout — `detect-profile.sh` deliberately always exits 0, so
`test_detect.py` checks stdout for the state and the exit code separately, to
catch a regression that starts using exit codes for state.

Fixtures that need to reference a path only known at test time — `extends:
"{{BASELINE}}"`, a self-referencing `extends: "{{SELF}}"` for the cycle test —
use a `{{PLACEHOLDER}}` token; `base.load_fixture()` substitutes it after the
fixture is copied into the test's tmpdir.

**Not yet automated:** round-tripping the `/bootstrap-profile` and
`/create-agent` interviews — they need to be drivable non-interactively first.
Until then, exercise them by hand per the smoke test below.

## Manual smoke test

End to end, on a clean machine:

```bash
git clone <repo> && cd agent-toolkit
pip install pyyaml jsonschema
bash scripts/verify-toolkit.sh          # expect 2 warnings, exit 0
claude
```

```
/bootstrap-profile express               # answer 5 questions, accept
/create-agent smoke-test                 # accept defaults, add a description
```

```bash
bash scripts/verify-toolkit.sh           # baseline warning now gone
python3 builders/create-agent/scripts/resolve-config.py \
  ~/.agent-toolkit/agents/smoke-test/agent.yaml --explain
```

Confirm: the profile exists at `~/.agent-toolkit/baseline.yaml`, the agent exists
at `~/.agent-toolkit/agents/smoke-test/`, **nothing was written inside the repo**,
and the resolved config shows the right provenance.

That last check matters — a `git status` showing new files in the repo means the
destination logic is broken.
