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
    validate-agent.py <agent.yaml> [--json]

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
    import cli_output
    import module_utils
    import semantic_checks
except ImportError as exc:  # pragma: no cover
    print("ERROR: could not import scripts/schema_utils.py or scripts/cli_output.py: %s" % exc)
    sys.exit(2)

SCHEMA_PATH = os.path.join(BUILDER_DIR, "schema", "agent-override.schema.json")
CURRENT_SCHEMA_VERSION = 2
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
CAPABILITIES_PATH = "operating_constraints.permissions_scope.capabilities"
ENV_REF = re.compile(r"^env:[A-Z_][A-Z0-9_]*$")

# Derived from the JSON schema at import time — not hand-copied. An override
# must obey the same enums as the baseline because both schemas define them
# independently; see scripts/schema_utils.py and HANDOFF.md, "Known gaps" #1.
ENUMS = schema_utils.extract_enums(schema_utils.load_schema(SCHEMA_PATH))

# Arrays whose items are an enum — `capabilities`. Checked per element, not
# as a whole value; see schema_utils.extract_array_enums.
ARRAY_ENUMS = schema_utils.extract_array_enums(schema_utils.load_schema(SCHEMA_PATH))

# v1 fields that v2 replaced. `additionalProperties: false` would reject them,
# but nothing here runs the JSON Schema itself, so say so explicitly — and name
# the replacement, because the whole point of the message is to migrate someone.
RETIRED_FIELDS = {
    "operating_constraints.permissions_scope.tools":
        "operating_constraints.permissions_scope.capabilities",
    "operating_constraints.permissions_scope.external_calls":
        "the web.search and web.fetch capabilities",
}

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
        errors.append(cli_output.issue(
            "schema_version: missing. Add `schema_version: %d`." % CURRENT_SCHEMA_VERSION,
            field="schema_version",
            fix="Add `schema_version: %d`." % CURRENT_SCHEMA_VERSION,
        ))
    elif isinstance(version, int) and version < CURRENT_SCHEMA_VERSION:
        # Stale, not malformed. An agent written against an older schema is a
        # migration away from working, and saying only "does not match" leaves
        # the user to guess that a migration exists at all.
        errors.append(cli_output.issue(
            "schema_version: %d is older than the current schema (%d). This agent "
            "predates a schema change and needs migrating, not repairing."
            % (version, CURRENT_SCHEMA_VERSION),
            field="schema_version",
            fix="Run `/refresh-agent <name> --migrate`, or "
                "migrate-config.py <agent.yaml>.",
        ))
    elif version != CURRENT_SCHEMA_VERSION:
        errors.append(cli_output.issue(
            "schema_version: %r does not match the current schema (%d). A version "
            "newer than this means the toolkit is out of date, not the agent."
            % (version, CURRENT_SCHEMA_VERSION),
            field="schema_version",
            fix="Update the toolkit.",
        ))

    name = data.get("name")
    if not name:
        errors.append(cli_output.issue("name: required.", field="name", fix="Add a name."))
    elif not SLUG.match(str(name)):
        errors.append(cli_output.issue(
            "name: %r is not a valid slug. Use lowercase letters, digits and hyphens, "
            "starting with a letter." % name,
            field="name",
            fix="Use lowercase letters, digits and hyphens, starting with a letter.",
        ))

    if not data.get("description"):
        warnings.append(cli_output.issue(
            "description: empty. One line on what this agent does saves future confusion.",
            field="description",
        ))

    extends = data.get("extends")
    if not extends:
        errors.append(cli_output.issue(
            "extends: required. An agent must name the profile it inherits from, "
            "e.g. `extends: \"~/.agent-toolkit/baseline.yaml\"`.",
            field="extends",
            fix="Add `extends: \"~/.agent-toolkit/baseline.yaml\"` or your own baseline's path.",
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
                "Possible secret in agent.yaml (%s): %s… — replace with an env: reference."
                % (description, snippet[:12]),
            ))

    model, found = get_path(data, "operating_constraints.model")
    if found and model is not None:
        _canonical, note = schema_utils.resolve_model(model)
        if note:
            warnings.append(cli_output.issue(note, field="operating_constraints.model"))

    return errors, warnings


