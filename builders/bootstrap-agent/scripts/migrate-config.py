#!/usr/bin/env python3
"""
migrate-config.py — carry a toolkit config file forward a schema version.

Works on a `baseline.yaml` or an `agent.yaml`. It was written for the first
and turned out to fit the second unchanged, because the v1-to-v2 change is in
`operating_constraints.permissions_scope`, which both schemas shared. Named
for what it does rather than for what it was written for.

Migration is deterministic: given a profile and a version to migrate from, the
result is fully determined. So it is a script, not prose a model follows (D19).
The rule that makes it safe is worth stating plainly:

    **Start from the user's document and change only what the version bump
    requires.** Never rebuild the profile from a template.

That is what "no data loss" means here. A migration that constructs a fresh
document from known fields silently drops anything it wasn't told about —
a comment-worthy value, a field added by a later toolkit, a key someone put
there on purpose. Every migration below mutates a deep copy of the original.

The v1 to v2 mapping (from docs/proposals/runtime-contract.md):

    tools: [read]          -> capabilities: [file.read]
    tools: [write]         -> capabilities: [file.read, file.write]
    tools: [search]        -> capabilities: [file.search]
    external_calls: true   -> capabilities: [web.search, web.fetch]
    external_calls: false  -> capabilities: [web.search], and SAY SO

That last row grants access the v1 profile withheld. It is the deliberate
consequence of D12 — read-only web search is a lower risk than the file.write
these profiles already had, and an agent that silently cannot look anything up
is the worse failure. But it is still an expansion of what the agent may do,
applied by a tool the user ran for another reason, so it is reported as a note
rather than folded in with the rest of the changes.

Usage:
    migrate-config.py [<path>] [--dry-run] [--json]

Defaults to $AGENT_TOOLKIT_HOME/baseline.yaml. Pass an agent's `agent.yaml`
to migrate that instead.

Writes a backup to <profile>.bak-<from-version> before touching the original.

Exit codes:
    0  migrated, or already current
    1  cannot migrate — unknown version, or a value that needs a human
    2  file missing or unparseable
"""

import argparse
import copy
import json
import os
import sys

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(2)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(BUILDER_DIR))
SCHEMA_PATH = os.path.join(BUILDER_DIR, "schema", "baseline-profile.schema.json")

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import cli_output  # noqa: E402

CURRENT_SCHEMA_VERSION = 2

# v1 `tools` entries and what each grants in v2. `write` implies read: you
# cannot meaningfully write a file you may not open.
V1_TOOL_CAPABILITIES = {
    "read": ["file.read"],
    "write": ["file.read", "file.write"],
    "search": ["file.search"],
}


