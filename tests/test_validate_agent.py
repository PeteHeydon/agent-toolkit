"""
test_validate_agent.py — validate-agent.py, cases A1-A8 from
docs/testing.md.

A2 is the subtle one: a redundant override doesn't error, it warns — because
it's structurally legal, just harmful (it silently pins the field against
future baseline edits).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, load_fixture


class ValidateAgentTests(ToolkitTestCase):
    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")

    def test_a1_clean_minimal_override_is_valid_no_warnings(self):
        content = load_fixture("agent-minimal.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("WARN", result.stdout)

    def test_a2_redundant_override_warns_but_is_valid(self):
        content = load_fixture("agent-redundant-override.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("overrides with the same value as the baseline", result.stdout)

    def test_a3_bad_slug_is_an_error(self):
        content = load_fixture("agent-bad-slug.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a valid slug", result.stdout)

    def test_a4_missing_extends_is_an_error(self):
        content = load_fixture("agent-missing-extends.yaml")
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("extends: required", result.stdout)

    def test_a5_illegal_enum_lists_legal_set(self):
        content = load_fixture("agent-illegal-enum.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a legal value", result.stdout)

    def test_a6_cyclic_extends_fails_resolution(self):
        cyclic_path = os.path.join(self.tmp, "cyclic.yaml")
        content = load_fixture("agent-cyclic.yaml", SELF=cyclic_path)
        self.write("cyclic.yaml", content)
        result = self.run_validate_agent(cyclic_path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cyclic", result.stdout)

    def test_a7_literal_secret_in_credentials_is_an_error(self):
        content = load_fixture("agent-literal-secret.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("env var reference", result.stdout)

    def test_a8_missing_description_warns_only(self):
        content = load_fixture("agent-missing-description.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("description: empty", result.stdout)


if __name__ == "__main__":
    unittest.main()
