#!/usr/bin/env python3
"""
detect-profile.py — report the state of the user's baseline profile.

Prints exactly one state to stdout and always exits 0. The state IS the
result; callers branch on stdout, not on the exit code. Diagnostics go to
stderr.

States:
  NONE        no file at $AGENT_TOOLKIT_HOME/baseline.yaml
  VALID       parses, schema_version matches, passes validate-profile.py
  STALE       parses, schema_version is older than current
  INVALID     parses, current schema_version, but fails validation. Also covers
              a schema_version NEWER than current — the toolkit is out of date,
              not the profile
  UNREADABLE  the file exists but is not parseable YAML
  NO_PYTHON   the environment cannot run the check. NOT a statement about the
              profile, which has not been read

**On NO_PYTHON, and what this port can and cannot do.** The bash version of
this script existed partly to answer "is there a working interpreter at all",
which it could do because it ran before Python did. A Python script cannot
report its own absence. So this file detects the half it can see from the
inside — pyyaml missing, the profile unreadable — and `detect-profile.sh`
remains the entry point that answers the other half by finding an interpreter
first.

That is not transitional. On Windows `python3` is routinely the Microsoft
Store stub, which prints an install prompt and exits without being an
interpreter; the wrapper is what turns that into `NO_PYTHON` and a fix rather
than a confusing empty result. Anything that must work on a machine nobody has
checked should call the wrapper. Anything already running under a known-good
interpreter can call this directly.

Usage:
  detect-profile.py [--json]

--json wraps the state in the toolkit's one envelope (scripts/cli_output.py):
  {"ok": <state == VALID>, "errors": [], "warnings": [], "data": {"state": ...}}
errors/warnings are always empty: this reports a state, not itemized
diagnostics. Run validate-profile.py --json for those.
"""

import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VALIDATE_SCRIPT = os.path.join(SCRIPT_DIR, "validate-profile.py")

# Deliberately no cli_output import: this script builds its one envelope by
# hand (see emit()), and importing a module it does not use would imply a
# dependency that is not there.

CURRENT_SCHEMA_VERSION = 2


def profile_path():
    home = os.environ.get("AGENT_TOOLKIT_HOME", os.path.expanduser("~/.agent-toolkit"))
    return os.path.join(home, "baseline.yaml")


def emit(state, note=None, as_json=False):
    """
    The one exit point. Always exits 0 — see the header.

    The envelope is built by hand rather than through `cli_output.envelope()`,
    which derives `ok` from whether there are errors. Here there never are:
    this script reports a *state*, and `NONE` or `STALE` is a real answer
    rather than a failure to produce one. So `ok` means "there is a usable
    profile", which is only true of VALID.

    This is the documented exception to the envelope's `ok == no errors` rule
    (see docs/testing.md, C3). Deriving it the usual way made every state
    report `ok: true`, including NONE.
    """
    if note:
        print(note, file=sys.stderr)
    if as_json:
        print(json.dumps({
            "ok": state == "VALID",
            "errors": [],
            "warnings": [],
            "data": {"state": state},
        }, indent=2))
    else:
        print(state)
    return 0


def detect(path):
    """Returns (state, note). `note` is stderr diagnostics, or None."""
    if not os.path.isfile(path):
        return "NONE", None

    try:
        import yaml
    except ImportError:
        return "NO_PYTHON", (
            "detect-profile: this interpreter (%s) does not have pyyaml.\n"
            "  Fix with: %s -m pip install pyyaml\n"
            "  The profile at %s has NOT been read."
            % (sys.executable, sys.executable, path)
        )

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError:
        return "UNREADABLE", None
    except OSError as exc:
        return "UNREADABLE", "detect-profile: could not read %s: %s" % (path, exc)

    if not isinstance(data, dict):
        return "UNREADABLE", None

    version = data.get("schema_version")
    if version is None:
        return "INVALID", None

    # A non-numeric schema_version is a bad profile, not an old one. The bash
    # version needed a guard here because its arithmetic read a string as 0
    # and reported STALE; Python needs the same guard for the same reason.
    if isinstance(version, bool) or not isinstance(version, int):
        return "INVALID", None

    if version < CURRENT_SCHEMA_VERSION:
        return "STALE", None
    if version > CURRENT_SCHEMA_VERSION:
        return "INVALID", None

    result = subprocess.run(
        [sys.executable, VALIDATE_SCRIPT, path],
        capture_output=True, text=True,
    )
    return ("VALID" if result.returncode == 0 else "INVALID"), None


def main():
    parser = argparse.ArgumentParser(
        description="Report the state of the user's baseline profile."
    )
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    args = parser.parse_args()

    state, note = detect(profile_path())
    return emit(state, note, args.json)


if __name__ == "__main__":
    sys.exit(main())
