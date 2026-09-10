#!/usr/bin/env python3
"""
resolve-config.py — resolve an agent's effective configuration.

Merges the precedence layers and reports where every value came from:

    1. Baseline profile      ~/.agent-toolkit/baseline.yaml       lowest
    2. Agent override        <agent-dir>/agent.yaml
    3. CLI flag              --set model=claude-opus-5
    4. In-session            (applied by the runtime, not here)   highest

Merge rules (see docs/precedence-and-inheritance.md):
  - Higher wins for the field it sets, and ONLY that field
  - Nested maps merge at the leaf; sibling keys survive
  - Arrays REPLACE wholesale — never appended. Silently merging permission
    arrays is how an agent ends up with access nobody granted it.

Usage:
    resolve-config.py <agent.yaml>                  # resolved config as YAML
    resolve-config.py <agent.yaml> --explain        # with provenance per line
    resolve-config.py <agent.yaml> --set a.b=c      # apply a CLI-layer override
    resolve-config.py --baseline-only [--summary]   # just the baseline
    resolve-config.py <agent.yaml> --json           # the cli_output envelope

Exit codes:
    0  resolved
    1  resolution error (missing baseline, cyclic extends, bad --set)
    2  file missing or unparseable
"""

import argparse
import os
import sys

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(BUILDER_DIR)), "scripts"))

try:
    import cli_output
except ImportError as exc:  # pragma: no cover
    print("ERROR: could not import scripts/cli_output.py: %s" % exc, file=sys.stderr)
    sys.exit(2)

MAX_EXTENDS_DEPTH = 10

# Keys whose values are arrays that must replace rather than merge.
# Listed explicitly rather than inferred, so the behaviour is auditable.
REPLACE_ARRAYS = {
    "operating_constraints.permissions_scope.capabilities",
    "knowledge_memory.default_context_sources",
    "compose",
}


def expand(path):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def load_yaml(path, label):
    if not os.path.isfile(path):
        raise ResolveError("%s not found: %s" % (label, path))
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ResolveError("%s is not valid YAML (%s):\n%s" % (label, path, exc))
    if not isinstance(data, dict):
        raise ResolveError("%s root must be a mapping, found %s" % (label, type(data).__name__))
    return data


class ResolveError(Exception):
    pass


def merge(base, overlay, provenance, source_label, prefix=""):
    """
    Deep-merge overlay onto base. Mutates and returns base.
    Records the winning source for every leaf in `provenance`.
    """
    for key, value in overlay.items():
        dotted = "%s.%s" % (prefix, key) if prefix else key

        if isinstance(value, dict) and isinstance(base.get(key), dict):
            # Nested map: recurse so sibling keys survive.
            merge(base[key], value, provenance, source_label, dotted)
        else:
            # Scalar, list, or a map replacing a non-map: overlay wins outright.
            base[key] = value
            provenance[dotted] = source_label
            if isinstance(value, dict):
                # Whole subtree came from this source.
                for sub in flatten_keys(value, dotted):
                    provenance[sub] = source_label
    return base


def flatten_keys(node, prefix=""):
    keys = []
    for key, value in node.items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            keys.extend(flatten_keys(value, dotted))
        else:
            keys.append(dotted)
    return keys


def resolve_chain(agent_path):
    """
    Walk the extends chain from the agent file down to the root baseline,
    then merge back up. Returns (resolved, provenance, chain).
    """
    chain = []
    current_path = expand(agent_path)
    seen = set()

    while True:
        if current_path in seen:
            raise ResolveError(
                "Cyclic `extends` chain detected at %s. A profile cannot extend itself, "
                "directly or transitively." % current_path
            )
        seen.add(current_path)

        if len(chain) > MAX_EXTENDS_DEPTH:
            raise ResolveError(
                "`extends` chain deeper than %d levels. This is almost certainly a mistake."
                % MAX_EXTENDS_DEPTH
            )

        label = "baseline" if not chain else os.path.basename(os.path.dirname(current_path))
        data = load_yaml(current_path, "Profile")
        chain.append((current_path, data))

        parent = data.get("extends")
        if not parent:
            break
        current_path = expand(parent)

    # chain is [agent, ..., baseline]. Merge from baseline upward.
    resolved = {}
    provenance = {}
    for path, data in reversed(chain):
        is_baseline = path == chain[-1][0]
        source = "baseline" if is_baseline else "agent (%s)" % os.path.basename(os.path.dirname(path))
        payload = {k: v for k, v in data.items() if k != "extends"}
        merge(resolved, payload, provenance, source)

    return resolved, provenance, [p for p, _ in chain]


