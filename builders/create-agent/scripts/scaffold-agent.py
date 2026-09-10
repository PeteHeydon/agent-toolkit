#!/usr/bin/env python3
"""
scaffold-agent.py — deterministic file creation for a new agent.

Everything `builders/create-agent/CLAUDE.md` Step 4 used to leave to a model
reading prose: copy `templates/agent/`, substitute `{{AGENT_NAME}}` and
`{{AGENT_DESCRIPTION}}`, write an `agent.yaml` carrying only the requested
overrides, then validate. The interview genuinely needs a model; none of this
does — see D19. Output is the cli_output envelope, always — this script is
meant to be called by a builder or a future front-end, not read directly, so
there's no plain-text mode to keep in sync.

Usage:
    scaffold-agent.py --name <slug> [--dest <dir>] [--description <text>]
                       [--extends <path>] [--set key.path=value ...]
                       [--compose kind/name ...] [--web | --no-web]
                       [--force] [--merge] [--dry-run]

`--merge` is what makes this usable as an *edit*: it starts from the agent's
existing overrides and applies the change on top, so editing one field does
not silently drop the others. Without it, `--force` rewrites `agent.yaml` from
the flags it was given — correct for re-creating an agent from a fresh
interview, data loss for anything that calls itself an edit.

Exit codes:
    0  scaffolded (and, unless --dry-run, the result validated cleanly)
    1  logic error — bad slug, existing directory without --force, a
       malformed --set, conflicting overrides, or validation failed
    2  missing or unreadable input — the toolkit's own template is absent
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

try:
    import yaml
except ImportError:
    print(json.dumps({
        "ok": False,
        "errors": [{"field": None, "message": "pyyaml is required. Install with: pip install pyyaml",
                     "legal": None, "fix": "pip install pyyaml"}],
        "warnings": [],
        "data": {},
    }))
    sys.exit(2)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(BUILDER_DIR))
TEMPLATE_DIR = os.path.join(REPO_ROOT, "templates", "agent")
VALIDATE_SCRIPT = os.path.join(SCRIPT_DIR, "validate-agent.py")
RENDER_SCRIPT = os.path.join(SCRIPT_DIR, "render-agent.py")

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import cli_output  # noqa: E402
import module_utils  # noqa: E402

try:
    from importlib import util as _importlib_util
    _spec = _importlib_util.spec_from_file_location(
        "resolve_config", os.path.join(SCRIPT_DIR, "resolve-config.py")
    )
    resolve_config = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(resolve_config)
except Exception as exc:  # pragma: no cover
    cli_output.print_envelope(
        [cli_output.issue("could not load resolve-config.py: %s" % exc)]
    )
    sys.exit(2)

CAPABILITIES_PATH = "operating_constraints.permissions_scope.capabilities"
WEB_CAPABILITIES = ["web.search", "web.fetch"]
PATTERN_PATH = "operating_constraints.pattern"
MAX_CYCLES_PATH = "operating_constraints.evaluation_loop.max_cycles"
PATTERN_LIBRARY = os.path.join(REPO_ROOT, "library", "pattern")
COMPOSE_PATH = "compose"

# Must match name.pattern in schema/agent-override.schema.json.
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")

# What the toolkit owns inside an agent directory and may therefore rewrite.
# Everything else there is the user's, and --force must not touch it: their
# process section in CLAUDE.md, their steering notes, and above all their
# output/ results. See docs/architecture.md, "Who owns what".
#
# CLAUDE.md's marked region joins this set in TODO 5.1 — a region inside a
# file the user otherwise owns, which is why the whole file is not listed here.
TOOLKIT_OWNED = {"agent.yaml", ".claude/settings.json", ".agent/render.json"}

IDENTITY_KEYS = {"schema_version", "extends", "name", "description"}

# Written by render-agent.py rather than copied from the template, but
# still part of what a scaffold produces — so the dry-run manifest has to
# predict them or it stops matching a real run.
GENERATED_FILES = [".claude/settings.json", ".agent/render.json"]

# CLAUDE.md is written from the template on a fresh scaffold and then
# rendered into; the renderer owns only the marked region inside it, which
# is why the whole file is not in TOOLKIT_OWNED.

AGENT_YAML_HEADER = """# agent.yaml — per-agent configuration
#
# List ONLY the fields that differ from your baseline profile. Everything
# omitted is inherited from the file named in `extends` at runtime.
#
# Precedence: baseline -> THIS FILE -> CLI flag -> in-session instruction.
# Arrays REPLACE wholesale, they never append: to keep the baseline's list and
# add one entry, list them all. Full merge rules:
#   docs/precedence-and-inheritance.md
#
# Never put a secret here. Reference env vars as env:VAR_NAME.
# See docs/environment-variables.md in the toolkit.

