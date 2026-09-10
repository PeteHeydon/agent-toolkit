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
  ".claude/commands/list-agents.md"
  ".claude/commands/refresh-agent.md"
  ".claude/commands/edit-agent.md"
  ".claude/commands/review-agent.md"
  "builders/refinement-agent/CLAUDE.md"
  "builders/validation-agent/CLAUDE.md"
  ".claude/commands/validate-agent.md"
  "scripts/semantic_checks.py"
  "builders/bootstrap-agent/CLAUDE.md"
  "builders/bootstrap-agent/README.md"
  "builders/bootstrap-agent/bootstrap-agent-example.yaml"
  "builders/bootstrap-agent/schema/baseline-profile.schema.json"
  "builders/bootstrap-agent/scripts/detect-profile.py"
  "builders/bootstrap-agent/scripts/detect-profile.sh"
  "builders/bootstrap-agent/scripts/validate-profile.py"
  "builders/bootstrap-agent/scripts/migrate-config.py"
  "builders/create-agent/CLAUDE.md"
  "builders/create-agent/README.md"
  "builders/create-agent/agent-example.yaml"
  "builders/create-agent/schema/agent-override.schema.json"
  "builders/create-agent/scripts/resolve-config.py"
  "builders/create-agent/scripts/validate-agent.py"
  "builders/create-agent/scripts/scaffold-agent.py"
  "builders/create-agent/scripts/render-agent.py"
  "builders/create-agent/scripts/agent-status.py"
  "library/README.md"
  "library/pattern/standalone.md"
  "scripts/module_utils.py"
  "runtimes/claude-code.yaml"
  "scripts/describe-schema.py"
  "scripts/cli_output.py"
  "templates/agent/agent.yaml"
  "templates/agent/CLAUDE.md"
  "templates/agent/README.md"
  "templates/agent/steering.md"
  "templates/agent/run.sh"
  "templates/agent/run.ps1"
  "templates/agent/output/.gitkeep"
  "docs/architecture.md"
  "docs/decisions.md"
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

# Find an interpreter that actually RUNS, not just one that exists on PATH.
# On Windows `$PY` resolves to the Microsoft Store stub, which prints an
# install prompt and exits — so `command -v $PY` succeeds and every check
# downstream of it then fails, blaming the toolkit for a broken environment.
# $AGENT_TOOLKIT_PYTHON overrides the search, as in detect-profile.sh.
PY=""
PY_CANDIDATES=("python3" "python" "py -3")
if [[ -n "${AGENT_TOOLKIT_PYTHON:-}" ]]; then
  PY_CANDIDATES=("$AGENT_TOOLKIT_PYTHON")
fi
for candidate in "${PY_CANDIDATES[@]}"; do
  if $candidate -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

if [[ -n "$PY" ]]; then
  ok "python: $PY ($($PY --version 2>&1 | cut -d' ' -f2))"
else
  bad "no working Python interpreter (tried: python3, python, py -3)"
  echo ""
  echo "  On Windows, 'python3' is commonly the Microsoft Store stub rather than an"
  echo "  interpreter. Install Python, disable the alias under Settings > Apps >"
  echo "  Advanced app settings > App execution aliases, or set \$AGENT_TOOLKIT_PYTHON."
  echo ""
  echo "Aborting: every remaining check needs Python."
  exit 1
fi

if $PY -c "import yaml" 2>/dev/null; then
  ok "pyyaml installed"
else
  bad "pyyaml missing — run: pip install pyyaml"
fi

if $PY -c "import jsonschema" 2>/dev/null; then
  ok "jsonschema installed (optional, used by schema checks)"
else
  warn "jsonschema missing — optional. For schema conformance checks: pip install jsonschema"
fi

# --- 3. Schemas and examples parse -----------------------------------------
hdr "Schemas and examples"
$PY - <<'PYEOF'
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
$PY - <<'PYEOF'
import sys
sys.path.insert(0, "scripts")
import schema_utils

