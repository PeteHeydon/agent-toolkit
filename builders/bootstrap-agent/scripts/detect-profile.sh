#!/usr/bin/env bash
# detect-profile.sh — report the state of the user's baseline profile.
#
# Prints exactly one state to stdout and always exits 0 — the state IS the
# result, callers branch on stdout, not on the exit code.
#
# States:
#   NONE        no file at $AGENT_TOOLKIT_HOME/baseline.yaml
#   VALID       file parses, schema_version matches, passes validate-profile.py
#   STALE       file parses, schema_version is older than current
#   INVALID     file parses, current schema_version, but fails validation
#               (this also covers a schema_version NEWER than current — the
#               toolkit itself is out of date, not the profile)
#   UNREADABLE  file exists but is not parseable YAML
#
# Usage:
#   detect-profile.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_HOME="${AGENT_TOOLKIT_HOME:-$HOME/.agent-toolkit}"
PROFILE="$TOOLKIT_HOME/baseline.yaml"
CURRENT_SCHEMA_VERSION=1

if [[ ! -f "$PROFILE" ]]; then
  echo "NONE"
  exit 0
fi

VERSION="$(python3 - "$PROFILE" <<'PYEOF' 2>/dev/null
import sys
import yaml

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
except yaml.YAMLError:
    print("__UNREADABLE__")
    sys.exit(0)

if not isinstance(data, dict):
    print("__UNREADABLE__")
    sys.exit(0)

print(data.get("schema_version", "__MISSING__"))
PYEOF
)"

if [[ -z "$VERSION" || "$VERSION" == "__UNREADABLE__" ]]; then
  echo "UNREADABLE"
  exit 0
fi

if [[ "$VERSION" == "__MISSING__" ]]; then
  echo "INVALID"
  exit 0
fi

if [[ "$VERSION" -lt "$CURRENT_SCHEMA_VERSION" ]] 2>/dev/null; then
  echo "STALE"
  exit 0
fi

if [[ "$VERSION" -gt "$CURRENT_SCHEMA_VERSION" ]] 2>/dev/null; then
  echo "INVALID"
  exit 0
fi

if python3 "$SCRIPT_DIR/validate-profile.py" "$PROFILE" >/dev/null 2>&1; then
  echo "VALID"
else
  echo "INVALID"
fi
exit 0
