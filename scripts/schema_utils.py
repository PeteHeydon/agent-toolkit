#!/usr/bin/env python3
"""
schema_utils.py — derive validator rules from a JSON schema, so
validate-profile.py and validate-agent.py stop hardcoding their own copies of
the same enum sets and required-field lists. See HANDOFF.md, "Known gaps" #1.

This only understands the `properties` / `required` / `enum` / `type`
keywords — enough for this toolkit's two schemas, not a general JSON Schema
implementation. If a schema starts using `oneOf`, `$ref`, or similar, this
needs to grow with it.

It also owns the known-model list. That can't come from the schema: `model` is
deliberately an open string, because a model released after the toolkit was
last updated must still be usable.
"""

import json

# Models the toolkit knows about, newest tier first. Deliberately NOT a schema
# enum — an unrecognised model warns, it never errors, or the toolkit would
# block every model released after its last update.
KNOWN_MODELS = [
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5",
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-fable-5-1",
]

# Bare tier names, so a profile can say `sonnet` and mean the current Sonnet.
# Resolution is reported, never silent — a config that says one thing and
# resolves to another is how surprises start.
MODEL_ALIASES = {
    "opus": "claude-opus-5",
    "sonnet": "claude-sonnet-5",
    "haiku": "claude-haiku-4-5",
}

DEFAULT_MODEL = "claude-sonnet-5"


def resolve_model(value):
    """
    Resolve a `model` value to a canonical ID.

    Returns (canonical, note). `note` is None when the value is a known model
    ID, and otherwise a message the caller should surface as a WARNING — an
    alias resolution the user should see, or a model this toolkit doesn't
    recognise. Never an error: see KNOWN_MODELS.
    """
    if not isinstance(value, str) or not value.strip():
        return value, None

    value = value.strip()

    if value in MODEL_ALIASES:
        canonical = MODEL_ALIASES[value]
        return canonical, (
            "operating_constraints.model: %r is an alias, resolved to %r. "
            "Write the full ID if you want to pin it against a future tier change."
            % (value, canonical)
        )

    if value in KNOWN_MODELS:
        return value, None

    return value, (
        "operating_constraints.model: %r is not a model this toolkit knows about. "
        "That's fine if it's newer than the toolkit; check it against the "
        "provider's model list. Known: %s" % (value, ", ".join(KNOWN_MODELS))
    )


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


def extract_array_enums(schema, prefix=""):
    """
    Walk `properties` recursively and return {dotted.path: set(legal values)}
    for every array whose `items` carry an `enum` — `capabilities` being the
    one that matters.

    Kept separate from extract_enums() because the check differs: a scalar
    enum validates the value, an array enum validates every element. Folding
    them into one dict would make a validator check `["file.read"] in legal`
    and pass everything.
    """
    enums = {}
    for key, subschema in (schema.get("properties") or {}).items():
        if not isinstance(subschema, dict):
            continue
        dotted = "%s.%s" % (prefix, key) if prefix else key
        items = subschema.get("items")
        if subschema.get("type") == "array" and isinstance(items, dict) and "enum" in items:
            enums[dotted] = set(items["enum"])
        if subschema.get("type") == "object":
            enums.update(extract_array_enums(subschema, dotted))
    return enums


def extract_defaults(schema, prefix=""):
    """
    Walk `properties` recursively and return {dotted.path: default} for every
    leaf that declares one.

    Used by the renderer to keep the generated region small: a value sitting
    at its schema default changes no behaviour, so rendering a line about it
    spends tokens to say nothing. Knowing the default is what makes "render
    only where it differs" possible.
    """
    defaults = {}
    for key, subschema in (schema.get("properties") or {}).items():
        if not isinstance(subschema, dict):
            continue
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if "properties" in subschema:
            defaults.update(extract_defaults(subschema, dotted))
        elif "default" in subschema:
            defaults[dotted] = subschema["default"]
    return defaults


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
