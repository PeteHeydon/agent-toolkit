"""
test_cli_output.py — the shared JSON envelope (scripts/cli_output.py) and its
conformance across every script that carries it, per D16.

Two layers: unit tests on the module itself, then one success and one
failure case through --json for each of the five scripts, asserting the
result validates against the envelope and — the point of the whole exercise —
that no error message has to be parsed to recover the field it's about.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, load_fixture

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import cli_output


def assert_is_envelope(test, envelope, ok_matches_errors=True):
    """
    Structural conformance: the shape every --json caller can rely on.

    `ok_matches_errors` holds for every script whose envelope is built by
    `cli_output.envelope()` — every Python one. detect-profile.sh is the
    exception: it reports a *state*, not itemized diagnostics, so `ok` can be
    false (NONE, STALE, ...) with `errors` deliberately empty; see its header
    comment. Callers testing that script pass ok_matches_errors=False.
    """
    test.assertIsInstance(envelope, dict)
    for key in ("ok", "errors", "warnings", "data"):
        test.assertIn(key, envelope)
    test.assertIsInstance(envelope["ok"], bool)
    test.assertIsInstance(envelope["errors"], list)
    test.assertIsInstance(envelope["warnings"], list)
    test.assertIsInstance(envelope["data"], dict)
    if ok_matches_errors:
        test.assertEqual(envelope["ok"], len(envelope["errors"]) == 0)

    for entry in envelope["errors"] + envelope["warnings"]:
        test.assertIsInstance(entry, dict)
        for key in ("field", "message", "legal", "fix"):
            test.assertIn(key, entry)
        test.assertIsInstance(entry["message"], str)
        test.assertTrue(entry["message"], "an issue's message must not be empty")
        if entry["legal"] is not None:
            test.assertIsInstance(entry["legal"], list)


class CliOutputModuleTests(unittest.TestCase):
    """Unit tests on scripts/cli_output.py directly — no subprocess."""

    def test_issue_sorts_legal_and_defaults_the_rest_to_none(self):
        result = cli_output.issue("bad value", field="x.y", legal={"b", "a"})
        self.assertEqual(result, {"field": "x.y", "message": "bad value", "legal": ["a", "b"], "fix": None})

    def test_issue_with_no_legal_is_none_not_empty_list(self):
        self.assertIsNone(cli_output.issue("msg")["legal"])

    def test_envelope_ok_is_true_only_with_no_errors(self):
        self.assertTrue(cli_output.envelope([], [cli_output.issue("just a warning")])["ok"])
        self.assertFalse(cli_output.envelope([cli_output.issue("an error")], [])["ok"])

    def test_envelope_defaults_data_to_empty_dict(self):
        self.assertEqual(cli_output.envelope()["data"], {})


class CliOutputConformanceTests(ToolkitTestCase):
    """One success and one failure per script, all under --json."""

    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")

    # -- validate-profile.py -------------------------------------------------

    def test_validate_profile_success_envelope(self):
        result = self.run_validate_profile(self.baseline_path, "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertTrue(envelope["ok"])

    def test_validate_profile_failure_envelope_names_the_field(self):
        bad = self.write_baseline("baseline-invalid-enum.yaml")
        result = self.run_validate_profile(bad, "--json")
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["errors"][0]["field"], "operating_constraints.pattern")
        self.assertIn("standalone", envelope["errors"][0]["legal"])

    # -- validate-agent.py ----------------------------------------------------

    def test_validate_agent_success_envelope(self):
        content = load_fixture("agent-minimal.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path, "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertTrue(envelope["ok"])

    def test_validate_agent_failure_envelope_names_the_field(self):
        content = load_fixture("agent-illegal-enum.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_validate_agent(path, "--json")
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["errors"][0]["field"], "operating_constraints.pattern")

    # -- resolve-config.py ------------------------------------------------

    def test_resolve_config_success_envelope(self):
        content = load_fixture("agent-minimal.yaml", BASELINE=self.baseline_path)
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertTrue(envelope["ok"])
        self.assertIn("resolved", envelope["data"])

    def test_resolve_config_failure_envelope(self):
        content = 'schema_version: 1\nextends: "/does/not/exist.yaml"\nname: "probe"\n'
        path = self.write("agent.yaml", content)
        result = self.run_resolve(path, "--json")
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertFalse(envelope["ok"])
        self.assertIn("not found", envelope["errors"][0]["message"])

    # -- scaffold-agent.py ------------------------------------------------

    def test_scaffold_agent_success_envelope(self):
        result = self.run_scaffold("--name", "probe", "--description", "Test probe.")
        self.assertEqual(result.returncode, 0, result.stdout)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertTrue(envelope["ok"])

    def test_scaffold_agent_failure_envelope_names_the_field(self):
        result = self.run_scaffold("--name", "Not_A_Slug!")
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["errors"][0]["field"], "name")

    # -- detect-profile.sh --------------------------------------------------
    # Its own envelope is deliberately thin (data.state only, never itemized
    # diagnostics — see the script's header) so only the shape is asserted
    # here, not per-field content.

    def test_detect_profile_success_envelope(self):
        result = self.run_detect("--json")
        self.assertEqual(result.returncode, 0)
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope, ok_matches_errors=False)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["data"]["state"], "VALID")

    def test_detect_profile_failure_envelope(self):
        os.remove(self.baseline_path)
        result = self.run_detect("--json")
        self.assertEqual(result.returncode, 0)  # detect-profile always exits 0; see its header
        envelope = json.loads(result.stdout)
        assert_is_envelope(self, envelope, ok_matches_errors=False)
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["data"]["state"], "NONE")


if __name__ == "__main__":
    unittest.main()
