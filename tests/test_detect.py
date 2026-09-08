"""
test_detect.py — detect-profile.sh, cases D1-D6 from docs/testing.md.

detect-profile.sh deliberately always exits 0 — the state is the stdout, not
the exit code. Every test here asserts both, so a regression that starts
using exit codes for state doesn't slip through unnoticed.
"""

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


if __name__ == "__main__":
    unittest.main()
