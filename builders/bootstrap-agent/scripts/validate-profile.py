#!/usr/bin/env python3
"""
validate-profile.py — validate a baseline profile (baseline.yaml).

Distinct from validate-agent.py: a baseline is expected to be COMPLETE, not
overrides. So this checks:

  1. STRUCTURAL — required sections and fields present, legal enum values,
     schema_version matches, no secrets, coherence between fields that only
     make sense together (e.g. evaluation_loop.enabled needs a reviewer).
  2. RANGE (warnings) — numeric budgets outside a sane range. Not an error;
     the user may have a real reason for an unusual number.
  3. SEMANTIC — stub. Hook for the Validation Agent.

Usage:
    validate-profile.py <baseline.yaml>

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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(BUILDER_DIR)), "scripts"))

try:
    import schema_utils
except ImportError as exc:  # pragma: no cover
    print("ERROR: could not import scripts/schema_utils.py: %s" % exc)
    sys.exit(2)

SCHEMA_PATH = os.path.join(BUILDER_DIR, "schema", "baseline-profile.schema.json")
CURRENT_SCHEMA_VERSION = 1
ENV_REF = re.compile(r"^env:[A-Z_][A-Z0-9_]*$")

_SCHEMA = schema_utils.load_schema(SCHEMA_PATH)

# Derived from the JSON schema at import time — not hand-copied. See
# scripts/schema_utils.py and HANDOFF.md, "Known gaps" #1.
ENUMS = schema_utils.extract_enums(_SCHEMA)

# schema_version is required too, but it gets its own const check below with
# a migration-specific message, so it's excluded here.
REQUIRED_FIELDS = [
    path for path in schema_utils.extract_required_leaves(_SCHEMA)
    if path != "schema_version"
]

# (dotted path, minimum, maximum, label) — outside this range is a WARN, not an ERROR.
RANGE_CHECKS = [
    ("operating_constraints.cost_performance_budget.max_tokens_per_run", 100, 200000),
    ("operating_constraints.cost_performance_budget.latency_target_seconds", 1, 600),
    ("knowledge_memory.context_management.tool_output_token_cap", 1000, 200000),
]

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


def run_structural_checks(data, raw_text):
    errors, warnings = [], []

    version = data.get("schema_version")
    if version is None:
        errors.append("schema_version: missing. Add `schema_version: %d`." % CURRENT_SCHEMA_VERSION)
    elif version != CURRENT_SCHEMA_VERSION:
        errors.append(
            "schema_version: %r does not match the current schema (%d). "
            "Run `/bootstrap-profile migrate`." % (version, CURRENT_SCHEMA_VERSION)
        )

    for path in REQUIRED_FIELDS:
        value, found = get_path(data, path)
        if not found or value in (None, ""):
            errors.append("%s: required." % path)

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
                "operating_constraints.evaluation_loop: enabled is true but reviewer is "
                "null or missing. Set a reviewer, or turn evaluation_loop off."
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
                "Possible secret in baseline.yaml (%s): %s… — replace with an env: reference."
                % (description, snippet[:12])
            )

    return errors, warnings


def run_range_checks(data):
    warnings = []
    for path, lo, hi in RANGE_CHECKS:
        value, found = get_path(data, path)
        if found and isinstance(value, (int, float)) and not (lo <= value <= hi):
            warnings.append(
                "%s: %r is outside the usual range (%s–%s). Not an error, but "
                "confirm it's intentional." % (path, value, lo, hi)
            )
    return warnings


def run_semantic_checks(data):
    """
    STUB — hook for the Validation Agent.

    Planned checks:
      - pattern vs evaluation_loop coherence beyond the null-reviewer case
      - permissions_scope vs guardrails: internally coherent risk posture
      - tone_of_voice vs audience coherence
      - locale vs domain plausibility

    Returns (errors, warnings). Currently always empty.
    """
    return [], []


def main():
    if len(sys.argv) < 2:
        print("Usage: validate-profile.py <baseline.yaml>")
        return 2

    path = sys.argv[1]
    if not os.path.isfile(path):
        print("ERROR: no profile at %s" % path)
        return 2

    with open(path, "r", encoding="utf-8") as fh:
        raw_text = fh.read()

    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        print("ERROR: could not parse %s as YAML:\n%s" % (path, exc))
        return 2

    if not isinstance(data, dict):
        print("ERROR: baseline.yaml root must be a mapping, found %s." % type(data).__name__)
        return 2

    errors, warnings = run_structural_checks(data, raw_text)
    warnings += run_range_checks(data)

    sem_errors, sem_warnings = run_semantic_checks(data)
    errors += sem_errors
    warnings += sem_warnings

    for warning in warnings:
        print("WARN:  %s" % warning)
    for error in errors:
        print("ERROR: %s" % error)

    if errors:
        print("\n%d error(s), %d warning(s) — profile is INVALID." % (len(errors), len(warnings)))
        return 1

    print("Profile at %s is valid (%d warning(s))." % (path, len(warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
