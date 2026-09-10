#!/usr/bin/env python3
"""
describe-schema.py — emit the interview descriptor built into the schema.

Per D17, the schema is the single home for what to ask a user and what the
legal answers are. It carries that as `x-` extension keywords, which JSON
Schema ignores and `additionalProperties: false` doesn't constrain (that
constrains the *data*, not the schema document), so the whole thing is
additive.

    x-label       human name for the characteristic ("Tone of voice")
    x-group       which section of the interview it belongs to
    x-question    the prompt to ask; its presence is what makes a node asked
    x-help        the explanation, and the source of the README bullet
    x-express     asked in Express mode
    x-express-via names the composite that covers it in Express mode
    x-infer       an environment source for a field that is never asked
    x-internal    machinery, not a user characteristic (schema_version, extends)

Plus, at the schema root, `x-groups` (section order) and
`x-composite-questions` — one question whose answer sets several fields at
once, which is how "risk posture" covers both guardrails and permissions.

Three consumers read this one descriptor: the bootstrap interview, the
characteristics list in the builder README, and any future form.

Every leaf field must be **determinable** — inferred, carrying a default, or
asked by an Express question. Anything else can't be filled in an Express run,
so it's reported as an error rather than silently skipped.

Usage:
    describe-schema.py [--json] [--markdown] [--write [path]] [--schema <path>]

`--write` replaces the marked region in the builder README with the generated
characteristics list, so regenerating after a schema edit is one command.

Exit codes:
    0  descriptor is coherent
    1  descriptor has errors (an undeterminable field, a bad composite)
    2  schema missing or unparseable
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

import cli_output  # noqa: E402

DEFAULT_SCHEMA = os.path.join(
    REPO_ROOT, "builders", "bootstrap-agent", "schema", "baseline-profile.schema.json"
)
DEFAULT_README = os.path.join(REPO_ROOT, "builders", "bootstrap-agent", "README.md")

BEGIN_MARKER = "<!-- BEGIN GENERATED describe-schema -->"
END_MARKER = "<!-- END GENERATED -->"

# Tokens x-infer may name. A consumer maps these to actual detection; the
# descriptor only promises the field is never asked.
INFER_SOURCES = {"system_locale"}

SENTINEL = object()


def leaf_type(node):
    """A node with `properties` is a section; everything else is a leaf."""
    if "properties" in node:
        return None
    if node.get("type") == "object":
        return "map"
    node_type = node.get("type", "string")
    if isinstance(node_type, list):
        # e.g. ["string", "null"] — name the non-null half.
        non_null = [t for t in node_type if t != "null"]
        return non_null[0] if non_null else "null"
    return node_type


def declared_default(node):
    if "const" in node:
        return node["const"]
    return node.get("default", SENTINEL)


def walk(node, prefix="", inherited=None):
    """
    Yield (dotted_path, subschema, covering_characteristic) for every leaf.

    `covering_characteristic` is the nearest self-or-ancestor carrying
    x-question or x-infer — the thing an interview actually asks about.
    """
    for key, sub in (node.get("properties") or {}).items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        covering = inherited
        if sub.get("x-question") or sub.get("x-infer"):
            covering = dotted

        if leaf_type(sub) is None:
            for item in walk(sub, dotted, covering):
                yield item
        else:
            yield dotted, sub, covering


def collect_characteristics(node, prefix=""):
    """Every node, leaf or section, that declares itself an interview unit."""
    found = []
    for key, sub in (node.get("properties") or {}).items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if sub.get("x-question") or sub.get("x-infer"):
            found.append((dotted, sub))
        if leaf_type(sub) is None:
            found.extend(collect_characteristics(sub, dotted))
    return found


def build(schema):
    errors, warnings = [], []

    groups = schema.get("x-groups") or []
    composites = schema.get("x-composite-questions") or []

    # --- which fields each composite sets, and whether those are legal -----
    composite_of = {}
    all_leaves = {path: sub for path, sub, _ in walk(schema)}

    for composite in composites:
        for answer in composite.get("answers") or []:
            for field, value in (answer.get("sets") or {}).items():
                composite_of[field] = composite["id"]
                target = all_leaves.get(field)
                if target is None:
                    errors.append(cli_output.issue(
                        "%s: composite question %r sets a field that is not in the schema."
                        % (field, composite["id"]),
                        field=field,
                        fix="Correct the field path, or remove it from the composite.",
                    ))
                    continue
                legal = target.get("enum")
                if legal and value not in legal:
                    errors.append(cli_output.issue(
                        "%s: composite question %r sets %r for answer %r, which is not a "
                        "legal value. Expected one of: %s"
                        % (field, composite["id"], value, answer.get("value"),
                           ", ".join(sorted(legal))),
                        field=field, legal=legal,
                        fix="Use one of the legal values.",
                    ))

    express_composites = {c["id"] for c in composites if c.get("express")}

    # --- characteristics ---------------------------------------------------
    characteristics = []
    for dotted, sub in collect_characteristics(schema):
        group = sub.get("x-group")
        if group and group not in groups:
            errors.append(cli_output.issue(
                "%s: x-group %r is not listed in the schema's x-groups."
                % (dotted, group),
                field=dotted, legal=groups,
                fix="Use one of the declared groups, or add it to x-groups.",
            ))
        if not sub.get("x-help"):
            warnings.append(cli_output.issue(
                "%s: no x-help. The README bullet generated for it will be empty."
                % dotted,
                field=dotted,
            ))

        infer = sub.get("x-infer")
        if infer and infer not in INFER_SOURCES:
            errors.append(cli_output.issue(
                "%s: x-infer names %r, which is not a source this toolkit knows how "
                "to read." % (dotted, infer),
                field=dotted, legal=INFER_SOURCES,
                fix="Use a known source, or ask for the field instead.",
            ))

        express_via = sub.get("x-express-via")
        if express_via and express_via not in {c["id"] for c in composites}:
            errors.append(cli_output.issue(
                "%s: x-express-via names composite %r, which does not exist."
                % (dotted, express_via),
                field=dotted,
                fix="Correct the composite id, or drop x-express-via.",
            ))

        covered = [path for path, _, covering in walk(schema) if covering == dotted]
        default = declared_default(sub)

        characteristics.append({
            "id": dotted,
            "label": sub.get("x-label") or dotted.rsplit(".", 1)[-1],
            "group": group,
            "kind": "section" if leaf_type(sub) is None else "field",
            "question": sub.get("x-question"),
            "help": sub.get("x-help"),
            "express": bool(sub.get("x-express")),
            "express_via": express_via,
            "infer": infer,
            "type": leaf_type(sub),
            "legal": sub.get("enum"),
            "default": None if default is SENTINEL else default,
            "fields": covered or [dotted],
        })

    # --- fields ------------------------------------------------------------
    express_fields = set()
    for characteristic in characteristics:
        if characteristic["express"] or characteristic["express_via"] in express_composites:
            express_fields.update(characteristic["fields"])
    for field, composite_id in composite_of.items():
        if composite_id in express_composites:
            express_fields.add(field)

    by_id = {c["id"]: c for c in characteristics}
    fields = []
    for dotted, sub, covering in walk(schema):
        default = declared_default(sub)
        has_default = default is not SENTINEL
        characteristic = by_id.get(covering)
        infer = characteristic["infer"] if characteristic else None

        if infer:
            source = "inferred"
        elif dotted in composite_of:
            source = "composite"
        elif characteristic and characteristic["question"]:
            source = "question"
        else:
            source = "default"

        determinable = bool(infer) or has_default or dotted in express_fields
        if not determinable:
            errors.append(cli_output.issue(
                "%s: cannot be determined. It is not inferred, has no default, and is "
                "not asked in Express mode — an Express run would leave it unset."
                % dotted,
                field=dotted,
                fix="Give it a default, mark it x-express, or infer it.",
            ))

        fields.append({
            "field": dotted,
            "type": leaf_type(sub),
            "legal": sub.get("enum"),
            "default": None if default is SENTINEL else default,
            "has_default": has_default,
            "source": source,
            "characteristic": covering,
            "composite": composite_of.get(dotted),
            "infer": infer,
            "express": dotted in express_fields,
            "internal": bool(sub.get("x-internal")),
        })

    for group in groups:
        if not any(c["group"] == group for c in characteristics):
            warnings.append(cli_output.issue(
                "group %r has no characteristics." % group,
            ))

    express_questions = (
        [c["id"] for c in characteristics if c["express"]]
        + [c["id"] for c in composites if c.get("express")]
    )

    descriptor = {
        "schema": os.path.basename(DEFAULT_SCHEMA),
        "schema_version": (schema.get("properties", {}).get("schema_version", {})).get("const"),
        "groups": groups,
        "characteristics": characteristics,
        "composites": composites,
        "fields": fields,
        "express_questions": express_questions,
        "counts": {
            "characteristics": len(characteristics),
            "fields": len(fields),
            "express_questions": len(express_questions),
            "express_characteristics": sum(
                1 for c in characteristics
                if c["express"] or c["express_via"] in express_composites
            ),
        },
    }
    return descriptor, errors, warnings


def render_markdown(descriptor):
    """The README's Characteristics body — everything between its markers."""
    express_composites = {c["id"] for c in descriptor["composites"] if c.get("express")}
    lines = [
        "Characteristics marked **[E]** are asked in Express mode. The rest are "
        "inferred from the environment or take the documented default.",
        "",
        "Generated from `builders/bootstrap-agent/schema/baseline-profile.schema.json` "
        "by `scripts/describe-schema.py --markdown`. Edit the schema, not this list.",
    ]

    for group in descriptor["groups"]:
        members = [c for c in descriptor["characteristics"] if c["group"] == group]
        if not members:
            continue
        lines.append("")
        lines.append("### %s" % group)
        for characteristic in members:
            express = characteristic["express"] or (
                characteristic["express_via"] in express_composites
            )
            marker = " **[E]**" if express else ""
            suffix = ""
            if characteristic["infer"]:
                suffix = " *(inferred from system)*"
            lines.append("* **%s**%s: %s%s" % (
                characteristic["label"], marker, characteristic["help"] or "", suffix
            ))

    composites = [c for c in descriptor["composites"] if c.get("express")]
    if composites:
        lines.append("")
        lines.append("### Composite questions")
        for composite in composites:
            covered = sorted({
                field["characteristic"] for field in descriptor["fields"]
                if field["composite"] == composite["id"] and field["characteristic"]
            })
            lines.append(
                "* **%s** **[E]**: %s Sets %s in one answer — %s."
                % (
                    composite["label"],
                    composite.get("help", ""),
                    " and ".join("`%s`" % path for path in covered),
                    ", ".join(a["label"] for a in composite["answers"]),
                )
            )

    return "\n".join(lines)


