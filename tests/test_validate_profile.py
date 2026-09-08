"""
test_validate_profile.py — validate-profile.py, cases P1-P6 from
docs/testing.md.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, load_fixture


class ValidateProfileTests(ToolkitTestCase):
    def test_p1_shipped_example_is_valid_no_warnings(self):
        path = self.write("probe.yaml", load_fixture("baseline-valid.yaml"))
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("WARN", result.stdout)

    def test_p2_illegal_pattern_lists_legal_set(self):
        path = self.write("probe.yaml", load_fixture("baseline-invalid-enum.yaml"))
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a legal value", result.stdout)
        self.assertIn("standalone", result.stdout)

    def test_p3_missing_required_field_names_it(self):
        path = self.write("probe.yaml", load_fixture("baseline-missing-field.yaml"))
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("identity_context.domain: required", result.stdout)

    def test_p4_evaluation_loop_incoherence_is_an_error(self):
        path = self.write("probe.yaml", load_fixture("baseline-incoherent-loop.yaml"))
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("evaluation_loop", result.stdout)

    def test_p5_literal_secret_is_error_and_warning(self):
        path = self.write("probe.yaml", load_fixture("baseline-literal-secret.yaml"))
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stdout)
        self.assertIn("WARN:", result.stdout)

    def test_p6_budget_out_of_range_is_warning_only(self):
        path = self.write("probe.yaml", load_fixture("baseline-budget-out-of-range.yaml"))
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("WARN:", result.stdout)


if __name__ == "__main__":
    unittest.main()
