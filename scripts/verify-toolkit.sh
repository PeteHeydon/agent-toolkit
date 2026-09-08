#!/usr/bin/env bash
# verify-toolkit.sh
# Checks the toolkit is correctly in place before you start using it.
# Run from the repo root:  bash scripts/verify-toolkit.sh
#
# Exit 0 = everything checks out. Exit 1 = something needs attention.

set -uo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { printf "  \033[32mPASS\033[0m  %s\n" "$1"; PASS=$((PASS+1)); }
bad()  { printf "  \033[31mFAIL\033[0m  %s\n" "$1"; FAIL=$((FAIL+1)); }
warn() { printf "  \033[33mWARN\033[0m  %s\n" "$1"; WARN=$((WARN+1)); }

hdr()  { printf "\n\033[1m%s\033[0m\n" "$1"; }

# --- 0. Are we in the right place? ------------------------------------------
hdr "Location"
if [[ -d builders && -d .claude/commands ]]; then
  ok "running from the agent-toolkit repo root"
else
  bad "not in the repo root — cd into agent-toolkit/ and re-run"
  echo ""
  echo "Aborting: nothing else can be checked from here."
  exit 1
fi

# --- 1. Required files ------------------------------------------------------
hdr "Files"
REQUIRED_FILES=(
  "README.md"
  ".gitignore"
  ".env.example"
  ".claude/commands/bootstrap-profile.md"
  ".claude/commands/create-agent.md"
  "builders/bootstrap-agent/CLAUDE.md"
  "builders/bootstrap-agent/README.md"
  "builders/bootstrap-agent/bootstrap-agent-example.yaml"
  "builders/bootstrap-agent/schema/baseline-profile.schema.json"
  "builders/bootstrap-agent/scripts/detect-profile.sh"
  "builders/bootstrap-agent/scripts/validate-profile.py"
  "builders/create-agent/CLAUDE.md"
  "builders/create-agent/README.md"
  "builders/create-agent/agent-example.yaml"
  "builders/create-agent/schema/agent-override.schema.json"
  "builders/create-agent/scripts/resolve-config.py"
  "builders/create-agent/scripts/validate-agent.py"
  "templates/agent/agent.yaml"
  "templates/agent/CLAUDE.md"
  "templates/agent/README.md"
  "docs/repository-structure.md"
  "docs/precedence-and-inheritance.md"
  "docs/environment-variables.md"
)
MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
  [[ -f "$f" ]] || { bad "missing: $f"; MISSING=$((MISSING+1)); }
done
[[ $MISSING -eq 0 ]] && ok "all ${#REQUIRED_FILES[@]} required files present"

# --- 2. Dependencies --------------------------------------------------------
hdr "Dependencies"
if command -v python3 >/dev/null 2>&1; then
  ok "python3 ($(python3 --version 2>&1 | cut -d' ' -f2))"
else
  bad "python3 not found — required by the validators and resolver"
fi

if python3 -c "import yaml" 2>/dev/null; then
  ok "pyyaml installed"
else
  bad "pyyaml missing — run: pip install pyyaml"
fi

if python3 -c "import jsonschema" 2>/dev/null; then
  ok "jsonschema installed (optional, used by schema checks)"
else
  warn "jsonschema missing — optional. For schema conformance checks: pip install jsonschema"
fi

# --- 3. Schemas and examples parse -----------------------------------------
hdr "Schemas and examples"
python3 - <<'PYEOF'
import json, sys, yaml

checks = [
    ("builders/bootstrap-agent/schema/baseline-profile.schema.json", "json"),
    ("builders/create-agent/schema/agent-override.schema.json", "json"),
    ("builders/bootstrap-agent/bootstrap-agent-example.yaml", "yaml"),
    ("builders/create-agent/agent-example.yaml", "yaml"),
    ("templates/agent/agent.yaml", "yaml"),
]
failed = False
for path, kind in checks:
    try:
        with open(path) as fh:
            json.load(fh) if kind == "json" else yaml.safe_load(fh)
        print("  \033[32mPASS\033[0m  parses: %s" % path)
    except Exception as exc:
        print("  \033[31mFAIL\033[0m  %s: %s" % (path, exc))
        failed = True

try:
    import jsonschema
    pairs = [
        ("builders/bootstrap-agent/schema/baseline-profile.schema.json",
         "builders/bootstrap-agent/bootstrap-agent-example.yaml"),
        ("builders/create-agent/schema/agent-override.schema.json",
         "builders/create-agent/agent-example.yaml"),
        ("builders/create-agent/schema/agent-override.schema.json",
         "templates/agent/agent.yaml"),
    ]
    for schema_path, doc_path in pairs:
        jsonschema.validate(yaml.safe_load(open(doc_path)), json.load(open(schema_path)))
        print("  \033[32mPASS\033[0m  %s conforms to its schema" % doc_path)
except ImportError:
    print("  \033[33mWARN\033[0m  jsonschema not installed — conformance not checked")
except Exception as exc:
    print("  \033[31mFAIL\033[0m  schema conformance: %s" % exc)
    failed = True