def replace_region(text, body):
    """
    Swap what's between the markers for `body`, leaving everything else byte
    for byte. Raises ValueError if the markers aren't both present — writing
    a file that doesn't declare a managed region would silently take
    ownership of someone's prose.
    """
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        raise ValueError(
            "no managed region found — expected %s ... %s" % (BEGIN_MARKER, END_MARKER)
        )
    return (
        text[:start]
        + BEGIN_MARKER
        + "\n"
        + body
        + "\n"
        + text[end:]
    )


def render_text(descriptor):
    counts = descriptor["counts"]
    lines = [
        "Baseline profile interview descriptor",
        "  %d characteristics, %d leaf fields" % (counts["characteristics"], counts["fields"]),
        "  %d Express questions covering %d characteristics"
        % (counts["express_questions"], counts["express_characteristics"]),
        "",
    ]
    for group in descriptor["groups"]:
        members = [c for c in descriptor["characteristics"] if c["group"] == group]
        if not members:
            continue
        lines.append(group)
        for characteristic in members:
            how = "inferred" if characteristic["infer"] else (
                "Express" if characteristic["express"] else
                "Express via %s" % characteristic["express_via"] if characteristic["express_via"]
                else "Full only"
            )
            lines.append("  %-28s %s" % (characteristic["label"], how))
        lines.append("")

    by_source = {}
    for field in descriptor["fields"]:
        by_source[field["source"]] = by_source.get(field["source"], 0) + 1
    lines.append("Fields by how they are determined:")
    for source in sorted(by_source):
        lines.append("  %-12s %d" % (source, by_source[source]))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Emit the interview descriptor carried by the baseline schema."
    )
    parser.add_argument("--json", action="store_true", help="Emit the JSON envelope")
    parser.add_argument(
        "--markdown", action="store_true", help="Emit the README characteristics body"
    )
    parser.add_argument(
        "--write", nargs="?", const=DEFAULT_README, default=None, metavar="PATH",
        help="Replace the marked region in PATH (default: the bootstrap README)",
    )
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="Schema to describe")
    args = parser.parse_args()

    if not os.path.isfile(args.schema):
        return cli_output.fail("no schema at %s" % args.schema, args.json)

    try:
        with open(args.schema, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
    except ValueError as exc:
        return cli_output.fail(
            "could not parse %s as JSON:\n%s" % (args.schema, exc), args.json
        )

    descriptor, errors, warnings = build(schema)

    if args.json:
        cli_output.print_envelope(errors, warnings, descriptor)
        return 1 if errors else 0

    # Never emit or write a list built from a broken descriptor.
    if (args.markdown or args.write) and errors:
        cli_output.render_text(errors, warnings)
        return 1

    if args.markdown:
        print(render_markdown(descriptor))
        return 0

    if args.write:
        if not os.path.isfile(args.write):
            return cli_output.fail("no file at %s" % args.write, args.json)
        with open(args.write, "r", encoding="utf-8", newline="") as fh:
            original = fh.read()
        try:
            updated = replace_region(original, render_markdown(descriptor))
        except ValueError as exc:
            return cli_output.fail("%s: %s" % (args.write, exc), args.json, exit_code=1)
        if updated == original:
            print("%s is already up to date." % args.write)
            return 0
        with open(args.write, "w", encoding="utf-8", newline="") as fh:
            fh.write(updated)
        print("Regenerated the characteristics region in %s." % args.write)
        return 0

    cli_output.render_text(errors, warnings)
    if errors:
        print("\n%d error(s), %d warning(s) — descriptor is INCOHERENT."
              % (len(errors), len(warnings)))
        return 1

    print(render_text(descriptor))
    return 0


if __name__ == "__main__":
    sys.exit(main())
