#!/usr/bin/env python3
"""
agent-status.py — what you have built, and whether any of it has drifted.

This is what reconciles a rendered artefact with inheritance by reference
(D2, D11). Agents read their baseline at runtime, but `CLAUDE.md` is rendered
once — so a baseline edit reaches an agent's *config* immediately and its
*rendered instructions* not at all. Without something that says so, the
toolkit has quietly become the copy-at-creation system the design exists to
avoid.

Reports per agent:

    overrides    what it pins, and therefore what a baseline edit will not reach
    valid        does agent.yaml still resolve and validate
    rendered     is CLAUDE.md in step with the config it would render from now
    finished     has anyone written its process, or is the seeded TODO: still there

Usage:
    agent-status.py [--dest <dir>] [--json]

Exit codes:
    0  reported — including when agents are stale or invalid; saying so IS the job
    2  the agents directory could not be read
"""

import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(BUILDER_DIR))
VALIDATE_SCRIPT = os.path.join(SCRIPT_DIR, "validate-agent.py")

sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import cli_output  # noqa: E402


def _load(name, filename):
    from importlib import util
    spec = util.spec_from_file_location(name, os.path.join(SCRIPT_DIR, filename))
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    resolve_config = _load("resolve_config", "resolve-config.py")
    render_agent = _load("render_agent", "render-agent.py")
except Exception as exc:  # pragma: no cover
    print("ERROR: could not load a sibling script: %s" % exc)
    sys.exit(2)

IDENTITY_KEYS = {"schema_version", "extends", "name", "description"}


def default_dest():
    home = os.environ.get("AGENT_TOOLKIT_HOME", os.path.expanduser("~/.agent-toolkit"))
    return os.path.join(home, "agents")


def flatten(node, prefix=""):
    out = []
    for key, value in (node or {}).items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            out.extend(flatten(value, dotted))
        else:
            out.append(dotted)
    return out


def inspect(agent_dir):
    """Everything worth knowing about one agent, without changing it."""
    import yaml

    name = os.path.basename(agent_dir.rstrip(os.sep))
    agent_yaml = os.path.join(agent_dir, "agent.yaml")
    report = {
        "name": name,
        "path": agent_dir,
        "description": None,
        "overrides": [],
        "valid": None,
        "errors": 0,
        "warnings": 0,
        "rendered": None,     # True fresh, False stale, None never rendered
        "finished": None,
    }

    try:
        with open(agent_yaml, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError):
        report["valid"] = False
        report["errors"] = 1
        return report

    report["description"] = data.get("description")
    report["overrides"] = sorted(
        flatten({k: v for k, v in data.items() if k not in IDENTITY_KEYS})
    )

    result = subprocess.run(
        [sys.executable, VALIDATE_SCRIPT, agent_yaml, "--json"],
        capture_output=True, text=True,
    )
    try:
        envelope = json.loads(result.stdout)
        report["valid"] = envelope["ok"]
        report["errors"] = len(envelope["errors"])
        report["warnings"] = len(envelope["warnings"])
        report["finished"] = not any(
            "TODO:" in warning["message"] for warning in envelope["warnings"]
        )
    except ValueError:
        report["valid"] = False
        report["errors"] = 1

    # Render freshness: what the config hashes to now, against what the
    # rendered region says it was built from.
    claude_md = os.path.join(agent_dir, "CLAUDE.md")
    if os.path.isfile(claude_md):
        try:
            resolved, _p, _c = resolve_config.resolve_chain(agent_yaml)
            with open(claude_md, "r", encoding="utf-8") as fh:
                found = render_agent.current_hash(fh.read())
            if found in (None, "unrendered"):
                report["rendered"] = None
            else:
                report["rendered"] = found == render_agent.config_hash(resolved)
        except resolve_config.ResolveError:
            report["rendered"] = None

    return report


def render_table(reports):
    if not reports:
        return "No agents yet. Create one with /create-agent."

    width = max(len(r["name"]) for r in reports)
    lines = ["%-*s  %-9s  %-9s  %-10s  %s"
             % (width, "AGENT", "VALID", "RENDERED", "FINISHED", "OVERRIDES")]
    for report in reports:
        rendered = {True: "fresh", False: "STALE", None: "never"}[report["rendered"]]
        finished = {True: "yes", False: "TODO left", None: "-"}[report["finished"]]
        valid = "yes" if report["valid"] else "NO"
        if report["valid"] and report["warnings"]:
            valid = "%d warn" % report["warnings"]
        lines.append("%-*s  %-9s  %-9s  %-10s  %s" % (
            width, report["name"], valid, rendered, finished,
            ", ".join(report["overrides"]) or "none (tracks the baseline)",
        ))

    stale = [r["name"] for r in reports if r["rendered"] is False]
    if stale:
        lines.append("")
        lines.append(
            "%d stale: the baseline has moved on since these were rendered. "
            "Re-render with render-agent.py <agent-dir>." % len(stale)
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Report on every agent you have built.")
    parser.add_argument("--dest", help="Agents directory (default: $AGENT_TOOLKIT_HOME/agents)")
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    args = parser.parse_args()

    dest = args.dest or default_dest()

    if not os.path.isdir(dest):
        data = {"dest": dest, "agents": []}
        if args.json:
            cli_output.print_envelope([], [], data)
        else:
            print("No agents directory at %s yet. Create one with /create-agent." % dest)
        return 0

    try:
        # Shared with the renderer so "which directories are agents" has one
        # answer; a status report that disagrees with what --all renders would
        # be worse than either alone.
        directories = render_agent.iter_agent_dirs(dest)
    except OSError as exc:
        return cli_output.fail("could not read %s: %s" % (dest, exc), args.json)

    reports = [inspect(directory) for directory in directories]

    warnings = []
    stale = [r["name"] for r in reports if r["rendered"] is False]
    if stale:
        warnings.append(cli_output.issue(
            "%s rendered from an older configuration. A baseline edit reaches an "
            "agent's config immediately but its rendered CLAUDE.md not at all, so "
            "these are running on out-of-date instructions."
            % ", ".join(stale),
            fix="Re-render with: render-agent.py <agent-dir>",
        ))

    data = {"dest": dest, "agents": reports,
            "counts": {
                "total": len(reports),
                "invalid": len([r for r in reports if not r["valid"]]),
                "stale": len(stale),
                "unfinished": len([r for r in reports if r["finished"] is False]),
            }}

    if args.json:
        cli_output.print_envelope([], warnings, data)
        return 0

    print(render_table(reports))
    return 0


if __name__ == "__main__":
    sys.exit(main())