INTENT_MARKER = "TODO:"


def run_intent_checks(agent_path):
    """
    Warn while the seeded process still carries its `TODO:` step.

    The toolkit writes the scaffolding around an agent's process — confirm the
    inputs, check the result — because those are properties of the pattern.
    What the agent actually does is the user's, and until they write it the
    agent is unfinished. Saying so here makes that a state someone can report
    on, rather than something discovered on the first run.
    """
    warnings = []
    claude_md = os.path.join(os.path.dirname(os.path.abspath(agent_path)), "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return warnings

    with open(claude_md, "r", encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if INTENT_MARKER in line:
                warnings.append(cli_output.issue(
                    "CLAUDE.md:%d still has the seeded `%s` step — this agent's own "
                    "process has never been written. Replace that step with what the "
                    "agent actually does." % (number, INTENT_MARKER),
                    field="CLAUDE.md",
                    fix="Replace the TODO: step with the agent's real process.",
                ))
    return warnings


def run_resolution_checks(agent_path, data):
    """Confirm the extends chain reaches a real, usable baseline."""
    errors, warnings = [], []
    resolved = None

    try:
        resolved, provenance, chain = resolve_config.resolve_chain(agent_path)
        if len(chain) < 2:
            warnings.append(cli_output.issue(
                "extends chain has no parent — this file resolves to itself alone. "
                "An agent normally inherits from a baseline.",
                field="extends",
            ))
    except resolve_config.ResolveError as exc:
        errors.append(cli_output.issue("Resolution failed: %s" % exc, field="extends"))
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
            warnings.append(cli_output.issue(
                "%s: overrides with the same value as the baseline (%r). Remove it to keep "
                "inheriting — an identical override silently pins the field against future "
                "baseline changes." % (dotted, value),
                field=dotted,
                fix="Remove the override to keep inheriting.",
            ))
    return warnings


def run_semantic_checks(data, resolved, agent_path=None):
    """
    Checks a schema cannot express — see scripts/semantic_checks.py.

    Run against the **resolved** config, not this file: an agent composing a
    module needs the capabilities it ends up with, whether they came from here
    or from the baseline.
    """
    if resolved is None:
        return [], []

    agent_dir = os.path.dirname(os.path.abspath(agent_path)) if agent_path else None
    raw_errors, raw_warnings = semantic_checks.run(
        resolved, agent_dir=agent_dir, module_utils=module_utils
    )
    errors = [cli_output.issue("%s: %s" % (field, message), field=field, fix=fix)
              for field, message, fix in raw_errors]
    warnings = [cli_output.issue("%s: %s" % (field, message), field=field, fix=fix)
                for field, message, fix in raw_warnings]
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate an agent override file.")
    parser.add_argument("path", help="Path to agent.yaml")
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        return cli_output.fail("no agent file at %s" % args.path, args.json)

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
            "agent.yaml root must be a mapping, found %s." % type(data).__name__, args.json
        )

    errors, warnings = run_structural_checks(data, raw_text)

    res_errors, res_warnings, resolved = run_resolution_checks(args.path, data)
    errors += res_errors
    warnings += res_warnings

    warnings += run_hygiene_checks(args.path, data, resolved)
    warnings += run_intent_checks(args.path)

    sem_errors, sem_warnings = run_semantic_checks(data, resolved, args.path)
    errors += sem_errors
    warnings += sem_warnings

    if args.json:
        cli_output.print_envelope(errors, warnings, {"path": args.path})
        return 1 if errors else 0

    cli_output.render_text(errors, warnings)

    if errors:
        print("\n%d error(s), %d warning(s) — agent is INVALID." % (len(errors), len(warnings)))
        return 1

    print("Agent at %s is valid (%d warning(s))." % (args.path, len(warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
