#!/usr/bin/env python3
"""
semantic_checks.py — checks a schema cannot express.

Structural validation asks "is this field legal?". These ask "do these fields
make sense *together*?" — a pattern that needs a loop it has switched off, a
budget that cannot cover the work the pattern implies, a composed module the
agent lacks the capability to run.

Shared by both validators so a baseline and an agent are held to the same
standard. A profile that would be incoherent as an agent is incoherent now,
and finding out at creation is cheaper than finding out per-agent later.

**Severity is the hard part, and the rule is narrow.** An error means the
configuration contradicts itself: two fields that cannot both be true. A
warning means it is coherent but worth a second look. The test that keeps this
honest is the toolkit's own risk postures — the Autonomous row is deliberately
full filesystem access, shell, and no human gate. That is not a mistake, it is
what the user asked for, so it warns. A check that fails the shipped defaults
is a broken check, not a strict one.

Judgment that no rule can express — is this tone right for this audience, does
the process match the description — belongs to the validation builder
(TODO 8.2), not here.
"""

import os

CHECKS = []


def check(function):
    CHECKS.append(function)
    return function


def get(resolved, dotted, default=None):
    node = resolved
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


# --- coherence between fields ---------------------------------------------

@check
def evaluation_loop_matches_pattern(resolved, context):
    """
    `evaluator-optimizer` is a review loop. With the loop switched off, the
    pattern and the configuration say opposite things, and the process seeded
    from that pattern tells the agent to iterate a number of times the config
    says is zero.
    """
    errors, warnings = [], []
    pattern = get(resolved, "operating_constraints.pattern")
    enabled = get(resolved, "operating_constraints.evaluation_loop.enabled")

    if pattern == "evaluator-optimizer" and not enabled:
        errors.append((
            "operating_constraints.evaluation_loop.enabled",
            "the pattern is evaluator-optimizer, which is a review loop, but the "
            "evaluation loop is off. The process seeded from this pattern tells the "
            "agent to revise and repeat; the config says there is nothing to repeat.",
            "Set evaluation_loop.enabled: true, or choose a pattern that does not "
            "loop (standalone).",
        ))
    return errors, warnings


@check
def evaluation_loop_has_a_reviewer(resolved, context):
    """A loop with nobody to review is a loop that cannot run."""
    errors, warnings = [], []
    if not get(resolved, "operating_constraints.evaluation_loop.enabled"):
        return errors, warnings

    reviewer = get(resolved, "operating_constraints.evaluation_loop.reviewer")
    if not reviewer:
        errors.append((
            "operating_constraints.evaluation_loop.reviewer",
            "the evaluation loop is enabled but no reviewer is set, so there is "
            "nothing to run the review pass.",
            "Set a reviewer (`self` is the usual answer), or turn the loop off.",
        ))
    return errors, warnings


@check
def unsupervised_full_access(resolved, context):
    """
    Full filesystem access, shell, and no approval gate.

    Deliberately a **warning**: this is exactly the Autonomous risk posture the
    toolkit ships, so erroring would fail its own defaults. But it is worth one
    line, because it is the combination whose blast radius is largest and the
    one most likely to have been inherited rather than chosen.
    """
    errors, warnings = [], []
    filesystem = get(resolved, "operating_constraints.permissions_scope.filesystem")
    granted = get(resolved, "operating_constraints.permissions_scope.capabilities", []) or []
    gated = get(resolved, "operating_constraints.guardrails.human_in_the_loop")

    if filesystem == "full" and "shell" in granted and not gated:
        warnings.append((
            "operating_constraints.guardrails.human_in_the_loop",
            "this agent can run any shell command anywhere on the filesystem without "
            "asking first. That is what the Autonomous posture means, so this is a "
            "note rather than a fault — but confirm it was chosen rather than "
            "inherited.",
            None,
        ))
    return errors, warnings


