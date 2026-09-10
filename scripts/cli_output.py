#!/usr/bin/env python3
"""
cli_output.py — the one JSON envelope every front-end-callable script emits
under --json, per D16.

    {
      "ok": bool,
      "errors":   [{"field": str|None, "message": str, "legal": [str,...]|None, "fix": str|None}],
      "warnings": [{"field": str|None, "message": str, "legal": [str,...]|None, "fix": str|None}],
      "data": {...}
    }

Errors and warnings share one shape — both are built by `issue()` below —
`fix` is just more often `None` on a warning, since a warning is usually
something to confirm rather than something with one concrete correction.

`field` is a dotted path into the schema (`"operating_constraints.pattern"`)
wherever an issue traces to exactly one field, and `None` for something
structural — a cyclic `extends`, a missing file, a malformed CLI flag — that
isn't one field's fault. `legal` is the enum's legal set wherever the field is
an enum, `None` otherwise. `fix` is a short imperative when there's one
concrete thing to do about it; often `None`.

Every script keeps its existing plain-text output byte-for-byte when --json
is absent — `render_text` below reproduces exactly the "WARN:  "/"ERROR: "
lines each validator already printed, from the same issue dicts that back the
JSON. Building the message text once, at the point each issue is raised, and
reading it back verbatim in both renderers is what keeps the two in sync.
"""

import json


def issue(message, field=None, legal=None, fix=None):
    """One error or warning entry. `legal`, if given, is any iterable of legal values."""
    return {
        "field": field,
        "message": message,
        "legal": sorted(legal) if legal else None,
        "fix": fix,
    }


def envelope(errors=None, warnings=None, data=None):
    errors = errors or []
    warnings = warnings or []
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "data": data if data is not None else {},
    }


def print_envelope(errors=None, warnings=None, data=None):
    print(json.dumps(envelope(errors, warnings, data), indent=2))


def render_text(errors, warnings):
    """Print the WARN:/ERROR: lines every validator has always printed."""
    for warning in warnings:
        print("WARN:  %s" % warning["message"])
    for error in errors:
        print("ERROR: %s" % error["message"])


def fail(message, json_mode, field=None, fix=None, exit_code=2):
    """
    A pre-check failure — unreadable file, missing dependency, bad usage —
    that happens before a script has anything to validate. Exit code 2 by
    convention (pass exit_code=1 for a logic error caught the same way).
    Prints the same "ERROR: message" line as always when json_mode is False,
    so this never changes today's plain-text behaviour.
    """
    if json_mode:
        print_envelope([issue(message, field=field, fix=fix)], [], {})
    else:
        print("ERROR: %s" % message)
    return exit_code
