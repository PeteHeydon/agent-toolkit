#!/usr/bin/env python3
"""
schema_utils.py — derive validator rules from a JSON schema, so
validate-profile.py and validate-agent.py stop hardcoding their own copies of
the same enum sets and required-field lists. See HANDOFF.md, "Known gaps" #1.

This only understands the `properties` / `required` / `enum` / `type`
keywords — enough for this toolkit's two schemas, not a general JSON Schema
implementation. If a schema starts using `oneOf`, `$ref`, or similar, this
needs to grow with it.
"""

import json


def load_schema(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def extract_enums(schema, prefix=""):
    """
    Walk `properties` recursively and return {dotted.path: set(legal values)}
    for every `enum` found. Dotted paths match the notation the validators
    already use (`operating_constraints.pattern`, etc.), so this is a
    drop-in replacement for a hand-written ENUMS dict.
    """
    enums = {}
    for key, subschema in (schema.get("properties") or {}).items():
        if not isinstance(subschema, dict):
            continue
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if "enum" in subschema:
            enums[dotted] = set(subschema["enum"])
        if subschema.get("type") == "object":
            enums.update(extract_enums(subschema, dotted))
    return enums


def extract_required_leaves(schema, prefix=""):
    """
    Walk `required` recursively and return a flat list of dotted paths that
    must be present. A required object that itself declares no `required`
    fields is treated as a leaf — its presence, not its contents, is what's
    mandated at that point.
    """
    leaves = []
    props = schema.get("properties") or {}
    for key in schema.get("required") or []:
        dotted = "%s.%s" % (prefix, key) if prefix else key
        subschema = props.get(key) or {}
        if subschema.get("type") == "object" and subschema.get("required"):
            leaves.extend(extract_required_leaves(subschema, dotted))
        else:
            leaves.append(dotted)
    return leaves