@check
def budget_covers_the_pattern(resolved, context):
    """
    A multi-pass pattern on a single-pass budget.

    Deliberately vague about numbers, because precision here would be invented.
    The signal worth reporting is the *shape*: the pattern implies repeated
    work and the budget was left where a single pass put it.
    """
    errors, warnings = [], []
    pattern = get(resolved, "operating_constraints.pattern")
    budget = get(resolved, "operating_constraints.cost_performance_budget.max_tokens_per_run")
    if not budget or pattern in (None, "standalone"):
        return errors, warnings

    passes = 1
    if pattern == "evaluator-optimizer":
        passes = 1 + int(get(resolved, "operating_constraints.evaluation_loop.max_cycles", 3) or 3)
    elif pattern in ("pipeline", "orchestrator-workers", "parallel", "collaborative", "router"):
        passes = 2

    if passes > 1 and budget <= 4000:
        warnings.append((
            "operating_constraints.cost_performance_budget.max_tokens_per_run",
            "the %s pattern does roughly %d passes over the work, but the budget is "
            "%d tokens — about what a single pass costs. Either the budget or the "
            "pattern is probably not what was intended."
            % (pattern, passes, budget),
            "Raise max_tokens_per_run, or use the standalone pattern.",
        ))
    return errors, warnings


@check
def context_sources_exist(resolved, context):
    """
    Paths named in `default_context_sources` that are not there.

    A warning, not an error: the path may be created later, and only an agent
    has a directory to resolve against. Checked relative to the agent's own
    directory, because that is where it runs.
    """
    errors, warnings = [], []
    agent_dir = context.get("agent_dir")
    if not agent_dir:
        return errors, warnings

    for source in get(resolved, "knowledge_memory.default_context_sources", []) or []:
        if os.path.isabs(source):
            candidate = source
        else:
            candidate = os.path.join(agent_dir, source)
        if not os.path.exists(candidate):
            warnings.append((
                "knowledge_memory.default_context_sources",
                "%r does not exist relative to the agent directory, so nothing will "
                "be loaded from it." % source,
                "Create it, correct the path, or remove it from the list.",
            ))
    return errors, warnings


@check
def composed_modules_are_runnable(resolved, context):
    """
    Composition against capability, moved here from validate-agent.py so that
    every semantic check lives in one place.

    The failure this catches is the one the toolkit used to produce in
    silence: an agent composed of research guidance that cannot reach the web,
    discovered at run time.
    """
    errors, warnings = [], []
    references = resolved.get("compose") or []
    if not references:
        return errors, warnings

    module_utils = context.get("module_utils")
    if module_utils is None:
        return errors, warnings

    granted = set(get(resolved, "operating_constraints.permissions_scope.capabilities", []) or [])
    loaded = {}

    for reference in references:
        if isinstance(reference, str) and reference.startswith("pattern/"):
            errors.append((
                "compose",
                "%s — patterns are not composed. Name it in "
                "`operating_constraints.pattern` instead; two ways to say the same "
                "thing is two ways for them to disagree." % reference,
                "Set operating_constraints.pattern: %s" % reference.split("/", 1)[1],
            ))
            continue

        try:
            module = module_utils.load(reference)
        except module_utils.ModuleError as exc:
            errors.append(("compose", str(exc), exc.fix))
            continue

        loaded[reference] = module
        missing = [c for c in module["requires_capabilities"] if c not in granted]
        if missing:
            errors.append((
                "compose",
                "%s needs %s, which this agent has not been granted. It would be "
                "told to do something it cannot do."
                % (reference, " and ".join(missing)),
                "Grant %s — `/create-agent --web` covers the web ones — or drop the "
                "module." % ", ".join(missing),
            ))

    for reference, module in loaded.items():
        for other in module["conflicts_with"]:
            if other in loaded:
                errors.append((
                    "compose",
                    "%s and %s declare a conflict with each other and cannot both be "
                    "composed." % (reference, other),
                    "Drop one of them.",
                ))

    if len(references) > 4:
        warnings.append((
            "compose",
            "%d modules. An agent that needs more than four is usually two agents — "
            "each module is guidance the model carries on every run." % len(references),
            None,
        ))

    return errors, warnings


# --- the entry point -------------------------------------------------------

def run(resolved, agent_dir=None, module_utils=None):
    """
    Run every check against a resolved config.

    Returns (errors, warnings) as lists of (field, message, fix) tuples — the
    caller turns them into whatever its own output format is, so this module
    stays independent of cli_output and testable on its own.
    """
    if not isinstance(resolved, dict):
        return [], []

    context = {"agent_dir": agent_dir, "module_utils": module_utils}
    errors, warnings = [], []
    for function in CHECKS:
        check_errors, check_warnings = function(resolved, context)
        errors.extend(check_errors)
        warnings.extend(check_warnings)
    return errors, warnings