baseline = schema_utils.load_schema("builders/bootstrap-agent/schema/baseline-profile.schema.json")
override = schema_utils.load_schema("builders/create-agent/schema/agent-override.schema.json")

# Scalar enums and array-item enums both matter. `capabilities` is the second
# kind, and the one where drift grants access nobody defined.
baseline_enums = schema_utils.extract_enums(baseline)
override_enums = schema_utils.extract_enums(override)
baseline_enums.update(schema_utils.extract_array_enums(baseline))
override_enums.update(schema_utils.extract_array_enums(override))

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

# --- 3c. Every capability maps to a tool in every runtime ------------------
# A capability in the schema with no entry in a runtime file renders to no
# tool at all, so an agent silently loses access it was granted.
$PY - <<'INNEREOF'
import sys, glob, os
sys.path.insert(0, "scripts")
import schema_utils, yaml

schema = schema_utils.load_schema(
    "builders/bootstrap-agent/schema/baseline-profile.schema.json")
declared = schema_utils.extract_array_enums(schema).get(
    "operating_constraints.permissions_scope.capabilities", set())

failed = False
for path in sorted(glob.glob(os.path.join("runtimes", "*.yaml"))):
    with open(path, encoding="utf-8") as fh:
        runtime = yaml.safe_load(fh) or {}
    mapped = set(runtime.get("capabilities") or {})
    missing = declared - mapped
    extra = mapped - declared
    if missing or extra:
        failed = True
        if missing:
            print("  [31mFAIL[0m  %s: no mapping for %s"
                  % (path, ", ".join(sorted(missing))))
        if extra:
            print("  [31mFAIL[0m  %s: maps %s, which the schema does not define"
                  % (path, ", ".join(sorted(extra))))
    else:
        print("  [32mPASS[0m  %s maps all %d capabilities"
              % (path, len(declared)))

sys.exit(1 if failed else 0)
INNEREOF
if [[ $? -eq 0 ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi

# --- 3d. Every pattern has a process skeleton to seed from -----------------
# A pattern with no file in library/pattern/ falls back to standalone, which
# is safe but silent: the agent gets steps that do not match how it works.
# Informational rather than fatal, so exit 3 means "some missing".
SKELETONS="$($PY - <<'INNEREOF'
import sys, os
sys.path.insert(0, "scripts")
import schema_utils

schema = schema_utils.load_schema(
    "builders/bootstrap-agent/schema/baseline-profile.schema.json")
patterns = schema_utils.extract_enums(schema).get("operating_constraints.pattern", set())
missing = sorted(p for p in patterns
                 if not os.path.isfile(os.path.join("library", "pattern", p + ".md")))

if missing:
    print("no process skeleton for: %s (they fall back to standalone.md)"
          % ", ".join(missing))
    sys.exit(3)

print("all %d patterns have a process skeleton" % len(patterns))
sys.exit(0)
INNEREOF
)"
case $? in
  0) ok "$SKELETONS" ;;
  3) warn "$SKELETONS" ;;
  *) bad "could not check pattern skeletons" ;;
esac

# --- 3e. Every shipped module loads and validates --------------------------
# A module that fails to load is not merely absent: an agent composing it
# fails at render time, having been configured to use guidance it never got.
MODULES="$($PY - <<'INNEREOF'
import sys
sys.path.insert(0, "scripts")
import module_utils

modules, problems = module_utils.list_modules()
if problems:
    for p in problems:
        print("%s: %s" % (p.path, p))
    sys.exit(1)

overlong = [m["id"] for m in modules if m["warnings"]]
if overlong:
    print("over the 40-line body limit: %s" % ", ".join(overlong))
    sys.exit(3)

print("all %d library modules load and validate" % len(modules))
sys.exit(0)
INNEREOF
)"
case $? in
  0) ok "$MODULES" ;;
  3) warn "$MODULES" ;;
  *) bad "a library module failed to load: $MODULES" ;;
