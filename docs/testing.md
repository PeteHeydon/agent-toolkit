# Testing

## Pre-flight check

```bash
cd agent-toolkit
bash scripts/verify-toolkit.sh
```

Covers: required files present, dependencies installed, schemas and examples
parse and conform, schema-enum drift, scripts compile, and a resolver
round-trip asserting leaf-level merge, provenance correctness, and cycle
rejection.

Exit 0 means clean. Run it after any change to a script, schema, or required
file — it's the "is the toolkit even in place" check, distinct from the
behavioural test suite below.

## Manual test cases

These were exercised during development. They are the intended fixtures for the
automated harness — each one is a real behaviour that would break silently.

### Profile detection (`detect-profile.sh`)

| # | Setup | Expected |
|---|---|---|
| D1 | No file at `$AGENT_TOOLKIT_HOME/baseline.yaml` | `NONE` |
| D2 | Valid current profile | `VALID` |
| D3 | `schema_version` lower than current | `STALE` |
| D4 | Illegal enum value present | `INVALID` |
| D5 | Malformed YAML | `UNREADABLE` |
| D6 | `schema_version` *higher* than current | `INVALID` + "update the toolkit" |

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
| R9 | `--json` | Parseable, contains `resolved`, `provenance`, `chain` |

**R1 is the most important test in the suite.** If leaf merging breaks, an agent
overriding `guardrails.output_validation` would silently wipe `input_filtering`
and every other sibling — a security-relevant failure that produces no error.

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

## Automated harness

```bash
cd agent-toolkit
python3 -m unittest discover -s tests -v
```

Plain `unittest` — no `pytest` dependency, consistent with the rest of the
toolkit's no-install-step approach. 30 tests, covering D1-D6, P1-P6, A1-A8,
R1-R9, plus a schema-drift check.

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
├── test_detect.py                 # D1-D6
├── test_validate_profile.py       # P1-P6
├── test_validate_agent.py         # A1-A8
├── test_resolve.py                # R1-R9
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
