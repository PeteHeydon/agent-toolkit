#!/usr/bin/env python3
"""
validate-agent.py — validate an agent override file (agent.yaml).

Distinct from validate-profile.py: an override file is mostly *absences*. Most
fields are legitimately missing because they're inherited. So this checks:

  1. STRUCTURAL — required identity fields, legal enum values on whatever IS
     present, name is a valid slug, no secrets.
  2. RESOLUTION — the extends chain reaches a real baseline, resolves without
     cycles, and the resolved result is itself valid.
  3. HYGIENE (warnings) — overrides that restate the baseline value verbatim.
     These are noise, and worse, they silently pin the field against future
     baseline edits.
  4. SEMANTIC — stub. Hook for the Validation Agent.

Usage:
    validate-agent.py <agent.yaml>

Exit codes:
    0  valid
    1  validation errors
    2  file missing or unparseable
"""

import os
import re
import sys

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(2)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(BUILDER_DIR)), "scripts"))

try:
    from importlib import util as _importlib_util
    _spec = _importlib_util.spec_from_file_location(
        "resolve_config", os.path.join(SCRIPT_DIR, "resolve-config.py")
    )
    resolve_config = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(resolve_config)
except Exception as exc:  # pragma: no cover
    print("ERROR: could not load resolve-config.py: %s" % exc)
    sys.exit(2)

try:
    import schema_utils
except ImportError as exc:  # pragma: no cover
    print("ERROR: could not import scripts/schema_utils.py: %s" % exc)
    sys.exit(2)

SCHEMA_PATH = os.path.join(BUILDER_DIR, "schema", "agent-override.schema.json")
CURRENT_SCHEMA_VERSION = 1
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
ENV_REF = re.compile(r"^env:[A-Z_][A-Z0-9_]*$")

# Derived from the JSON schema at import time — not hand-copied. An override
# must obey the same enums as the baseline because both schemas define them
# independently; see scripts/schema_utils.py and HANDOFF.md, "Known gaps" #1.
ENUMS = schema_utils.extract_enums(schema_utils.load_schema(SCHEMA_PATH))

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "looks like an API key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "looks like a GitHub token"),
    (re.compile(r"(?i)\b(password|passwd|secret|token)\s*[:=]\s*\S+"), "looks like an inline credential"),
]


def get_path(data, dotted):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None, False
        node = node[part]
    return node, True


def flatten(node, prefix=""):
    out = {}
    for key, value in node.items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, dotted))
        else:
            out[dotted] = value
    return out


def run_structural_checks(data, raw_text):
    errors, warnings = [], []

    version = data.get("schema_version")
    if version is None:
        errors.append("schema_version: missing. Add `schema_version: %d`." % CURRENT_SCHEMA_VERSION)
    elif version != CURRENT_SCHEMA_VERSION:
        errors.append(
            "schema_version: %r does not match the current schema (%d)."
            % (version, CURRENT_SCHEMA_VERSION)
        )

    name = data.get("name")
    if not name:
        errors.append("name: required.")
    elif not SLUG.match(str(name)):
        errors.append(
            "name: %r is not a valid slug. Use lowercase letters, digits and hyphens, "
            "starting with a letter." % name
        )

    if not data.get("description"):
        warnings.append("description: empty. One line on what this agent does saves future confusion.")

    extends = data.get("extends")
    if not extends:
        errors.append(
            "extends: required. An agent must name the profile it inherits from, "
            "e.g. `extends: \"~/.agent-toolkit/baseline.yaml\"`."
        )

    for path, legal in ENUMS.items():
        value, found = get_path(data, path)
        if found and value is not None and value not in legal:
            errors.append(
                "%s: %r is not a legal value. Expected one of: %s"
                % (path, value, ", ".join(sorted(legal)))
            )

    enabled, _ = get_path(data, "operating_constraints.evaluation_loop.enabled")
    if enabled:
        reviewer, found = get_path(data, "operating_constraints.evaluation_loop.reviewer")
        if not found or not reviewer:
            errors.append(
                "operating_constraints.evaluation_loop: enabled is true but no reviewer is set "
                "in this file. Set one here, or confirm the baseline provides it."
            )

    creds = data.get("credentials") or {}
    if isinstance(creds, dict):
        for key, value in creds.items():
            if not isinstance(value, str) or not ENV_REF.match(value):
                errors.append(
                    "credentials.%s: must be an env var reference like 'env:MY_VAR', found %r."
                    % (key, value)
                )

    for pattern, description in SECRET_PATTERNS:
        for match in pattern.findall(raw_text):
            snippet = match if isinstance(match, str) else match[0]
            if snippet.startswith("env:"):
                continue
            warnings.append(
                "Possible secret in agent.yaml (%s): %s… — replace with an env: reference."
                % (description, snippet[:12])
            )

    return errors, warnings


