"""
test_detect.py — profile detection, cases D1-D12 from docs/testing.md.

detect-profile.sh deliberately always exits 0 — the state is the stdout, not
the exit code. Every test here asserts both, so a regression that starts
using exit codes for state doesn't slip through unnoticed.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase


class DetectProfileTests(ToolkitTestCase):
    def test_d1_no_file_is_none(self):
        result = self.run_detect()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "NONE")

    def test_d2_valid_profile(self):
        self.write_baseline("baseline-valid.yaml")
        result = self.run_detect()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "VALID")

    def test_d3_stale_schema_version(self):
        self.write_baseline("baseline-stale.yaml")
        result = self.run_detect()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "STALE")

    def test_d4_illegal_enum_is_invalid(self):
        self.write_baseline("baseline-invalid-enum.yaml")
        result = self.run_detect()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "INVALID")

    def test_d5_malformed_yaml_is_unreadable(self):
        self.write_baseline("baseline-malformed.yaml")
        result = self.run_detect()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "UNREADABLE")

    def test_d6_newer_schema_version_is_invalid(self):
        self.write_baseline("baseline-newer-schema.yaml")
        result = self.run_detect()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "INVALID")

    def test_d7_broken_interpreter_is_no_python_not_unreadable(self):
        """
        The bug this guards: `python3` on Windows resolves to the Microsoft
        Store stub, which isn't an interpreter. The old script swallowed that
        and reported UNREADABLE, so a valid profile looked corrupt and
        /create-agent refused to run. An environment failure must never be
        reported as a data failure.
        """
        self.write_baseline("baseline-valid.yaml")
        result = self.run_detect(AGENT_TOOLKIT_PYTHON="/nonexistent/python")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "NO_PYTHON")
        self.assertIn("AGENT_TOOLKIT_PYTHON", result.stderr)
        self.assertIn("NOT been read", result.stderr)

    def test_d8_env_failure_outranks_a_bad_profile(self):
        """
        With no interpreter we cannot know anything about the profile, even a
        genuinely malformed one. Reporting UNREADABLE here would be a guess
        that happens to be right, and the same code path guesses wrong on a
        valid profile.
        """
        self.write_baseline("baseline-malformed.yaml")
        result = self.run_detect(AGENT_TOOLKIT_PYTHON="/nonexistent/python")
        self.assertEqual(result.stdout.strip(), "NO_PYTHON")

    def test_d9_interpreter_override_is_honoured_when_it_works(self):
        self.write_baseline("baseline-valid.yaml")
        result = self.run_detect(AGENT_TOOLKIT_PYTHON=sys.executable)
        self.assertEqual(result.stdout.strip(), "VALID")


class DetectProfilePythonTests(ToolkitTestCase):
    """
    D10-D12 — the same states, straight from the Python script.

    The builders call the .py; the .sh is the interpreter probe that finds an
    interpreter and delegates. Both are tested because only one of them can
    report a missing interpreter and only one of them reads the profile — a
    port that quietly disagreed with its wrapper would be worse than either.
    """

    def test_d10_the_python_script_reports_the_same_states(self):
        for fixture, expected in [
            ("baseline-valid.yaml", "VALID"),
            ("baseline-stale.yaml", "STALE"),
            ("baseline-invalid-enum.yaml", "INVALID"),
            ("baseline-malformed.yaml", "UNREADABLE"),
            ("baseline-newer-schema.yaml", "INVALID"),
        ]:
            self.write_baseline(fixture)
            result = self.run_detect_py()
            self.assertEqual(result.returncode, 0, fixture)
            self.assertEqual(result.stdout.strip(), expected, fixture)

    def test_d11_both_entry_points_agree(self):
        """A port that disagrees with its wrapper is worse than neither."""
        for fixture in ("baseline-valid.yaml", "baseline-stale.yaml",
                        "baseline-malformed.yaml"):
            self.write_baseline(fixture)
            self.assertEqual(
                self.run_detect_py().stdout.strip(),
                self.run_detect().stdout.strip(),
                fixture,
            )

    def test_d12_no_file_and_json_shape(self):
        result = self.run_detect_py()
        self.assertEqual(result.stdout.strip(), "NONE")

        # `ok` follows the *state*, not the (always empty) error list. Deriving
        # it the usual way made every state report ok:true, NONE included —
        # which is what the port got wrong before C3 caught it.
        envelope = json.loads(self.run_detect_py("--json").stdout)
        self.assertFalse(envelope["ok"], "NONE is not an ok state")
        self.assertEqual(envelope["data"]["state"], "NONE")

        self.write_baseline("baseline-valid.yaml")
        envelope = json.loads(self.run_detect_py("--json").stdout)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["data"]["state"], "VALID")
        self.assertEqual(envelope["errors"], [])

        self.write_baseline("baseline-stale.yaml")
        self.assertFalse(json.loads(self.run_detect_py("--json").stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
