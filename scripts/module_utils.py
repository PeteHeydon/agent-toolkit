#!/usr/bin/env python3
"""
module_utils.py — the library's format and loader (D14).

A module is markdown with YAML frontmatter. One directory, three kinds
distinguished by frontmatter rather than by three parallel vocabularies:

    pattern   How does this agent's process run?
    role      What stance and expertise does it work from?
    routine   What concrete procedure does it follow?

Modules are addressed `kind/name` and resolved user-first:

    $AGENT_TOOLKIT_HOME/library/   your own modules
    <toolkit>/library/             the ones that ship

First match wins, which is the same precedence the rest of the toolkit uses
and means `git pull` can never overwrite something you wrote. A shadowed
module is reported rather than silently preferred — "why is my guidance not
taking effect" is a miserable thing to debug.

Two constraints keep the library light, both enforced here:

  - A body of 40 lines or fewer. Longer than that is a document, not a module.
  - Imperative guidance only. Configuration belongs in the schema, where it
    can be validated and resolved; a module that carries settings is a second
    place for them to disagree.
"""

import os

try:
    import yaml
except ImportError:  # pragma: no cover
    raise

KINDS = ("pattern", "role", "routine")
MAX_BODY_LINES = 40
CURRENT_SCHEMA_VERSION = 1

REQUIRED_FIELDS = ("name", "kind", "summary")
OPTIONAL_FIELDS = ("requires_capabilities", "conflicts_with", "schema_version")


class ModuleError(Exception):
    """A module could not be loaded. Carries the file and field at fault."""

    def __init__(self, message, path=None, field=None, fix=None):
        super().__init__(message)
        self.path = path
        self.field = field
        self.fix = fix


def toolkit_library():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "library"
    )


def user_library():
    home = os.environ.get("AGENT_TOOLKIT_HOME", os.path.expanduser("~/.agent-toolkit"))
    return os.path.join(home, "library")


def search_paths():
    """User first, then shipped. Order is the whole of the shadowing rule."""
    return [user_library(), toolkit_library()]


def split_frontmatter(text, path):
    """
    Return (frontmatter dict, body). A module without frontmatter is an
    error rather than a default, because every field it would default is one
    the loader needs to say something useful about.
    """
    if not text.startswith("---"):
        raise ModuleError(
            "no YAML frontmatter. A module starts with a `---` block naming at "
            "least %s." % ", ".join("`%s`" % f for f in REQUIRED_FIELDS),
            path=path,
            fix="Add a frontmatter block to the top of the file.",
        )

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ModuleError(
            "the frontmatter block is not closed. It needs a second `---` line.",
            path=path,
            fix="Close the frontmatter with a `---` line.",
        )

    try:
        front = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise ModuleError("frontmatter is not valid YAML: %s" % exc, path=path)

    if not isinstance(front, dict):
        raise ModuleError(
            "frontmatter must be a mapping, found %s." % type(front).__name__, path=path
        )

    return front, parts[2].lstrip("\n")


def validate_frontmatter(front, body, path, expected_kind=None, expected_name=None):
    """Returns (errors, warnings) as (message, field) pairs."""
    errors, warnings = [], []

    for field in REQUIRED_FIELDS:
        if not front.get(field):
            errors.append(("`%s` is missing or empty." % field, field))

    kind = front.get("kind")
    if kind and kind not in KINDS:
        errors.append((
            "`kind` is %r, which is not one of: %s." % (kind, ", ".join(KINDS)), "kind"
        ))
    if expected_kind and kind and kind != expected_kind:
        errors.append((
            "`kind` is %r but the file sits in `%s/`. The directory and the "
            "frontmatter have to agree." % (kind, expected_kind), "kind"
        ))

    name = front.get("name")
    if expected_name and name and name != expected_name:
        errors.append((
            "`name` is %r but the file is called `%s.md`. The two have to agree, "
            "because `compose` addresses modules by filename."
            % (name, expected_name), "name"
        ))

    version = front.get("schema_version", CURRENT_SCHEMA_VERSION)
    if version != CURRENT_SCHEMA_VERSION:
        errors.append((
            "`schema_version` is %r; this toolkit reads version %d."
            % (version, CURRENT_SCHEMA_VERSION), "schema_version"
        ))

    for field in ("requires_capabilities", "conflicts_with"):
        value = front.get(field)
        if value is not None and not isinstance(value, list):
            errors.append(("`%s` must be a list, found %s."
                           % (field, type(value).__name__), field))

    unknown = set(front) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    if unknown:
        warnings.append((
            "unrecognised frontmatter: %s. Configuration belongs in the schema, "
            "not in a module." % ", ".join(sorted(unknown)), None
        ))

    body_lines = len([l for l in body.strip().splitlines()])
    if body_lines > MAX_BODY_LINES:
        warnings.append((
            "the body is %d lines, past the %d-line limit. A module longer than "
            "that is a document — split it or cut it."
            % (body_lines, MAX_BODY_LINES), None
        ))

    return errors, warnings