def capability_order():
    """The schema's own enum order, so migrated output is stable and readable."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    node = schema["properties"]["operating_constraints"]["properties"]
    return list(node["permissions_scope"]["properties"]["capabilities"]["items"]["enum"])


def get_path(data, dotted):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None, False
        node = node[part]
    return node, True


def migrate_v1_to_v2(profile):
    """
    Replace the v1 permissions vocabulary with v2 capabilities.

    Mutates `profile` in place — the caller has already copied it — and
    returns (changes, notes, warnings).
    """
    changes, notes, warnings = [], [], []

    scope, found = get_path(profile, "operating_constraints.permissions_scope")
    if not found or not isinstance(scope, dict):
        # Nothing to translate. The version bump alone is the migration, and
        # the agent inherits the schema default when it renders.
        changes.append(
            "no permissions_scope to translate; capabilities will take the schema default"
        )
        profile["schema_version"] = 2
        return changes, notes, warnings

    granted = []

    tools = scope.get("tools")
    if tools is not None:
        for tool in tools if isinstance(tools, list) else [tools]:
            mapped = V1_TOOL_CAPABILITIES.get(tool)
            if mapped is None:
                warnings.append(cli_output.issue(
                    "operating_constraints.permissions_scope.tools: %r has no v2 "
                    "equivalent, so nothing was granted for it. The v1 tool names were "
                    "never a defined set, so this cannot be translated automatically — "
                    "add the capability you meant by hand." % tool,
                    field="operating_constraints.permissions_scope.tools",
                    legal=set(V1_TOOL_CAPABILITIES),
                    fix="Add the capability you meant to grant to `capabilities`.",
                ))
                continue
            for capability in mapped:
                if capability not in granted:
                    granted.append(capability)
        changes.append("tools %s -> capabilities" % json.dumps(tools))
        del scope["tools"]

    external_calls = scope.get("external_calls")
    if external_calls is not None:
        if external_calls:
            for capability in ("web.search", "web.fetch"):
                if capability not in granted:
                    granted.append(capability)
            changes.append("external_calls: true -> web.search + web.fetch")
        else:
            if "web.search" not in granted:
                granted.append("web.search")
            notes.append(
                "This profile had `external_calls: false`, which withheld all network "
                "access. Version 2 splits that into web.search and web.fetch, and grants "
                "web.search at every risk posture — so this migration GRANTS read-only "
                "web search that the profile previously denied. Page fetching "
                "(web.fetch) is still withheld. Remove web.search from capabilities if "
                "that is not what you want."
            )
            changes.append("external_calls: false -> web.search granted (see notes)")
        del scope["external_calls"]

    if granted:
        order = capability_order()
        scope["capabilities"] = sorted(
            granted, key=lambda capability: order.index(capability)
        )

    profile["schema_version"] = 2
    return changes, notes, warnings


MIGRATIONS = {1: migrate_v1_to_v2}


def migrate(original):
    """
    Apply every migration between the profile's version and the current one.

    Returns (migrated, steps, notes, warnings, errors). `migrated` is None
    when nothing could be done.
    """
    version = original.get("schema_version")
    if not isinstance(version, int):
        return None, [], [], [], [cli_output.issue(
            "schema_version: %r is not a version number, so there is nothing to migrate "
            "from." % version,
            field="schema_version",
            fix="Set schema_version to the version this profile was written for.",
        )]

    if version > CURRENT_SCHEMA_VERSION:
        return None, [], [], [], [cli_output.issue(
            "schema_version: %d is newer than this toolkit understands (%d). The "
            "toolkit is out of date, not the profile — update it rather than "
            "migrating backwards." % (version, CURRENT_SCHEMA_VERSION),
            field="schema_version",
            fix="Update the toolkit.",
        )]

    migrated = copy.deepcopy(original)
    steps, notes, warnings = [], [], []

    while version < CURRENT_SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            return None, steps, notes, warnings, [cli_output.issue(
                "no migration from schema_version %d to %d." % (version, version + 1),
                field="schema_version",
            )]
        step_changes, step_notes, step_warnings = step(migrated)
        steps.append({
            "from": version,
            "to": version + 1,
            "changes": step_changes,
        })
        notes.extend(step_notes)
        warnings.extend(step_warnings)
        version += 1

    return migrated, steps, notes, warnings, []


def render_yaml(profile):
    return yaml.safe_dump(profile, sort_keys=False, default_flow_style=False, width=100)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate a baseline profile to the current schema version."
    )
    parser.add_argument(
        "path", nargs="?", help="Profile to migrate (default: $AGENT_TOOLKIT_HOME/baseline.yaml)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report the migration and return the result; write nothing",
    )
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    args = parser.parse_args()

    path = args.path
    if not path:
        home = os.environ.get("AGENT_TOOLKIT_HOME", os.path.expanduser("~/.agent-toolkit"))
        path = os.path.join(home, "baseline.yaml")

    if not os.path.isfile(path):
        return cli_output.fail("no profile at %s" % path, args.json)

    with open(path, "r", encoding="utf-8") as fh:
        raw_text = fh.read()

    try:
        original = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        return cli_output.fail("could not parse %s as YAML:\n%s" % (path, exc), args.json)

    if not isinstance(original, dict):
        return cli_output.fail(
            "baseline.yaml root must be a mapping, found %s." % type(original).__name__,
            args.json,
        )

    from_version = original.get("schema_version")

    if from_version == CURRENT_SCHEMA_VERSION:
        data = {"path": path, "from": from_version, "to": from_version,
                "migrated": False, "steps": [], "notes": []}
        if args.json:
            cli_output.print_envelope([], [], data)
        else:
            print("%s is already at schema_version %d." % (path, CURRENT_SCHEMA_VERSION))
        return 0

    migrated, steps, notes, warnings, errors = migrate(original)
    if errors:
        if args.json:
            cli_output.print_envelope(errors, warnings, {"path": path})
        else:
            cli_output.render_text(errors, warnings)
        return 1

    backup_path = "%s.bak-%s" % (path, from_version)

    # Values survive a migration; comments do not. Round-tripping through
    # pyyaml drops them, and preserving them would mean a round-trip YAML
    # library the toolkit does not otherwise need. Say so rather than let
    # someone discover their annotations are gone — the backup has them.
    if "#" in raw_text:
        notes.append(
            "Comments in the original are not carried across — values survive a "
            "migration, comments do not. The backup at %s keeps them if you want to "
            "copy any back." % os.path.basename(backup_path)
        )

    data = {
        "path": path,
        "from": from_version,
        "to": CURRENT_SCHEMA_VERSION,
        "migrated": True,
        "dry_run": args.dry_run,
        "backup": None if args.dry_run else backup_path,
        "steps": steps,
        "notes": notes,
        "profile": migrated,
        "yaml": render_yaml(migrated),
    }

    if not args.dry_run:
        # Back up before touching the original, and never over an existing
        # backup — a second migration run would otherwise destroy the only
        # copy of what the profile looked like before the first one.
        if os.path.exists(backup_path):
            message = (
                "a backup already exists at %s. Move or delete it first; overwriting it "
                "would destroy the only copy of the pre-migration profile." % backup_path
            )
            if args.json:
                cli_output.print_envelope(
                    [cli_output.issue(message, fix="Move or delete the existing backup.")],
                    warnings, {"path": path},
                )
            else:
                print("ERROR: %s" % message)
            return 1

        with open(backup_path, "w", encoding="utf-8") as fh:
            fh.write(raw_text)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_yaml(migrated))

    if args.json:
        cli_output.print_envelope([], warnings, data)
        return 0

    cli_output.render_text([], warnings)
    print("Migrated %s from schema_version %s to %d."
          % (path, from_version, CURRENT_SCHEMA_VERSION))
    for step in steps:
        for change in step["changes"]:
            print("  - %s" % change)
    if not args.dry_run:
        print("Backup: %s" % backup_path)
    for note in notes:
        print("\nNOTE: %s" % note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
