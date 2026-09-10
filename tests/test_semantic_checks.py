"""
test_semantic_checks.py — scripts/semantic_checks.py, cases N1-N8 from
docs/testing.md.

Every check gets both halves: a config that triggers it and one that does
not. A check only ever tested against the thing it is supposed to catch is a
check that might fire on everything.

**N3 is the one that shapes the rest.** Full filesystem access, shell, and no
approval gate is exactly the Autonomous risk posture the toolkit ships, so it
has to warn rather than error. A check that fails the toolkit's own defaults
is broken, not strict — and that is the line between the two severities:
an error means two fields contradict each other, a warning means the
combination is coherent but worth a second look.
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import semantic_checks

COHERENT = {
    "operating_constraints": {
        "pattern": "standalone",
        "evaluation_loop": {"enabled": False, "reviewer": None, "max_cycles": 3},
        "guardrails": {"human_in_the_loop": False},
        "permissions_scope": {
            "filesystem": "workspace_only",
            "capabilities": ["file.read", "file.search", "file.write"],
        },
        "cost_performance_budget": {"max_tokens_per_run": 4000},
    },
    "knowledge_memory": {"default_context_sources": []},
}


def config(**changes):
    """A coherent config with one thing changed, by dotted path."""
    result = copy.deepcopy(COHERENT)
    for dotted, value in changes.items():
        parts = dotted.replace("__", ".").split(".")
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return result


def fields(issues):
    return [field for field, _message, _fix in issues]


class SemanticCheckTests(unittest.TestCase):
    def run_checks(self, resolved, **kwargs):
        return semantic_checks.run(resolved, **kwargs)

    # -- N1: the shipped defaults must pass --------------------------------

    def test_n1_a_coherent_config_produces_nothing(self):
        """
        The check on the checks. Anything that fires here fires on ordinary
        configurations, which makes every other finding easier to ignore.
        """
        errors, warnings = self.run_checks(COHERENT)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_n2_every_shipped_risk_posture_is_accepted(self):
        """
        The toolkit's own three postures, run through its own checks. The
        Autonomous row is the one at risk: it is deliberately unsupervised.
        """
        import json
        schema_path = os.path.join(
            REPO_ROOT, "builders/bootstrap-agent/schema/baseline-profile.schema.json")
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)

        for answer in schema["x-composite-questions"][0]["answers"]:
            resolved = copy.deepcopy(COHERENT)
            for dotted, value in answer["sets"].items():
                parts = dotted.split(".")
                node = resolved
                for part in parts[:-1]:
                    node = node.setdefault(part, {})
                node[parts[-1]] = value

            errors, _warnings = self.run_checks(resolved)
            self.assertEqual(
                errors, [],
                "the %s posture the toolkit ships fails its own checks: %s"
                % (answer["value"], errors),
            )

    # -- N3: unsupervised full access --------------------------------------

    def test_n3_unsupervised_full_access_warns_and_never_errors(self):
        resolved = config(
            operating_constraints__permissions_scope__filesystem="full",
            operating_constraints__permissions_scope__capabilities=[
                "file.read", "shell"],
            operating_constraints__guardrails__human_in_the_loop=False,
        )
        errors, warnings = self.run_checks(resolved)
        self.assertEqual(errors, [], "this is the Autonomous posture; it must not error")
        self.assertIn("operating_constraints.guardrails.human_in_the_loop",
                      fields(warnings))

    def test_n3b_a_human_gate_removes_the_warning(self):
        resolved = config(
            operating_constraints__permissions_scope__filesystem="full",
            operating_constraints__permissions_scope__capabilities=[
                "file.read", "shell"],
            operating_constraints__guardrails__human_in_the_loop=True,
        )
        _errors, warnings = self.run_checks(resolved)
        self.assertNotIn("operating_constraints.guardrails.human_in_the_loop",
                         fields(warnings))

    # -- N4: pattern against loop ------------------------------------------

    def test_n4_evaluator_optimizer_without_its_loop_is_an_error(self):
        resolved = config(operating_constraints__pattern="evaluator-optimizer")
        errors, _warnings = self.run_checks(resolved)
        self.assertIn("operating_constraints.evaluation_loop.enabled", fields(errors))

    def test_n4b_the_same_pattern_with_the_loop_on_is_fine(self):
        resolved = config(
            operating_constraints__pattern="evaluator-optimizer",
            operating_constraints__evaluation_loop={
                "enabled": True, "reviewer": "self", "max_cycles": 3},
            operating_constraints__cost_performance_budget={"max_tokens_per_run": 40000},
        )
        errors, _warnings = self.run_checks(resolved)
        self.assertEqual(errors, [])

    # -- N5: a loop with nobody to review ----------------------------------

    def test_n5_an_enabled_loop_without_a_reviewer_is_an_error(self):
        resolved = config(
            operating_constraints__pattern="evaluator-optimizer",
            operating_constraints__evaluation_loop={
                "enabled": True, "reviewer": None, "max_cycles": 3},
        )
        errors, _warnings = self.run_checks(resolved)
        self.assertIn("operating_constraints.evaluation_loop.reviewer", fields(errors))

    # -- N6: budget against pattern ----------------------------------------

    def test_n6_a_looping_pattern_on_a_single_pass_budget_warns(self):
        resolved = config(
            operating_constraints__pattern="evaluator-optimizer",
            operating_constraints__evaluation_loop={
                "enabled": True, "reviewer": "self", "max_cycles": 3},
        )
        _errors, warnings = self.run_checks(resolved)
        self.assertIn(
            "operating_constraints.cost_performance_budget.max_tokens_per_run",
            fields(warnings),
        )

    def test_n6b_standalone_on_the_same_budget_does_not_warn(self):
        _errors, warnings = self.run_checks(COHERENT)
        self.assertNotIn(
            "operating_constraints.cost_performance_budget.max_tokens_per_run",
            fields(warnings),
        )

    # -- N7: context sources -----------------------------------------------

    def test_n7_a_context_source_that_is_not_there_warns(self):
        resolved = config(
            knowledge_memory__default_context_sources=["notes/house-style.md"])
        _errors, warnings = self.run_checks(resolved, agent_dir=REPO_ROOT)
        self.assertIn("knowledge_memory.default_context_sources", fields(warnings))

    def test_n7b_a_source_that_exists_does_not_warn(self):
        resolved = config(
            knowledge_memory__default_context_sources=["library/README.md"])
        _errors, warnings = self.run_checks(resolved, agent_dir=REPO_ROOT)
        self.assertNotIn("knowledge_memory.default_context_sources", fields(warnings))

    def test_n7c_a_profile_has_no_directory_so_the_check_is_skipped(self):
        """A baseline is not resolved against any one agent's directory."""
        resolved = config(
            knowledge_memory__default_context_sources=["nowhere/at/all.md"])
        _errors, warnings = self.run_checks(resolved)
        self.assertNotIn("knowledge_memory.default_context_sources", fields(warnings))

    # -- N8: composition ----------------------------------------------------

    def test_n8_composition_checks_moved_here_still_work(self):
        sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
        import module_utils

        resolved = config(
            operating_constraints__permissions_scope__capabilities=["file.read"])
        resolved["compose"] = ["routine/web-research"]

        errors, _warnings = self.run_checks(resolved, module_utils=module_utils)
        self.assertIn("compose", fields(errors))
        self.assertTrue(any("web.fetch" in message for _f, message, _fix in errors))

    def test_n8b_composition_is_skipped_when_the_loader_is_not_supplied(self):
        """
        A profile validator has no library loader wired in. Skipping is right;
        erroring on every composed module would make baselines unvalidatable.
        """
        resolved = config()
        resolved["compose"] = ["routine/web-research"]
        errors, _warnings = self.run_checks(resolved)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