esac

# --- 4. Scripts execute -----------------------------------------------------
hdr "Scripts"
if bash -n builders/bootstrap-agent/scripts/detect-profile.sh 2>/dev/null; then
  ok "detect-profile.sh syntax"
else
  bad "detect-profile.sh has a syntax error"
fi

for s in builders/bootstrap-agent/scripts/validate-profile.py \
         builders/bootstrap-agent/scripts/detect-profile.py \
         builders/bootstrap-agent/scripts/migrate-config.py \
         builders/create-agent/scripts/validate-agent.py \
         builders/create-agent/scripts/resolve-config.py \
         builders/create-agent/scripts/scaffold-agent.py \
         builders/create-agent/scripts/render-agent.py \
         builders/create-agent/scripts/agent-status.py \
         scripts/describe-schema.py \
         scripts/module_utils.py \
         scripts/semantic_checks.py \
         scripts/cli_output.py; do
  if $PY -m py_compile "$s" 2>/dev/null; then
    ok "$(basename "$s") compiles"
  else
    bad "$(basename "$s") has a syntax error"
  fi
done
rm -rf builders/*/scripts/__pycache__ 2>/dev/null

# The example baseline must pass its own validator.
if $PY builders/bootstrap-agent/scripts/validate-profile.py \
     builders/bootstrap-agent/bootstrap-agent-example.yaml >/dev/null 2>&1; then
  ok "example baseline passes validate-profile.py"
else
  bad "example baseline FAILS its own validator"
fi

# Every leaf field must be askable, inferrable, or defaulted — otherwise an
# Express run leaves it unset. describe-schema.py exits 1 if any isn't.
if $PY scripts/describe-schema.py >/dev/null 2>&1; then
  ok "every schema field is asked, inferred, or defaulted"
else
  bad "the interview descriptor is incoherent — run: $PY scripts/describe-schema.py"
fi

# --- 5. Round-trip: resolver produces a correct merge -----------------------
hdr "Resolver round-trip"

# Paths written INTO a YAML file have to be readable by the Python resolver,
# which is a native process. Under Git Bash on Windows the shell's /tmp is not
# a path Python can open, and a native C:\... path inside a double-quoted YAML
# scalar makes \U an escape sequence. cygpath -m gives C:/... — native, and
# forward-slashed, so it is safe in YAML. On Linux this is a no-op.
to_yaml_path() {
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -m "$1"
  else
    printf '%s' "$1"
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
TMP_YAML="$(to_yaml_path "$TMP")"
cp builders/bootstrap-agent/bootstrap-agent-example.yaml "$TMP/baseline.yaml"
mkdir -p "$TMP/agents/probe"
cat > "$TMP/agents/probe/agent.yaml" <<EOF
schema_version: 2
extends: "$TMP_YAML/baseline.yaml"
name: "probe"
description: "Verification probe."
operating_constraints:
  guardrails:
    output_validation: true
EOF

RESOLVED="$($PY builders/create-agent/scripts/resolve-config.py "$TMP/agents/probe/agent.yaml" --json 2>/dev/null)"
if echo "$RESOLVED" | $PY -c "
import json,sys
d = json.load(sys.stdin)['data']
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

if $PY builders/create-agent/scripts/validate-agent.py "$TMP/agents/probe/agent.yaml" >/dev/null 2>&1; then
  ok "probe agent passes validate-agent.py"
else
  bad "probe agent fails validation"
fi

# Cycle detection must trigger.
cat > "$TMP/agents/probe/cyclic.yaml" <<EOF
schema_version: 2
extends: "$TMP_YAML/agents/probe/cyclic.yaml"
name: "cyclic"
EOF
if $PY builders/create-agent/scripts/resolve-config.py "$TMP/agents/probe/cyclic.yaml" >/dev/null 2>&1; then
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
