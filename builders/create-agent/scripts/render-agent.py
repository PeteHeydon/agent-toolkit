#!/usr/bin/env python3
"""
render-agent.py — compile a resolved config into the artefacts a runtime reads.

Two outputs, both inside the agent's own directory and never a parent's,
including under `--path`:

    CLAUDE.md               the generated region — the only artefact that
                            reaches the model
    .claude/settings.json   tool permissions, from the capability set

One script rather than two because both start from the same resolved config
and the same question: is this agent still in step with its baseline? Two
renderers would mean two config hashes and two answers to that, which is how
an agent ends up half-stale with nothing to say so.

**Structure first, markdown second** (D18). `build_sections()` assembles the
generated region as data — each section naming the config fields it came from
— and the markdown is one renderer over that. A host that cannot use
`CLAUDE.md` assembles its own prompt from `--json` instead of parsing prose.

**Render a line only where it changes behaviour** (D13). Identity, voice,
capability limits and the output contract always render; anything sitting at
its schema default renders nothing, because a line saying `input_filtering:
true` spends tokens to describe behaviour a competent agent already has.

Usage:
    render-agent.py <agent-dir> [--stdout] [--check] [--json] [--runtime <path>]
    render-agent.py --all [--check] [--json]

`--all` walks $AGENT_TOOLKIT_HOME/agents/ and does not stop at the first
failure: one agent whose baseline has gone missing should not prevent the
other nine being brought back into step.

It always renders both artefacts. There is deliberately no way to render one
without the other: they share a config hash, and a half-rendered agent would
have two records of what it was built from and no way to say which is right.

Exit codes:
    0  rendered, or --check found the agent in step with its config
    1  logic error, or --check found it stale
    2  missing or unreadable input
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(2)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(BUILDER_DIR))
DEFAULT_RUNTIME = os.path.join(REPO_ROOT, "runtimes", "claude-code.yaml")
BASELINE_SCHEMA = os.path.join(
    REPO_ROOT, "builders", "bootstrap-agent", "schema", "baseline-profile.schema.json"
)

sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

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

import cli_output  # noqa: E402
import module_utils  # noqa: E402
import schema_utils  # noqa: E402

RENDER_VERSION = "render:v1"
BEGIN_PATTERN = re.compile(
    r"<!-- BEGIN GENERATED render:[^\s]+ config-hash:([^\s]+) -->"
)
END_MARKER = "<!-- END GENERATED -->"

SETTINGS_PATH = os.path.join(".claude", "settings.json")
RENDER_STATE_PATH = os.path.join(".agent", "render.json")

# Target and hard warning for the generated region, per D13. Long enough to
# personalise an agent, short enough that nobody stops reading it.
TARGET_LINES = 80
WARN_LINES = 150

# What each capability means in prose. Capability names are toolkit
# vocabulary, not runtime vocabulary, so the phrasing belongs here rather
# than in runtimes/*.yaml — every runtime renders the same sentence.
CAPABILITY_PHRASES = {
    "file.read": "read files",
    "file.search": "search across files",
    "file.write": "create and edit files",
    "shell": "run shell commands",
    "web.search": "search the web",
    "web.fetch": "fetch web pages",
    "subagent": "delegate work to subagents",
}

FILESYSTEM_LIMITS = {
    "workspace_only": "Work inside this agent's own directory. Do not write elsewhere.",
    "read_only": "You may read the filesystem but not change it.",
    "full": None,     # no restriction worth a line
}

# Guardrails, rendered only when they differ from the schema default.
GUARDRAIL_PHRASES = {
    "operating_constraints.guardrails.human_in_the_loop": {
        True: "Pause and ask for approval before any irreversible action.",
        False: "Do not pause for approval; the user has not asked to gate actions.",
    },
    "operating_constraints.guardrails.output_validation": {
        True: "Check your output against the contract below before returning it.",
        False: None,
    },
    "operating_constraints.guardrails.tool_use_limits": {
        "strict": "Keep tool use to the minimum the task needs.",
        "none": "There is no ceiling on tool use.",
    },
    "operating_constraints.guardrails.input_filtering": {
        False: "Input filtering is off for this agent.",
    },
}


def agents_root():
    home = os.environ.get("AGENT_TOOLKIT_HOME", os.path.expanduser("~/.agent-toolkit"))
    return os.path.join(home, "agents")


def iter_agent_dirs(root=None):
    """Every directory under the agents root that actually holds an agent."""
    root = root or agents_root()
    if not os.path.isdir(root):
        return []
    return [
        os.path.join(root, entry) for entry in sorted(os.listdir(root))
        if os.path.isfile(os.path.join(root, entry, "agent.yaml"))
    ]


def config_hash(resolved):
    """Stable across machines and runs: sorted keys, no timestamp."""
    payload = json.dumps(resolved, sort_keys=True, separators=(",", ":"))
    return "sha256:%s" % hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def get(resolved, dotted, default=None):
    node = resolved
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def section(id_, heading, fields, lines):
    return {"id": id_, "heading": heading, "fields": fields, "lines": [l for l in lines if l]}


def compose_sections(resolved):
    """
    Composed module bodies, inlined.

    Inlined rather than linked so the agent directory stays self-contained and
    portable to a runtime that has never heard of this toolkit (D14). Returns
    (section or None, errors) — a module that cannot be loaded is an error
    here rather than a silent omission, because an agent quietly missing the
    guidance it was built around is the failure this library exists to fix.
    """
    references = get(resolved, "compose", []) or []
    if not references:
        return None, []

    lines, errors = [], []
    for reference in references:
        try:
            module = module_utils.load(reference)
        except module_utils.ModuleError as exc:
            errors.append(cli_output.issue(
                "compose: %s" % exc, field="compose", fix=exc.fix,
            ))
            continue
        if lines:
            lines.append("")
        lines.append("### %s" % module["id"])
        lines.extend(module["body"].splitlines())

    if errors or not lines:
        return None, errors

    return section("composed", "Composed modules", ["compose"], lines), errors


def build_sections(resolved, defaults):
    """
    The generated region as structure. Each section names the config fields it
    was built from, so a consumer can trace any line back to what produced it.
    """
    sections = []

    def differs(dotted):
        """True when the resolved value is not the schema's default."""
        return dotted in defaults and get(resolved, dotted) != defaults[dotted]

    # --- Operating context -------------------------------------------------
    domain = get(resolved, "identity_context.domain")
    audience = get(resolved, "identity_context.audience")
    locale = get(resolved, "identity_context.locale")
    lines = []
    if domain:
        lines.append("You work in %s." % domain)
    if audience:
        phrase = audience.replace("_", " ")
        lines.append("Your output is for %s %s audience." % (article(phrase), phrase))
    if locale:
        lines.append("Use %s spelling, date and currency conventions." % locale)
    fields = ["identity_context.domain", "identity_context.audience",
              "identity_context.locale"]

    sources = get(resolved, "knowledge_memory.default_context_sources", []) or []
    if sources:
        fields.append("knowledge_memory.default_context_sources")
        lines.append("Load these on start: %s." % ", ".join("`%s`" % s for s in sources))
    if differs("knowledge_memory.memory_behaviour"):
        fields.append("knowledge_memory.memory_behaviour")
        if get(resolved, "knowledge_memory.memory_behaviour") == "persistent":
            lines.append("You keep state across runs; earlier runs are context for this one.")
    if differs("operating_constraints.safety_compliance_profile"):
        fields.append("operating_constraints.safety_compliance_profile")
        lines.append("Follow the %s compliance profile."
                     % get(resolved, "operating_constraints.safety_compliance_profile"))

    sections.append(section("operating_context", "Operating context", fields, lines))

    # --- Voice --------------------------------------------------------------
    tone = get(resolved, "voice_style.tone_of_voice")
    verbosity = get(resolved, "voice_style.verbosity")
    persona = get(resolved, "voice_style.persona")
    lines = []
    if tone:
        lines.append("Write in a %s register." % tone)
    if verbosity:
        lines.append({
            "concise": "Be concise. Prefer bullets to prose, and stop when the point is made.",
            "standard": "Give a normal amount of detail.",
            "expansive": "Explain fully, including the reasoning behind the answer.",
        }.get(verbosity, "Verbosity: %s." % verbosity))
    if persona == "named":
        lines.append("Keep a consistent named persona across runs.")

    fields = ["voice_style.tone_of_voice", "voice_style.verbosity"]
    for dotted, phrase in (
        ("voice_style.formatting_conventions.headers",
         "Do not use markdown headers."),
        ("voice_style.formatting_conventions.tables", None),
    ):
        if differs(dotted):
            fields.append(dotted)
            value = get(resolved, dotted)
            if dotted.endswith("headers") and value is False:
                lines.append(phrase)
            elif dotted.endswith("tables"):
                lines.append({
                    "always": "Use a table wherever the content is tabular.",
                    "never": "Do not use tables.",
                }.get(value))
    sections.append(section("voice", "Voice", fields, lines))

    # --- Capabilities and limits -------------------------------------------
    granted = get(resolved, "operating_constraints.permissions_scope.capabilities", []) or []
    withheld = [c for c in CAPABILITY_PHRASES if c not in granted]
    lines = []
    if granted:
        phrases = [CAPABILITY_PHRASES.get(c, c) for c in granted]
        lines.append("You can %s." % oxford(phrases))
    if withheld:
        # Stated negatively as well as positively: an agent that does not know
        # what it cannot do wastes a turn discovering it.
        lines.append("You cannot %s." % oxford(
            [CAPABILITY_PHRASES.get(c, c) for c in withheld], "or"
        ))

    posture = get(resolved, "operating_constraints.permissions_scope.filesystem")
    if posture in FILESYSTEM_LIMITS and FILESYSTEM_LIMITS[posture]:
        lines.append(FILESYSTEM_LIMITS[posture])

    blocked = get(
        resolved, "operating_constraints.permissions_scope.web.blocked_domains", []
    ) or []
    if blocked:
        lines.append("Do not fetch from: %s." % ", ".join(blocked))
    allowed = get(
        resolved, "operating_constraints.permissions_scope.web.allowed_domains", []
    ) or []
    if allowed:
        lines.append("Fetch only from: %s." % ", ".join(allowed))

    fields = ["operating_constraints.permissions_scope.capabilities",
              "operating_constraints.permissions_scope.filesystem"]
    for dotted, mapping in GUARDRAIL_PHRASES.items():
        if differs(dotted):
            phrase = mapping.get(get(resolved, dotted))
            if phrase:
                fields.append(dotted)
                lines.append(phrase)
    sections.append(section("capabilities", "Capabilities and limits", fields, lines))

    # --- Output -------------------------------------------------------------
    contract = get(resolved, "interop.output_format_contract")
    location = get(resolved, "interop.output_location")
    escalation = get(resolved, "interop.escalation_path")
    steering_file = get(resolved, "steering.bulk_feedback_file")
    lines = []
    if contract:
        lines.append({
            "markdown": "Return markdown, written for a person to read.",
            "json": "Return JSON only, with no prose around it.",
            "plain_text": "Return plain text, with no markup.",
            "file": "Write the result to a file rather than returning it inline.",
        }.get(contract, "Output format: %s." % contract))
    if location:
        lines.append("Write results to `%s`, not the project root." % location)
    if escalation:
        lines.append("When you hit a limit you cannot resolve, escalate to %s."
                     % escalation.replace("_", " "))
    if get(resolved, "steering.feedback_mode") == "chat_and_bulk" and steering_file:
        lines.append("When asked to apply standing guidance, read `%s` and follow it."
                     % steering_file)
    sections.append(section(
        "output", "Output",
        ["interop.output_format_contract", "interop.output_location",
         "interop.escalation_path", "steering.bulk_feedback_file"],
        lines,
    ))

    composed, compose_errors = compose_sections(resolved)
    if composed:
        sections.append(composed)

    return [s for s in sections if s["lines"]], compose_errors