def apply_cli_sets(resolved, provenance, assignments):
    for assignment in assignments:
        if "=" not in assignment:
            raise ResolveError("--set expects key.path=value, got: %s" % assignment)
        dotted, raw = assignment.split("=", 1)
        dotted = dotted.strip()
        # Interpret the value as YAML so booleans/ints/lists work naturally.
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError:
            value = raw

        parts = dotted.split(".")
        node = resolved
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        provenance[dotted] = "CLI flag"
    return resolved, provenance


def render_explained(resolved, provenance, prefix="", indent=0, lines=None):
    if lines is None:
        lines = []
    pad = "  " * indent
    for key, value in resolved.items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            lines.append("%s%s:" % (pad, key))
            render_explained(value, provenance, dotted, indent + 1, lines)
        else:
            source = provenance.get(dotted, "baseline")
            rendered = yaml.safe_dump(
                value, default_flow_style=True, width=10**6
            ).replace("\n...", "").strip()
            entry = "%s%s: %s" % (pad, key, rendered)
            lines.append("%-58s # %s" % (entry, source))
    return lines


def summarise(resolved):
    def get(path, default="—"):
        node = resolved
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    return "\n".join([
        "  domain:     %s" % get("identity_context.domain"),
        "  audience:   %s" % get("identity_context.audience"),
        "  tone:       %s" % get("voice_style.tone_of_voice"),
        "  verbosity:  %s" % get("voice_style.verbosity"),
        "  model:      %s" % get("operating_constraints.model"),
        "  pattern:    %s" % get("operating_constraints.pattern"),
        "  output:     %s" % get("interop.output_location"),
    ])


def main():
    parser = argparse.ArgumentParser(description="Resolve an agent's effective configuration.")
    parser.add_argument("agent", nargs="?", help="Path to agent.yaml")
    parser.add_argument("--baseline-only", action="store_true", help="Resolve the baseline alone")
    parser.add_argument("--explain", action="store_true", help="Annotate each value with its source")
    parser.add_argument("--summary", action="store_true", help="Print a short human summary")
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="Apply a CLI-layer override (repeatable)")
    args = parser.parse_args()

    try:
        if args.baseline_only:
            home = os.environ.get("AGENT_TOOLKIT_HOME", os.path.expanduser("~/.agent-toolkit"))
            target = os.path.join(home, "baseline.yaml")
        elif args.agent:
            target = args.agent
        else:
            parser.error("give an agent.yaml path, or use --baseline-only")

        resolved, provenance, chain = resolve_chain(target)
        resolved, provenance = apply_cli_sets(resolved, provenance, args.set)

    except ResolveError as exc:
        # Field is "extends" even for a bad --set: both are about which layer
        # won, and there's no single leaf at fault the way a validator's
        # per-field checks have.
        if args.json:
            cli_output.print_envelope([cli_output.issue(str(exc), field="extends")], [], {})
        else:
            print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    if args.summary:
        print("Inherited configuration:")
        print(summarise(resolved))
        return 0

    if args.json:
        cli_output.print_envelope(
            data={"resolved": resolved, "provenance": provenance, "chain": chain}
        )
        return 0

    if args.explain:
        print("# Resolution chain (lowest precedence first):")
        for path in reversed(chain):
            print("#   %s" % path)
        if args.set:
            print("#   <CLI flags>")
        print()
        print("\n".join(render_explained(resolved, provenance)))
        return 0

    print(yaml.safe_dump(resolved, sort_keys=False, default_flow_style=False).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