def run_resolution_checks(agent_path, data):
    """Confirm the extends chain reaches a real, usable baseline."""
    errors, warnings = [], []
    resolved = None

    try:
        resolved, provenance, chain = resolve_config.resolve_chain(agent_path)
        if len(chain) < 2:
            warnings.append(
                "extends chain has no parent — this file resolves to itself alone. "
                "An agent normally inherits from a baseline."
            )
    except resolve_config.ResolveError as exc:
        errors.append("Resolution failed: %s" % exc)
        return errors, warnings, None

    return errors, warnings, resolved


def run_hygiene_checks(agent_path, data, resolved):
    """Flag overrides that merely restate the inherited value."""
    warnings = []
    if resolved is None:
        return warnings

    extends = data.get("extends")
    if not extends:
        return warnings

    try:
        baseline_resolved, _, _ = resolve_config.resolve_chain(
            resolve_config.expand(extends)
        )
    except resolve_config.ResolveError:
        return warnings

    overrides = flatten({k: v for k, v in data.items()
                         if k not in ("extends", "name", "description", "schema_version")})
    baseline_flat = flatten(baseline_resolved)

    for dotted, value in overrides.items():
        if dotted in baseline_flat and baseline_flat[dotted] == value:
            warnings.append(
                "%s: overrides with the same value as the baseline (%r). Remove it to keep "
                "inheriting — an identical override silently pins the field against future "
                "baseline changes." % (dotted, value)
            )
    return warnings


def run_semantic_checks(data, resolved):
    """
    STUB — hook for the Validation Agent.

    Planned checks:
      - pattern vs evaluation_loop: does the chosen pattern need a loop it lacks?
      - permissions_scope vs guardrails: is the risk posture internally coherent
        once resolved, not just within this file?
      - model vs cost_performance_budget: is the budget achievable?
      - referenced skills in default_context_sources actually exist
      - tone_of_voice vs audience coherence

    Returns (errors, warnings). Currently always empty.
    """
    return [], []


def main():
    if len(sys.argv) < 2:
        print("Usage: validate-agent.py <agent.yaml>")
        return 2

    path = sys.argv[1]
    if not os.path.isfile(path):
        print("ERROR: no agent file at %s" % path)
        return 2

    with open(path, "r", encoding="utf-8") as fh:
        raw_text = fh.read()

    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        print("ERROR: could not parse %s as YAML:\n%s" % (path, exc))
        return 2

    if not isinstance(data, dict):
        print("ERROR: agent.yaml root must be a mapping, found %s." % type(data).__name__)
        return 2

    errors, warnings = run_structural_checks(data, raw_text)

    res_errors, res_warnings, resolved = run_resolution_checks(path, data)
    errors += res_errors
    warnings += res_warnings

    warnings += run_hygiene_checks(path, data, resolved)

    sem_errors, sem_warnings = run_semantic_checks(data, resolved)
    errors += sem_errors
    warnings += sem_warnings

    for warning in warnings:
        print("WARN:  %s" % warning)
    for error in errors:
        print("ERROR: %s" % error)

    if errors:
        print("\n%d error(s), %d warning(s) — agent is INVALID." % (len(errors), len(warnings)))
        return 1

    print("Agent at %s is valid (%d warning(s))." % (path, len(warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
