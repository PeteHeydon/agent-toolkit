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
    validate-profile.py <baseline.yaml> [--json]

Exit codes:
    0  valid
    1  validation errors
    2  file missing or unparseable
"""

import argparse
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
    import cli_output
    import semantic_checks
except ImportError as exc:  # pragma: no cover
    print("ERROR: could not import scripts/schema_utils.py or scripts/cli_output.py: %s" % exc)
    sys.exit(2)

SCHEMA_PATH = os.path.join(BUILDER_DIR, "schema", "baseline-profile.schema.json")
CURRENT_SCHEMA_VERSION = 2
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
# Arrays whose items are an enum — `capabilities`. Checked per element, not
# as a whole value; see schema_utils.extract_array_enums.
ARRAY_ENUMS = schema_utils.extract_array_enums(_SCHEMA)

# v1 fields that v2 replaced. `additionalProperties: false` would reject them,
# but nothing here runs the JSON Schema itself, so say so explicitly — and name
# the replacement, because the whole point of the message is to migrate someone.
RETIRED_FIELDS = {
    "operating_constraints.permissions_scope.tools":
        "operating_constraints.permissions_scope.capabilities",
    "operating_constraints.permissions_scope.external_calls":
        "the web.search and web.fetch capabilities",
}

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
        errors.append(cli_output.issue(
            "schema_version: missing. Add `schema_version: %d`." % CURRENT_SCHEMA_VERSION,
            field="schema_version",
            fix="Add `schema_version: %d`." % CURRENT_SCHEMA_VERSION,
        ))
    elif version != CURRENT_SCHEMA_VERSION:
        errors.append(cli_output.issue(
            "schema_version: %r does not match the current schema (%d). "
            "Run `/bootstrap-profile migrate`." % (version, CURRENT_SCHEMA_VERSION),
            field="schema_version",
            fix="Run `/bootstrap-profile migrate`.",
        ))

    for path in REQUIRED_FIELDS:
        value, found = get_path(data, path)
        if not found or value in (None, ""):
            errors.append(cli_output.issue(
                "%s: required." % path, field=path, fix="Add this field."
            ))

    for path, legal in ENUMS.items():
        value, found = get_path(data, path)
        if found and value is not None and value not in legal:
            errors.append(cli_output.issue(
                "%s: %r is not a legal value. Expected one of: %s"
                % (path, value, ", ".join(sorted(legal))),
                field=path, legal=legal, fix="Use one of the legal values.",
            ))

    for path, legal in ARRAY_ENUMS.items():
        value, found = get_path(data, path)
        if found and isinstance(value, list):
            for item in value:
                if item not in legal:
                    errors.append(cli_output.issue(
                        "%s: %r is not a legal capability. Expected one of: %s"
                        % (path, item, ", ".join(sorted(legal))),
                        field=path, legal=legal,
                        fix="Use one of the legal capabilities.",
                    ))

    for retired, replacement in RETIRED_FIELDS.items():
        _value, found = get_path(data, retired)
        if found:
            errors.append(cli_output.issue(
                "%s: removed in schema_version 2. Use %s instead. "
                "Run `/bootstrap-profile migrate`." % (retired, replacement),
                field=retired,
                fix="Use %s instead." % replacement,
            ))

    # Domain lists bound web.fetch. Without that capability granted they are
    # inert, and a config that looks like it restricts egress but doesn't is
    # worse than one that says nothing.
    granted, _ = get_path(data, "operating_constraints.permissions_scope.capabilities")
    for key in ("allowed_domains", "blocked_domains"):
        domains, found = get_path(
            data, "operating_constraints.permissions_scope.web.%s" % key
        )
        if found and domains and "web.fetch" not in (granted or []):
            errors.append(cli_output.issue(
                "operating_constraints.permissions_scope.web.%s: set, but web.fetch is "
                "not granted, so it has no effect. Grant web.fetch or drop the list."
                % key,
                field="operating_constraints.permissions_scope.web.%s" % key,
                fix="Grant web.fetch, or remove the domain list.",
            ))
    creds = data.get("credentials") or {}
    if isinstance(creds, dict):
        for key, value in creds.items():
            if not isinstance(value, str) or not ENV_REF.match(value):
                errors.append(cli_output.issue(
                    "credentials.%s: must be an env var reference like 'env:MY_VAR', found %r."
                    % (key, value),
                    field="credentials.%s" % key,
                    fix="Replace with an env: reference.",
                ))

    for pattern, description in SECRET_PATTERNS:
        for match in pattern.findall(raw_text):
            snippet = match if isinstance(match, str) else match[0]
            if snippet.startswith("env:"):
                continue
            warnings.append(cli_output.issue(
                "Possible secret in baseline.yaml (%s): %s… — replace with an env: reference."
                % (description, snippet[:12]),
            ))

    model, found = get_path(data, "operating_constraints.model")
    if found and model is not None:
        _canonical, note = schema_utils.resolve_model(model)
        if note:
            warnings.append(cli_output.issue(note, field="operating_constraints.model"))

    return errors, warnings


def run_range_checks(data):
    warnings = []
    for path, lo, hi in RANGE_CHECKS:
        value, found = get_path(data, path)
        if found and isinstance(value, (int, float)) and not (lo <= value <= hi):
            warnings.append(cli_output.issue(
                "%s: %r is outside the usual range (%s–%s). Not an error, but "
                "confirm it's intentional." % (path, value, lo, hi),
                field=path,
            ))
    return warnings


def run_semantic_checks(data):
    """
    Checks a schema cannot express — see scripts/semantic_checks.py.

    A baseline is held to the same standard as an agent, because a profile
    that would be incoherent as an agent is incoherent now, and finding out at
    creation is cheaper than finding out once per agent.

    What is still not here, and is not a rule: tone against audience, locale
    against domain, whether the whole thing hangs together. Those need a model
    and belong to the validation builder.
    """
    raw_errors, raw_warnings = semantic_checks.run(data)
    errors = [cli_output.issue("%s: %s" % (field, message), field=field, fix=fix)
              for field, message, fix in raw_errors]
    warnings = [cli_output.issue("%s: %s" % (field, message), field=field, fix=fix)
                for field, message, fix in raw_warnings]
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate a baseline profile.")
    parser.add_argument("path", help="Path to baseline.yaml")
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        return cli_output.fail("no profile at %s" % args.path, args.json)

    with open(args.path, "r", encoding="utf-8") as fh:
        raw_text = fh.read()

    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        return cli_output.fail(
            "could not parse %s as YAML:\n%s" % (args.path, exc), args.json
        )

    if not isinstance(data, dict):
        return cli_output.fail(
            "baseline.yaml root must be a mapping, found %s." % type(data).__name__, args.json
        )

    errors, warnings = run_structural_checks(data, raw_text)
    warnings += run_range_checks(data)

    sem_errors, sem_warnings = run_semantic_checks(data)
    errors += sem_errors
    warnings += sem_warnings

    if args.json:
        cli_output.print_envelope(errors, warnings, {"path": args.path})
        return 1 if errors else 0

    cli_output.render_text(errors, warnings)

    if errors:
        print("\n%d error(s), %d warning(s) — profile is INVALID." % (len(errors), len(warnings)))
        return 1

    print("Profile at %s is valid (%d warning(s))." % (args.path, len(warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