"""


class ScaffoldError(Exception):
    """A logic error in the requested scaffold. Always exit 1."""

    def __init__(self, message, field=None, fix=None):
        super().__init__(message)
        self.field = field
        self.fix = fix


def expand(path):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def toolkit_home():
    return os.environ.get("AGENT_TOOLKIT_HOME", os.path.expanduser("~/.agent-toolkit"))


def default_dest():
    return os.path.join(toolkit_home(), "agents")


def default_extends():
    # When AGENT_TOOLKIT_HOME is set (every test, some real installs), the
    # portable "~/.agent-toolkit/..." literal would resolve to the wrong
    # place, so point at the actual home directly instead.
    if os.environ.get("AGENT_TOOLKIT_HOME"):
        return os.path.join(toolkit_home(), "baseline.yaml")
    return "~/.agent-toolkit/baseline.yaml"


def validate_name(name):
    if not name or not SLUG.match(name):
        raise ScaffoldError(
            "name: %r is not a valid slug. Use lowercase letters, digits and hyphens, "
            "starting with a letter." % name,
            field="name",
            fix="Use lowercase letters, digits and hyphens, starting with a letter.",
        )


def existing_overrides(target):
    """
    The overrides already in an agent's `agent.yaml`, if there is one.

    Everything except the identity fields, which are supplied fresh on every
    run. Returns {} when the agent does not exist yet, so --merge on a new
    agent is simply a normal scaffold.
    """
    path = os.path.join(target, "agent.yaml")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ScaffoldError(
            "cannot merge into %s: its agent.yaml did not parse (%s). Fix it, or "
            "re-create the agent without --merge." % (target, exc),
            fix="Repair agent.yaml, or drop --merge to overwrite it.",
        )
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k not in IDENTITY_KEYS}


def deep_merge(base, overlay):
    """
    Overlay wins per leaf; siblings survive. The same rule the resolver uses
    for config layers, applied here to one file's own overrides — an edit
    that set `guardrails.output_validation` should not wipe
    `guardrails.human_in_the_loop` next to it.
    """
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def build_overrides(set_args):
    """Turn repeated --set key.path=value into a nested override dict."""
    overrides = {}
    for raw in set_args:
        if "=" not in raw:
            raise ScaffoldError(
                "--set expects key.path=value, got: %s" % raw,
                fix="Use key.path=value.",
            )
        dotted, raw_value = raw.split("=", 1)
        dotted = dotted.strip()
        if not dotted:
            raise ScaffoldError(
                "--set expects key.path=value, got: %s" % raw,
                fix="Use key.path=value.",
            )

        # Interpret the value as YAML so booleans/ints/lists work naturally,
        # same as resolve-config.py's --set.
        try:
            value = yaml.safe_load(raw_value)
        except yaml.YAMLError:
            value = raw_value

        parts = dotted.split(".")
        node = overrides
        for i, part in enumerate(parts[:-1]):
            existing = node.get(part)
            if existing is None:
                existing = node[part] = {}
            elif not isinstance(existing, dict):
                raise ScaffoldError(
                    "--set %s conflicts with an earlier --set: '%s' is already a value, "
                    "not a section." % (raw, ".".join(parts[: i + 1])),
                    field=dotted,
                )
            node = existing

        leaf = parts[-1]
        if isinstance(node.get(leaf), dict):
            raise ScaffoldError(
                "--set %s conflicts with an earlier --set nested under '%s'." % (raw, dotted),
                field=dotted,
            )
        node[leaf] = value
    return overrides


def resolve_baseline(extends):
    """The config this agent inherits, or a ScaffoldError naming why not."""
    try:
        resolved, _provenance, _chain = resolve_config.resolve_chain(
            resolve_config.expand(extends)
        )
        return resolved
    except resolve_config.ResolveError as exc:
        raise ScaffoldError(
            "the baseline did not resolve (%s)." % exc,
            field="extends",
            fix="Fix the extends path.",
        )


def dotted_get(node, dotted):
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def seed_process(extends, overrides):
    """
    The process steps a new agent starts from, taken from its pattern.

    Scaffolding, not intent. "Confirm the inputs" and "check the result
    against the constraints" are properties of the pattern, so the toolkit can
    write them; what the agent actually does is the user's and stays marked
    `TODO:`. Seeding happens once, at creation — the Process section is the
    user's from then on, and no later render touches it.
    """
    resolved = resolve_baseline(extends)
    pattern = dotted_get(overrides, PATTERN_PATH) or dotted_get(resolved, PATTERN_PATH) \
        or "standalone"

    path = os.path.join(PATTERN_LIBRARY, "%s.md" % pattern)
    if not os.path.isfile(path):
        # A pattern with no skeleton yet still gets a usable agent.
        path = os.path.join(PATTERN_LIBRARY, "standalone.md")

    # The body only. A module's frontmatter is metadata for the toolkit, not
    # instructions for the agent, and inlining it verbatim would put a YAML
    # block at the top of the user's Process section.
    try:
        skeleton = module_utils.parse(path, expected_kind="pattern")["body"]
    except module_utils.ModuleError as exc:
        cli_output.print_envelope([cli_output.issue(
            "pattern module %s is malformed: %s" % (pattern, exc),
            field=PATTERN_PATH,
            fix="Fix the module under library/pattern/, or choose another pattern.",
        )])
        sys.exit(2)

    max_cycles = dotted_get(overrides, MAX_CYCLES_PATH)
    if max_cycles is None:
        max_cycles = dotted_get(resolved, MAX_CYCLES_PATH)
    skeleton = skeleton.replace("{{MAX_CYCLES}}", str(max_cycles or 3))
    return pattern, skeleton


def inherited_capabilities(extends):
    """
    The capability list this agent would inherit if it overrode nothing.

    Needed because arrays replace wholesale (D4): "the baseline's set, minus
    web" cannot be written as a delta, only as the whole list. Returns None
    when the baseline does not set capabilities at all.
    """
    resolved = resolve_baseline(extends)
    granted = dotted_get(resolved, CAPABILITIES_PATH)
    return list(granted) if isinstance(granted, list) else None


def apply_web_flags(overrides, extends, want_web):
    """
    Turn --web / --no-web into a full `capabilities` override.

    Writing only the two web entries would be a silent capability wipe: the
    array replaces the inherited one, so an agent asked for "no web" would
    also lose the file access nobody mentioned. So the whole set is written.

    Returns (info, warnings). No override is written when the result matches
    what the agent already inherits — restating a baseline value pins the
    field against future baseline edits, which is what D3 and the validator's
    hygiene warning exist to prevent.
    """
    warnings = []
    inherited = inherited_capabilities(extends)

    if inherited is None:
        warnings.append(cli_output.issue(
            "the baseline grants no capabilities, so %s produced a set containing "
            "only what it named." % ("--web" if want_web else "--no-web"),
            field=CAPABILITIES_PATH,
        ))
        inherited = []

    if want_web:
        effective = list(inherited) + [
            capability for capability in WEB_CAPABILITIES if capability not in inherited
        ]
    else:
        effective = [
            capability for capability in inherited if capability not in WEB_CAPABILITIES
        ]

    added = [c for c in effective if c not in inherited]
    removed = [c for c in inherited if c not in effective]
    flag = "--web" if want_web else "--no-web"

    info = {
        "effective": effective,
        "inherited": inherited,
        "added": added,
        "removed": removed,
        "source": flag if (added or removed) else "baseline (unchanged)",
    }

    if not added and not removed:
        # Nothing to say that the baseline does not already say.
        return info, warnings

    node = overrides
    parts = CAPABILITIES_PATH.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = effective
    return info, warnings


def template_manifest():
    """Relative paths (forward-slash, sorted) of every file in templates/agent/."""
    if not os.path.isdir(TEMPLATE_DIR):
        raise ScaffoldError("Template directory not found: %s" % TEMPLATE_DIR)

    files = []
    for root, _dirs, filenames in os.walk(TEMPLATE_DIR):
        for filename in filenames:
            rel = os.path.relpath(os.path.join(root, filename), TEMPLATE_DIR)
            files.append(rel.replace(os.sep, "/"))
    files.sort()
    return files + GENERATED_FILES


def render_agent_yaml(name, description, extends, overrides):
    doc = {
        "schema_version": 2,
        "extends": extends,
        "name": name,
        "description": description,
    }
    doc.update(overrides)
    body = yaml.safe_dump(doc, sort_keys=False, default_flow_style=False).rstrip("\n")
    return AGENT_YAML_HEADER + body + "\n"


def write_agent_directory(target, name, description, extends, overrides, manifest,
                          process=""):
    """
    Write the agent directory, and return (written, preserved).

    Toolkit-owned files are always written. Anything else is created only if
    it isn't there already, so re-scaffolding over an existing agent leaves
    the user's own work alone. Nothing is ever deleted.
    """
    os.makedirs(target, exist_ok=True)
    written, preserved = [], []

    for rel_path in manifest:
        if rel_path in GENERATED_FILES:
            continue          # render-agent.py writes these, not the copy loop

        dst = os.path.join(target, *rel_path.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        if os.path.exists(dst) and rel_path not in TOOLKIT_OWNED:
            preserved.append(rel_path)
            continue

        if rel_path == "agent.yaml":
            content = render_agent_yaml(name, description, extends, overrides)
        else:
            src = os.path.join(TEMPLATE_DIR, *rel_path.split("/"))
            with open(src, "r", encoding="utf-8") as fh:
                content = fh.read()
            content = (
                content.replace("{{AGENT_NAME}}", name)
                .replace("{{AGENT_DESCRIPTION}}", description)
                .replace("{{PROCESS}}", process)
            )

        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(content)

        # Copy the template's mode, or run.sh arrives non-executable and
        # `./run.sh` — the thing the agent's README tells you to type — fails.
        src = os.path.join(TEMPLATE_DIR, *rel_path.split("/"))
        if os.path.isfile(src):
            shutil.copymode(src, dst)

        written.append(rel_path)

    return written, preserved


def run_render(agent_dir):
    """
    Compile the resolved config into the artefacts a runtime reads: the
    generated region of CLAUDE.md, and the tool permissions. Without this an
    agent's config is decorative — see TODO 4.2 and 5.1.
    """
    result = subprocess.run(
        [sys.executable, RENDER_SCRIPT, agent_dir, "--json"],
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except ValueError:
        message = (result.stdout + result.stderr).strip() or "render-agent.py produced no output"
        return cli_output.envelope(
            [cli_output.issue("render-agent.py failed: %s" % message)]
        )


def run_validation(agent_yaml_path):
    """
    Validate the freshly written agent.yaml and return the envelope
    validate-agent.py --json produced, unchanged — its errors and warnings
    become this script's own, so a caller sees why `ok` is false without
    reaching into a nested result.
    """
    result = subprocess.run(
        [sys.executable, VALIDATE_SCRIPT, agent_yaml_path, "--json"],
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except ValueError:
        # The validator itself crashed before emitting JSON — surface that
        # rather than a JSON parse traceback.
        message = (result.stdout + result.stderr).strip() or "validate-agent.py produced no output"
        return cli_output.envelope(
            [cli_output.issue("validate-agent.py failed: %s" % message)]
        )


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold a new agent directory from templates/agent/."
    )
    parser.add_argument("--name", required=True, help="Agent slug; becomes the directory name")
    parser.add_argument(
        "--dest",
        help="Parent directory to create the agent in (default: $AGENT_TOOLKIT_HOME/agents)",
    )
    parser.add_argument("--description", default="", help="One line on what this agent does")
    parser.add_argument(
        "--extends",
        help="Path to the baseline this agent inherits from "
        "(default: ~/.agent-toolkit/baseline.yaml, or $AGENT_TOOLKIT_HOME/baseline.yaml)",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        dest="set_args",
        metavar="KEY.PATH=VALUE",
        help="Set an override field (repeatable)",
    )
    web_group = parser.add_mutually_exclusive_group()
    web_group.add_argument(
        "--web", dest="web", action="store_true", default=None,
        help="Grant web.search and web.fetch, keeping every inherited capability",
    )
    web_group.add_argument(
        "--no-web", dest="web", action="store_false",
        help="Withhold web.search and web.fetch, keeping every other capability",
    )
    parser.add_argument(
        "--compose", action="append", default=[], metavar="KIND/NAME",
        help="Compose a library module, as role/x or routine/x (repeatable)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing agent directory")
    parser.add_argument(
        "--merge", action="store_true",
        help="Apply the change on top of the agent's existing overrides, rather "
             "than replacing them. Implies --force.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the file manifest; write nothing"
    )
    args = parser.parse_args()

    try:
        validate_name(args.name)

        dest_abs = expand(args.dest) if args.dest else expand(default_dest())
        target = os.path.join(dest_abs, args.name)

        # Defence in depth: the slug pattern already forbids "/" and "..",
        # but never write anywhere the destination doesn't actually contain.
        if os.path.dirname(os.path.normpath(target)) != os.path.normpath(dest_abs):
            raise ScaffoldError("Refusing to write outside the destination: %s" % target)

        if args.merge:
            args.force = True

        if os.path.exists(target) and not args.force:
            raise ScaffoldError(
                "Agent directory already exists: %s (use --force to overwrite)" % target,
                fix="Pass --force to overwrite, or choose a different name.",
            )

        requested = build_overrides(args.set_args)
        overrides = (
            deep_merge(existing_overrides(target), requested)
            if args.merge else requested
        )
        extends = args.extends if args.extends else default_extends()

        capabilities_info, web_warnings = None, []
        if args.web is not None:
            if any(arg.split("=", 1)[0].strip() == CAPABILITIES_PATH
                   for arg in args.set_args):
                raise ScaffoldError(
                    "--%sweb and --set %s both set the capability list. Use one or "
                    "the other." % ("" if args.web else "no-", CAPABILITIES_PATH),
                    field=CAPABILITIES_PATH,
                    fix="Drop the --set, or drop the web flag.",
                )
            capabilities_info, web_warnings = apply_web_flags(
                overrides, extends, args.web
            )

        if args.compose:
            if any(arg.split("=", 1)[0].strip() == COMPOSE_PATH for arg in args.set_args):
                raise ScaffoldError(
                    "--compose and --set compose both set the composed module list. "
                    "Use one or the other.",
                    field=COMPOSE_PATH,
                    fix="Drop the --set, or drop --compose.",
                )
            for reference in args.compose:
                if reference.startswith("pattern/"):
                    raise ScaffoldError(
                        "--compose %s: patterns are not composed. Set "
                        "operating_constraints.pattern instead — naming a pattern in "
                        "two places is two ways for them to disagree." % reference,
                        field=COMPOSE_PATH,
                        fix="Use --set operating_constraints.pattern=%s"
                            % reference.split("/", 1)[1],
                    )
            # Arrays replace (D4), so --compose under --merge sets the whole
            # list rather than adding to it. That is the same rule everywhere
            # else in the toolkit, and the alternative — appending — is how an
            # agent ends up composing something nobody chose.
            overrides[COMPOSE_PATH] = list(args.compose)

        pattern, process = seed_process(extends, overrides)
        manifest = template_manifest()

    except ScaffoldError as exc:
        cli_output.print_envelope([cli_output.issue(str(exc), field=exc.field, fix=exc.fix)])
        return 1

    data = {
        "name": args.name,
        "target": target,
        "extends": extends,
        "description": args.description,
        "overrides": overrides,
        "files": manifest,
        "dry_run": args.dry_run,
    }
    data["pattern"] = pattern
    if capabilities_info is not None:
        data["capabilities"] = capabilities_info

    if args.dry_run:
        cli_output.print_envelope([], web_warnings, data)
        return 0

    try:
        written, preserved = write_agent_directory(
            target, args.name, args.description, extends, overrides, manifest, process
        )
    except OSError as exc:
        cli_output.print_envelope(
            [cli_output.issue("Could not write agent directory: %s" % exc)], data=data
        )
        return 2

    data["written"] = written
    data["preserved"] = preserved

    validation = run_validation(os.path.join(target, "agent.yaml"))
    data["validation"] = validation

    # Render only against a config that validated. Permissions built from a
    # config with an illegal capability in it would be wrong in the one
    # direction that matters.
    if validation["ok"]:
        render = run_render(target)
        data["render"] = render
        if render["ok"]:
            data["permissions"] = render["data"]["permissions"]
        errors = render["errors"]
        warnings = validation["warnings"] + render["warnings"]
        ok = render["ok"]
    else:
        errors = validation["errors"]
        warnings = validation["warnings"]
        ok = False

    cli_output.print_envelope(errors, web_warnings + warnings, data)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