def parse(path, expected_kind=None, expected_name=None):
    """Load one module file into a descriptor. Raises ModuleError."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise ModuleError("could not read: %s" % exc, path=path)

    front, body = split_frontmatter(text, path)
    errors, warnings = validate_frontmatter(
        front, body, path, expected_kind, expected_name
    )
    if errors:
        message, field = errors[0]
        raise ModuleError(message, path=path, field=field)

    return {
        "name": front["name"],
        "kind": front["kind"],
        "summary": front["summary"],
        "requires_capabilities": list(front.get("requires_capabilities") or []),
        "conflicts_with": list(front.get("conflicts_with") or []),
        "schema_version": front.get("schema_version", CURRENT_SCHEMA_VERSION),
        "body": body.strip(),
        "path": path,
        "warnings": [message for message, _field in warnings],
    }


def module_id(kind, name):
    return "%s/%s" % (kind, name)


def find(reference):
    """
    Locate `kind/name` across the search paths.

    Returns (path, shadowed) where `shadowed` lists the paths this one hides.
    Raises ModuleError naming *both* search paths when nothing matches — a
    "not found" that doesn't say where it looked is not much of an error.
    """
    if "/" not in reference:
        raise ModuleError(
            "%r is not a module reference. Use `kind/name`, e.g. `routine/web-research`."
            % reference,
            field="compose",
            fix="Address the module as kind/name.",
        )

    kind, _, name = reference.partition("/")
    if kind not in KINDS:
        raise ModuleError(
            "%r is not a module kind. Use one of: %s." % (kind, ", ".join(KINDS)),
            field="compose",
            fix="Use a known kind.",
        )

    matches = []
    for root in search_paths():
        candidate = os.path.join(root, kind, "%s.md" % name)
        if os.path.isfile(candidate):
            matches.append(candidate)

    if not matches:
        raise ModuleError(
            "no module `%s`. Looked in %s."
            % (reference, " and ".join(search_paths())),
            field="compose",
            fix="Check the name, or add the module to your library.",
        )

    return matches[0], matches[1:]


def load(reference):
    """Load `kind/name`, user library first. The descriptor names what it shadows."""
    path, shadowed = find(reference)
    kind, _, name = reference.partition("/")
    descriptor = parse(path, expected_kind=kind, expected_name=name)
    descriptor["id"] = reference
    descriptor["shadows"] = shadowed
    return descriptor


def list_modules():
    """
    Every module across both paths, user-first, with shadowing recorded.

    Returns (modules, problems). A module that fails to load is a problem
    rather than an omission: silently dropping it is how a library appears to
    be missing something it actually contains.
    """
    modules, problems, seen = [], [], {}

    for root in search_paths():
        for kind in KINDS:
            directory = os.path.join(root, kind)
            if not os.path.isdir(directory):
                continue
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith(".md") or filename == "README.md":
                    continue
                name = filename[:-3]
                reference = module_id(kind, name)
                path = os.path.join(directory, filename)

                if reference in seen:
                    seen[reference]["shadows"].append(path)
                    continue

                try:
                    descriptor = parse(path, expected_kind=kind, expected_name=name)
                except ModuleError as exc:
                    problems.append(exc)
                    continue

                descriptor["id"] = reference
                descriptor["shadows"] = []
                seen[reference] = descriptor
                modules.append(descriptor)

    return modules, problems
