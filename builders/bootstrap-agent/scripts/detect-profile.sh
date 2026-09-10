#!/usr/bin/env bash
# detect-profile.sh — find a working interpreter, then run detect-profile.py.
#
# The detection logic lives in the Python version (D15: Python is the platform
# floor). What is left here is the one job a Python script cannot do for
# itself: answer "is there a working interpreter at all".
#
# That job is not vestigial. On Windows `python3` is routinely the Microsoft
# Store stub, which prints an install prompt and exits without being an
# interpreter — the failure 2.6 was written to fix. Calling the .py directly
# from a machine nobody has checked turns that into an empty result and a
# confused user; calling this turns it into NO_PYTHON and a fix.
#
# Prints exactly one state to stdout and always exits 0 — the state IS the
# result. Diagnostics go to stderr.
#
# Usage:
#   detect-profile.sh [--json]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_HOME="${AGENT_TOOLKIT_HOME:-$HOME/.agent-toolkit}"
PROFILE="$TOOLKIT_HOME/baseline.yaml"

JSON_MODE=0
for arg in "$@"; do
  case "$arg" in
    --json) JSON_MODE=1 ;;
  esac
done

emit_no_python() {
  if [[ "$JSON_MODE" -eq 1 ]]; then
    printf '{\n  "ok": false,\n  "errors": [],\n  "warnings": [],\n  "data": {\n    "state": "NO_PYTHON"\n  }\n}\n'
  else
    echo "NO_PYTHON"
  fi
  exit 0
}

# Find an interpreter that actually RUNS, not just one that exists on PATH.
# $AGENT_TOOLKIT_PYTHON overrides the search, for a venv, a pyenv shim, or any
# setup where the right interpreter is not the first one found.
PY=""
CANDIDATES=("python3" "python" "py -3")
if [[ -n "${AGENT_TOOLKIT_PYTHON:-}" ]]; then
  CANDIDATES=("$AGENT_TOOLKIT_PYTHON")
fi

for candidate in "${CANDIDATES[@]}"; do
  if $candidate -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

if [[ -z "$PY" ]]; then
  {
    if [[ -n "${AGENT_TOOLKIT_PYTHON:-}" ]]; then
      echo "detect-profile: \$AGENT_TOOLKIT_PYTHON is set to '${AGENT_TOOLKIT_PYTHON}',"
      echo "  which did not run. Unset it to fall back to the normal search."
    else
      echo "detect-profile: no working Python interpreter found."
      echo "  Tried: python3, python, py -3"
    fi
    echo "  On Windows, 'python3' commonly resolves to the Microsoft Store stub,"
    echo "  which is not an interpreter. Install Python, disable the alias under"
    echo "  Settings > Apps > Advanced app settings > App execution aliases, or set"
    echo "  \$AGENT_TOOLKIT_PYTHON to the interpreter you want."
    echo "  The profile at $PROFILE has NOT been read."
  } >&2
  emit_no_python
fi

exec $PY "$SCRIPT_DIR/detect-profile.py" "$@"