sys.exit(1 if failed else 0)
PYEOF
if [[ $? -eq 0 ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi

# --- 3b. Schema drift: enums shared by both schemas must agree -------------
# The baseline and agent-override schemas define their enums independently
# (an override must obey the same legal values as the baseline). Nothing
# stops them drifting apart by hand-editing one and not the other, so assert
# it here. See HANDOFF.md, "Known gaps" #1.
python3 - <<'PYEOF'
import sys
sys.path.insert(0, "scripts")
import schema_utils

baseline = schema_utils.load_schema("builders/bootstrap-agent/schema/baseline-profile.schema.json")
override = schema_utils.load_schema("builders/create-agent/schema/agent-override.schema.json")

baseline_enums = schema_utils.extract_enums(baseline)
override_enums = schema_utils.extract_enums(override)

shared = set(baseline_enums) & set(override_enums)
mismatched = [p for p in shared if baseline_enums[p] != override_enums[p]]

if mismatched:
    for p in mismatched:
        print("  \033[31mFAIL\033[0m  %s: baseline has %s, override has %s"
              % (p, sorted(baseline_enums[p]), sorted(override_enums[p])))
    sys.exit(1)

print("  \033[32mPASS\033[0m  %d shared enum field(s) agree between both schemas" % len(shared))
sys.exit(0)
PYEOF
if [[ $? -eq 0 ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi

# --- 4. Scripts execute -----------------------------------------------------
hdr "Scripts"
if bash -n builders/bootstrap-agent/scripts/detect-profile.sh 2>/dev/null; then
  ok "detect-profile.sh syntax"
else
  bad "detect-profile.sh has a syntax error"
fi

for s in builders/bootstrap-agent/scripts/validate-profile.py \
         builders/create-agent/scripts/validate-agent.py \
         builders/create-agent/scripts/resolve-config.py; do
  if python3 -m py_compile "$s" 2>/dev/null; then
    ok "$(basename "$s") compiles"
  else
    bad "$(basename "$s") has a syntax error"
  fi
done
rm -rf builders/*/scripts/__pycache__ 2>/dev/null

# The example baseline must pass its own validator.
if python3 builders/bootstrap-agent/scripts/validate-profile.py \
     builders/bootstrap-agent/bootstrap-agent-example.yaml >/dev/null 2>&1; then
  ok "example baseline passes validate-profile.py"
else
  bad "example baseline FAILS its own validator"
fi

# --- 5. Round-trip: resolver produces a correct merge -----------------------
hdr "Resolver round-trip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp builders/bootstrap-agent/bootstrap-agent-example.yaml "$TMP/baseline.yaml"
mkdir -p "$TMP/agents/probe"
cat > "$TMP/agents/probe/agent.yaml" <<EOF
schema_version: 1
extends: "$TMP/baseline.yaml"
name: "probe"
description: "Verification probe."
operating_constraints:
  guardrails:
    output_validation: true
EOF

RESOLVED="$(python3 builders/create-agent/scripts/resolve-config.py "$TMP/agents/probe/agent.yaml" --json 2>/dev/null)"
if echo "$RESOLVED" | python3 -c "
import json,sys
d = json.load(sys.stdin)
r, p = d['resolved'], d['provenance']
g = r['operating_constraints']['guardrails']
assert g['output_validation'] is True, 'override did not win'
assert g['input_filtering'] is True, 'sibling key was wiped — leaf merge broken'
assert 'agent' in p['operating_constraints.guardrails.output_validation'], 'provenance wrong'
assert p['operating_constraints.guardrails.input_filtering'] == 'baseline', 'provenance wrong'
" 2>/dev/null; then
  ok "leaf-level merge: override wins, sibling keys survive, provenance correct"
else
  bad "resolver merge is not behaving correctly"
fi

if python3 builders/create-agent/scripts/validate-agent.py "$TMP/agents/probe/agent.yaml" >/dev/null 2>&1; then
  ok "probe agent passes validate-agent.py"
else
  bad "probe agent fails validation"
fi

# Cycle detection must trigger.
cat > "$TMP/agents/probe/cyclic.yaml" <<EOF
schema_version: 1
extends: "$TMP/agents/probe/cyclic.yaml"
name: "cyclic"
EOF
if python3 builders/create-agent/scripts/resolve-config.py "$TMP/agents/probe/cyclic.yaml" >/dev/null 2>&1; then
  bad "cyclic extends was NOT detected — this would hang or corrupt config"
else
  ok "cyclic extends detected and rejected"
fi

# --- 6. Environment ---------------------------------------------------------
hdr "Environment"
TOOLKIT_HOME="${AGENT_TOOLKIT_HOME:-$HOME/.agent-toolkit}"
echo "        AGENT_TOOLKIT_HOME -> $TOOLKIT_HOME"

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  ok "ANTHROPIC_API_KEY is set"
else
  warn "ANTHROPIC_API_KEY not set — see docs/environment-variables.md"
fi

if [[ -f "$TOOLKIT_HOME/baseline.yaml" ]]; then
  STATE="$(bash builders/bootstrap-agent/scripts/detect-profile.sh 2>/dev/null)"
  case "$STATE" in
    VALID) ok "baseline profile exists and is valid" ;;
    STALE) warn "baseline profile is stale — run: /bootstrap-profile migrate" ;;
    *)     bad "baseline profile state: $STATE — run: /bootstrap-profile" ;;
  esac
else
  warn "no baseline profile yet — this is expected on a fresh install."
  echo "        Next step: run /bootstrap-profile in Claude Code"
fi

# --- Summary ----------------------------------------------------------------
printf "\n\033[1mSummary\033[0m\n"
printf "  %d passed, %d failed, %d warnings\n\n" "$PASS" "$FAIL" "$WARN"

if [[ $FAIL -gt 0 ]]; then
  echo "Something needs attention before you start. See FAIL lines above."
  exit 1
fi
echo "Toolkit is in place."
exit 0