def oxford(items, conjunction="and"):
    """
    Join a list for prose. Negative lists take "or": "you cannot X and Y"
    reads as a joint prohibition rather than two separate ones.
    """
    items = list(items)
    if len(items) == 1:
        return items[0]
    return "%s %s %s" % (", ".join(items[:-1]), conjunction, items[-1])


def article(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def render_markdown(sections, digest):
    """One renderer over the structure above. Never builds prose directly."""
    lines = ["<!-- BEGIN GENERATED %s config-hash:%s -->" % (RENDER_VERSION, digest),
             "<!-- Generated from agent.yaml and its baseline."
             " Do not edit inside these markers. -->"]
    for item in sections:
        lines.append("")
        lines.append("## %s" % item["heading"])
        lines.extend(item["lines"])
    lines.append("")
    lines.append(END_MARKER)
    return "\n".join(lines)


def replace_region(text, region):
    """
    Swap the marked region, leaving everything outside it byte for byte.

    A file with no markers gets the region inserted after its title block,
    so a hand-written CLAUDE.md is adopted rather than rejected.
    """
    begin = BEGIN_PATTERN.search(text)
    end = text.find(END_MARKER)

    if begin and end != -1 and end > begin.start():
        return text[:begin.start()] + region + text[end + len(END_MARKER):]

    if begin or end != -1:
        raise ValueError(
            "CLAUDE.md has only one of the two generated markers. Restore both, or "
            "delete the stray one, rather than letting a render guess where the "
            "region ends."
        )

    # No region yet: place it after the title and description.
    parts = text.split("\n\n", 2)
    if len(parts) >= 2:
        head = "\n\n".join(parts[:2])
        rest = parts[2] if len(parts) > 2 else ""
        return "%s\n\n%s\n\n%s" % (head, region, rest.lstrip("\n"))
    return "%s\n\n%s\n" % (text.rstrip("\n"), region)


def current_hash(text):
    match = BEGIN_PATTERN.search(text)
    return match.group(1) if match else None


# --------------------------------------------------------------------------
# Permissions — rendered in the same pass as the region above, from the same
# resolved config, so the two can never disagree about what built them.
# --------------------------------------------------------------------------

def render_permissions(resolved, runtime):
    errors = []
    mapping = runtime.get("capabilities") or {}
    high_consequence = set(runtime.get("high_consequence") or [])

    granted = get(
        resolved, "operating_constraints.permissions_scope.capabilities", []
    ) or []

    allow, covered = set(), set()
    for capability in granted:
        tools = mapping.get(capability)
        if tools is None:
            errors.append(cli_output.issue(
                "operating_constraints.permissions_scope.capabilities: %r has no mapping "
                "in this runtime. Known: %s" % (capability, ", ".join(sorted(mapping))),
                field="operating_constraints.permissions_scope.capabilities",
                legal=set(mapping),
                fix="Use a capability this runtime maps, or add it to the runtime file.",
            ))
            continue
        allow.update(tools)
        covered.update(tools)

    every_tool = {tool for tools in mapping.values() for tool in tools}
    deny = {tool for tool in every_tool - covered if tool in high_consequence}

    posture = get(
        resolved, "operating_constraints.permissions_scope.filesystem", "workspace_only"
    )
    posture_rules = (runtime.get("filesystem") or {}).get(posture)
    if posture_rules is None:
        errors.append(cli_output.issue(
            "operating_constraints.permissions_scope.filesystem: %r has no rule in this "
            "runtime." % posture,
            field="operating_constraints.permissions_scope.filesystem",
            legal=set((runtime.get("filesystem") or {})),
            fix="Use a posture this runtime defines.",
        ))
    else:
        deny.update(posture_rules.get("deny") or [])

    rule_form = runtime.get("web_domain_rule")
    if rule_form and "web.fetch" in granted:
        for domain in get(
            resolved, "operating_constraints.permissions_scope.web.allowed_domains", []
        ) or []:
            allow.add(rule_form.format(domain=domain))
        for domain in get(
            resolved, "operating_constraints.permissions_scope.web.blocked_domains", []
        ) or []:
            deny.add(rule_form.format(domain=domain))

    allow -= deny
    return {"permissions": {"allow": sorted(allow), "deny": sorted(deny)}}, errors


def render_all(args):
    """
    Render every agent, reporting per-agent outcomes.

    Deliberately does not stop at the first failure: one agent whose baseline
    has gone missing should not leave the other nine stale, and the report is
    more useful than the exit code.
    """
    directories = iter_agent_dirs()
    if not directories:
        data = {"agents": [], "root": agents_root()}
        if args.json:
            cli_output.print_envelope([], [], data)
        else:
            print("No agents under %s yet." % agents_root())
        return 0

    results, failed = [], 0
    for directory in directories:
        one = subprocess.run(
            [sys.executable, os.path.abspath(__file__), directory, "--json"]
            + (["--check"] if args.check else []),
            capture_output=True, text=True,
        )
        try:
            envelope = json.loads(one.stdout)
        except ValueError:
            envelope = cli_output.envelope([cli_output.issue(
                (one.stdout + one.stderr).strip() or "render produced no output")])

        ok = one.returncode == 0
        failed += 0 if ok else 1
        results.append({
            "name": os.path.basename(directory),
            "ok": ok,
            "stale": envelope.get("data", {}).get("stale"),
            "config_hash": envelope.get("data", {}).get("config_hash"),
            "errors": envelope.get("errors", []),
        })

    data = {"root": agents_root(), "agents": results,
            "counts": {"total": len(results), "failed": failed}}

    if args.json:
        cli_output.print_envelope([], [], data)
    else:
        verb = "checked" if args.check else "rendered"
        for result in results:
            mark = "ok" if result["ok"] else "FAILED"
            print("  %-24s %s" % (result["name"], mark))
            for error in result["errors"]:
                print("      %s" % error["message"])
        print("\n%d agent(s) %s, %d failed." % (len(results), verb, failed))

    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Render an agent's CLAUDE.md region and tool permissions."
    )
    parser.add_argument("agent_dir", nargs="?",
                        help="The agent directory (containing agent.yaml)")
    parser.add_argument("--all", action="store_true",
                        help="Every agent under $AGENT_TOOLKIT_HOME/agents/")
    parser.add_argument("--runtime", default=DEFAULT_RUNTIME, help="Runtime mapping file")
    parser.add_argument("--stdout", action="store_true",
                        help="Print the generated region; write nothing")
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero if the rendered region is stale")
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    args = parser.parse_args()

    if args.all:
        return render_all(args)
    if not args.agent_dir:
        parser.error("give an agent directory, or use --all")

    agent_yaml = os.path.join(args.agent_dir, "agent.yaml")
    if not os.path.isfile(agent_yaml):
        return cli_output.fail("no agent.yaml in %s" % args.agent_dir, args.json)
    if not os.path.isfile(args.runtime):
        return cli_output.fail("no runtime mapping at %s" % args.runtime, args.json)

    try:
        with open(args.runtime, "r", encoding="utf-8") as fh:
            runtime = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        return cli_output.fail(
            "could not parse %s as YAML:\n%s" % (args.runtime, exc), args.json)

    try:
        resolved, _provenance, _chain = resolve_config.resolve_chain(agent_yaml)
    except resolve_config.ResolveError as exc:
        if args.json:
            cli_output.print_envelope([cli_output.issue(str(exc), field="extends")])
        else:
            print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    defaults = schema_utils.extract_defaults(schema_utils.load_schema(BASELINE_SCHEMA))
    digest = config_hash(resolved)
    sections, compose_errors = build_sections(resolved, defaults)
    if compose_errors:
        if args.json:
            cli_output.print_envelope(compose_errors, [], {})
        else:
            cli_output.render_text(compose_errors, [])
        return 1
    region = render_markdown(sections, digest)

    warnings = []
    region_lines = len(region.splitlines())
    if region_lines > WARN_LINES:
        warnings.append(cli_output.issue(
            "the generated region is %d lines, past the %d-line warning threshold. "
            "Every line of it is read on every run — check that each one still "
            "changes behaviour." % (region_lines, WARN_LINES),
        ))

    claude_md_path = os.path.join(args.agent_dir, "CLAUDE.md")

    # --- --check: is the rendered region still in step with the config? ----
    if args.check:
        if not os.path.isfile(claude_md_path):
            return cli_output.fail("no CLAUDE.md in %s" % args.agent_dir, args.json)
        with open(claude_md_path, encoding="utf-8") as fh:
            existing = fh.read()
        found = current_hash(existing)
        fresh = found == digest
        data = {"agent_dir": os.path.abspath(args.agent_dir), "stale": not fresh,
                "config_hash": digest, "rendered_hash": found}
        if args.json:
            cli_output.print_envelope(
                [] if fresh else [cli_output.issue(
                    "CLAUDE.md was rendered from a different configuration "
                    "(%s, now %s). The baseline has moved on since." % (found, digest),
                    fix="Re-render with: render-agent.py %s" % args.agent_dir,
                )],
                warnings, data,
            )
        elif fresh:
            print("%s is up to date." % claude_md_path)
        else:
            print("STALE: %s was rendered from %s, config is now %s."
                  % (claude_md_path, found, digest))
        return 0 if fresh else 1

    if args.stdout:
        if args.json:
            cli_output.print_envelope([], warnings, {
                "sections": sections, "config_hash": digest,
                "markdown": region, "lines": region_lines,
            })
        else:
            print(region)
        return 0

    written = []

    existing = ""
    if os.path.isfile(claude_md_path):
        with open(claude_md_path, encoding="utf-8") as fh:
            existing = fh.read()
    else:
        existing = "# %s\n\n%s\n" % (
            get(resolved, "name", os.path.basename(os.path.abspath(args.agent_dir))),
            get(resolved, "description", "") or "",
        )
    try:
        updated = replace_region(existing, region)
    except ValueError as exc:
        if args.json:
            cli_output.print_envelope([cli_output.issue(str(exc))], warnings, {})
        else:
            print("ERROR: %s" % exc)
        return 1
    with open(claude_md_path, "w", encoding="utf-8") as fh:
        fh.write(updated)
    written.append("CLAUDE.md")

    settings, errors = render_permissions(resolved, runtime)
    if errors:
        if args.json:
            cli_output.print_envelope(errors, warnings, {})
        else:
            cli_output.render_text(errors, warnings)
        return 1
    dst = os.path.join(args.agent_dir, SETTINGS_PATH)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(settings, indent=2) + "\n")
    written.append(SETTINGS_PATH.replace(os.sep, "/"))
    permissions = settings["permissions"]

    # The same hash the CLAUDE.md marker carries, recorded where tooling can
    # read it without parsing markdown. Written in the same pass, so the two
    # cannot disagree. No timestamp: an unchanged config re-renders identically.
    state_path = os.path.join(args.agent_dir, RENDER_STATE_PATH)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"renderer": RENDER_VERSION, "config_hash": digest}, indent=2, sort_keys=True
        ) + "\n")
    written.append(RENDER_STATE_PATH.replace(os.sep, "/"))

    data = {
        "agent_dir": os.path.abspath(args.agent_dir),
        "runtime": runtime.get("runtime"),
        "config_hash": digest,
        "files": written,
        "sections": sections,
        "lines": region_lines,
    }
    data["permissions"] = permissions

    if args.json:
        cli_output.print_envelope([], warnings, data)
        return 0

    cli_output.render_text([], warnings)
    print("Rendered %s (%d lines, %s)" % (", ".join(written), region_lines, digest))
    if permissions:
        print("  allow: %s" % (", ".join(permissions["allow"]) or "—"))
        print("  deny:  %s" % (", ".join(permissions["deny"]) or "—"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
