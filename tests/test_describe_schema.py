"""
test_describe_schema.py — describe-schema.py, cases X1-X9 from docs/testing.md.

The descriptor exists to end a three-way disagreement: the schema, the builder
README and the bootstrap process each used to carry their own idea of what to
ask. So the tests that matter most are the ones asserting the reconciliation
holds — every leaf field is accounted for exactly once (X1), and the README's
six [E] markers really do collapse to five Express questions (X3).

X6 is the guard the item was written around: a field that is neither inferred,
nor defaulted, nor asked in Express can't be filled by an Express run, and must
be reported rather than quietly skipped.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, REPO_ROOT

DESCRIBE_SCRIPT = os.path.join(REPO_ROOT, "scripts", "describe-schema.py")
SCHEMA_PATH = os.path.join(
    REPO_ROOT, "builders", "bootstrap-agent", "schema", "baseline-profile.schema.json"
)
BOOTSTRAP_README = os.path.join(REPO_ROOT, "builders", "bootstrap-agent", "README.md")


def run_describe(*args):
    return subprocess.run(
        [sys.executable, DESCRIBE_SCRIPT, *args], cwd=REPO_ROOT,
        capture_output=True, text=True,
    )


def descriptor():
    result = run_describe("--json")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)["data"]


class DescribeSchemaTests(unittest.TestCase):
    def setUp(self):
        self.data = descriptor()

    def test_x1_every_leaf_field_is_determined_exactly_one_way(self):
        legal_sources = {"question", "composite", "inferred", "default"}
        for field in self.data["fields"]:
            self.assertIn(field["source"], legal_sources, field["field"])

        # And the classification is exhaustive: nothing in the schema's
        # properties tree is missing from the field list.
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)

        def leaves(node, prefix=""):
            for key, sub in (node.get("properties") or {}).items():
                dotted = "%s.%s" % (prefix, key) if prefix else key
                if "properties" in sub:
                    for item in leaves(sub, dotted):
                        yield item
                else:
                    yield dotted

        self.assertEqual(
            sorted(leaves(schema)),
            sorted(field["field"] for field in self.data["fields"]),
        )

    def test_x2_the_shipped_schema_descriptor_is_coherent(self):
        result = run_describe("--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        envelope = json.loads(result.stdout)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["errors"], [])

    def test_x3_six_express_characteristics_collapse_to_five_questions(self):
        """
        The reconciliation this item exists to state. The README marks six
        characteristics [E]; the interview asks five, because risk posture
        covers both guardrails and permissions_scope.
        """
        counts = self.data["counts"]
        self.assertEqual(counts["express_characteristics"], 6)
        self.assertEqual(counts["express_questions"], 5)
        self.assertIn("risk_posture", self.data["express_questions"])

        covered = [
            c["id"] for c in self.data["characteristics"]
            if c["express_via"] == "risk_posture"
        ]
        self.assertEqual(sorted(covered), [
            "operating_constraints.guardrails",
            "operating_constraints.permissions_scope",
        ])

    def test_x4_composite_answers_only_set_legal_values(self):
        legal_by_field = {
            field["field"]: field["legal"] for field in self.data["fields"]
        }
        for composite in self.data["composites"]:
            for answer in composite["answers"]:
                for field, value in answer["sets"].items():
                    self.assertIn(field, legal_by_field, "%s is not a schema field" % field)
                    legal = legal_by_field[field]
                    if legal:
                        self.assertIn(value, legal, "%s=%r" % (field, value))

    def test_x5_an_inferred_field_is_never_asked(self):
        locale = [f for f in self.data["fields"] if f["field"] == "identity_context.locale"][0]
        self.assertEqual(locale["source"], "inferred")
        self.assertEqual(locale["infer"], "system_locale")
        self.assertFalse(locale["express"])

        characteristic = [
            c for c in self.data["characteristics"] if c["id"] == "identity_context.locale"
        ][0]
        self.assertIsNone(characteristic["question"])

    def test_x6_undeterminable_field_is_reported_not_skipped(self):
        """
        A field with no x-question, no x-infer and no default can't be filled
        by an Express run. Reporting it is the point; skipping it is how a
        profile ends up missing a value nobody noticed.
        """
        broken = self._schema_copy()
        target = broken["properties"]["interop"]["properties"]["escalation_path"]
        del target["default"]
        del target["x-question"]

        envelope = self._describe_broken(broken)
        self.assertFalse(envelope["ok"])
        fields = [error["field"] for error in envelope["errors"]]
        self.assertIn("interop.escalation_path", fields)

    def test_x7_composite_setting_an_unknown_field_is_an_error(self):
        broken = self._schema_copy()
        broken["x-composite-questions"][0]["answers"][0]["sets"]["operating_constraints.nope"] = 1
        envelope = self._describe_broken(broken)
        self.assertFalse(envelope["ok"])
        self.assertIn(
            "operating_constraints.nope",
            [error["field"] for error in envelope["errors"]],
        )

    def test_x8_composite_setting_an_illegal_enum_value_is_an_error(self):
        broken = self._schema_copy()
        broken["x-composite-questions"][0]["answers"][0]["sets"][
            "operating_constraints.guardrails.tool_use_limits"] = "paranoid"
        envelope = self._describe_broken(broken)
        self.assertFalse(envelope["ok"])
        error = [
            e for e in envelope["errors"]
            if e["field"] == "operating_constraints.guardrails.tool_use_limits"
        ][0]
        self.assertIn("strict", error["legal"])

    def test_x9_readme_characteristics_match_the_descriptor(self):
        """
        The README's list is generated. If this fails, someone edited the
        schema and didn't re-run `describe-schema.py --write`.
        """
        result = run_describe("--markdown")
        self.assertEqual(result.returncode, 0, result.stdout)
        generated = result.stdout.strip()

        with open(BOOTSTRAP_README, encoding="utf-8") as fh:
            readme = fh.read()

        begin = "<!-- BEGIN GENERATED describe-schema -->"
        end = "<!-- END GENERATED -->"
        self.assertIn(begin, readme)
        self.assertIn(end, readme)
        region = readme[readme.index(begin) + len(begin):readme.index(end)].strip()

        self.assertEqual(
            region, generated,
            "README characteristics are stale — run: "
            "python3 scripts/describe-schema.py --write",
        )

    # -- helpers -------------------------------------------------------------

    def _schema_copy(self):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            return json.load(fh)

    def _describe_broken(self, schema):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(prefix="agent-toolkit-schema-"), "broken.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(schema, fh)
        result = run_describe("--schema", path, "--json")
        self.assertEqual(result.returncode, 1, result.stdout)
        return json.loads(result.stdout)


class DescribeSchemaEnvelopeTests(ToolkitTestCase):
    """The D16 envelope contract, same as every other script carries."""

    def test_missing_schema_is_exit_2_with_an_envelope(self):
        result = run_describe("--schema", os.path.join(self.tmp, "nope.json"), "--json")
        self.assertEqual(result.returncode, 2)
        envelope = json.loads(result.stdout)
        self.assertFalse(envelope["ok"])
        self.assertIn("no schema at", envelope["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
