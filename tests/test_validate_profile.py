"""
test_validate_profile.py — validate-profile.py, cases P1-P12 from
docs/testing.md.

P10-P12 are the schema v2 capability checks: a v1 profile has to be told what
replaced its fields, an unknown capability has to list the legal set, and a
domain list that can never take effect has to be caught rather than accepted.
"""

import json
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

    # --- model resolution --------------------------------------------------
    # `model` is deliberately an open string in both schemas: a model released
    # after the toolkit was last updated must still be usable. So an
    # unrecognised value warns, and never errors.

    def _profile_with_model(self, model):
        text = load_fixture("baseline-valid.yaml").replace(
            'model: "claude-sonnet-5"', 'model: "%s"' % model
        )
        return self.write("probe.yaml", text)

    def test_p7_known_model_is_silent(self):
        path = self._profile_with_model("claude-opus-5")
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("operating_constraints.model", result.stdout)

    def test_p8_alias_resolves_and_reports_the_resolution(self):
        path = self._profile_with_model("sonnet")
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("WARN", result.stdout)
        self.assertIn("claude-sonnet-5", result.stdout)

    def test_p9_unknown_model_warns_but_stays_valid(self):
        path = self._profile_with_model("claude-sonnet-99")
        result = self.run_validate_profile(path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("WARN", result.stdout)
        self.assertIn("not a model this toolkit knows about", result.stdout)


class CapabilityVocabularyTests(ToolkitTestCase):
    """
    Schema v2, cases P10-P12. The v1 vocabulary (`tools`, `external_calls`)
    named things no runtime understood and conflated web search with arbitrary
    egress; v2 replaces both with a closed capability set.
    """

    def test_p10_v1_tools_key_names_its_v2_replacement(self):
        """
        Rejecting a v1 profile is not enough — the message has to say what to
        use instead, because whoever sees it is mid-migration.
        """
        path = self.write_baseline("baseline-v1-tools.yaml")
        result = self.run_validate_profile(path, "--json")
        self.assertEqual(result.returncode, 1)
        errors = {error["field"]: error for error in json.loads(result.stdout)["errors"]}

        retired = errors["operating_constraints.permissions_scope.tools"]
        self.assertIn("capabilities", retired["message"])
        self.assertIn("removed in schema_version 2", retired["message"])

        external = errors["operating_constraints.permissions_scope.external_calls"]
        self.assertIn("web.search", external["message"])
        self.assertIn("web.fetch", external["message"])

    def test_p11_illegal_capability_lists_the_legal_set(self):
        path = self.write_baseline("baseline-illegal-capability.yaml")
        result = self.run_validate_profile(path, "--json")
        self.assertEqual(result.returncode, 1)
        error = [
            e for e in json.loads(result.stdout)["errors"]
            if e["field"] == "operating_constraints.permissions_scope.capabilities"
        ][0]
        self.assertIn("shell.exec", error["message"])
        self.assertIn("file.read", error["legal"])
        self.assertIn("web.fetch", error["legal"])

    def test_p12_domain_list_without_web_fetch_is_an_error(self):
        """
        A config that looks like it bounds egress but can't is worse than one
        that says nothing about it.
        """
        path = self.write_baseline("baseline-domains-without-fetch.yaml")
        result = self.run_validate_profile(path, "--json")
        self.assertEqual(result.returncode, 1)
        error = [
            e for e in json.loads(result.stdout)["errors"]
            if e["field"].endswith("web.allowed_domains")
        ][0]
        self.assertIn("web.fetch is not granted", error["message"])


if __name__ == "__main__":
    unittest.main()
