"""
test_resolve.py — resolve-config.py, cases R1-R10 from docs/testing.md.

R1 is the most important test in the suite: if leaf merging breaks, an agent
overriding operating_constraints.guardrails.output_validation would silently
wipe input_filtering and every other sibling — a security-relevant failure
that produces no error.

R9 and R10 are the D16 cases: --json wraps resolved/provenance/chain in the
cli_output envelope on success, and a resolution error becomes one structured
entry in `errors` rather than a bare stderr line, when --json is given.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, as_yaml_path, load_fixture


class ResolveConfigTests(ToolkitTestCase):
    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")

    def test_r1_leaf_merge_preserves_sibling_keys(self):
        content = load_fixture("agent-nested-override.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)["data"]

        guardrails = data["resolved"]["operating_constraints"]["guardrails"]
        self.assertIs(guardrails["output_validation"], True)
        self.assertIs(guardrails["input_filtering"], True)

        provenance = data["provenance"]
        self.assertIn("agent", provenance["operating_constraints.guardrails.output_validation"])
        self.assertEqual(provenance["operating_constraints.guardrails.input_filtering"], "baseline")

    def test_r2_array_override_replaces_not_appends(self):
        """
        The security-relevant one. The baseline grants five capabilities; the
        override names one. If arrays merged, the agent would keep file.write
        and web.fetch that nobody granted it.
        """
        content = load_fixture("agent-array-override.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--json")
        data = json.loads(result.stdout)["data"]
        self.assertEqual(
            data["resolved"]["operating_constraints"]["permissions_scope"]["capabilities"],
            ["file.read"],
        )

    def test_r3_cli_set_wins_over_file_layers(self):
        content = load_fixture("agent-minimal.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--set", "operating_constraints.model=claude-opus-5", "--json")
        data = json.loads(result.stdout)["data"]
        self.assertEqual(data["resolved"]["operating_constraints"]["model"], "claude-opus-5")
        self.assertEqual(data["provenance"]["operating_constraints.model"], "CLI flag")

    def test_r4_self_referencing_extends_is_rejected(self):
        cyclic_path = os.path.join(self.tmp, "cyclic.yaml")
        content = load_fixture("agent-cyclic.yaml", SELF=cyclic_path)
        self.write("cyclic.yaml", content)
        result = self.run_resolve(cyclic_path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cyclic", result.stderr)

    def test_r5_extends_chain_too_deep_is_capped(self):
        prev = self.baseline_path
        for i in range(12):
            content = 'schema_version: 1\nextends: "%s"\n' % as_yaml_path(prev)
            prev = self.write("chain-%d.yaml" % i, content)
        result = self.run_resolve(prev)
        self.assertEqual(result.returncode, 1)
        self.assertIn("deeper than", result.stderr)

    def test_r6_missing_extends_target_names_the_path(self):
        content = 'schema_version: 1\nextends: "/does/not/exist.yaml"\nname: "probe"\n'
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr)

    def test_r7_explain_annotates_every_line_with_its_source(self):
        content = load_fixture("agent-minimal.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--explain")
        self.assertEqual(result.returncode, 0)
        self.assertIn("# agent", result.stdout)
        self.assertIn("# baseline", result.stdout)

    def test_r8_baseline_only_summary_is_seven_lines(self):
        result = self.run_resolve("--baseline-only", "--summary")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary_lines = [
            line for line in result.stdout.splitlines()
            if line.strip() and line.strip() != "Inherited configuration:"
        ]
        self.assertEqual(len(summary_lines), 7, result.stdout)

    def test_r9_json_output_has_the_expected_shape(self):
        content = load_fixture("agent-minimal.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--json")
        envelope = json.loads(result.stdout)
        self.assertIn("ok", envelope)
        self.assertIn("errors", envelope)
        self.assertIn("warnings", envelope)
        self.assertTrue(envelope["ok"])
        data = envelope["data"]
        self.assertIn("resolved", data)
        self.assertIn("provenance", data)
        self.assertIn("chain", data)

    def test_r10_resolution_error_is_the_envelope_under_json(self):
        content = 'schema_version: 1\nextends: "/does/not/exist.yaml"\nname: "probe"\n'
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--json")
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        self.assertFalse(envelope["ok"])
        self.assertEqual(len(envelope["errors"]), 1)
        self.assertIn("not found", envelope["errors"][0]["message"])
        self.assertEqual(envelope["errors"][0]["field"], "extends")


if __name__ == "__main__":
    unittest.main()
