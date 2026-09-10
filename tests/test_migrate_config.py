"""
test_migrate_config.py — migrate-config.py, cases M1-M9 from docs/testing.md.

The first real exercise of the migration path. `detect-profile` has had a
STALE state since the beginning and bootstrap has had a Step 4, but until
schema v2 there was no version to migrate from, so none of it had ever run.

M3 is the one that matters most: **every value the version bump does not
touch survives unchanged**. A migration that rebuilds the profile from known
fields passes every other test here and still quietly discards whatever it
was not told about. M3 is what catches that.

M5 is the honesty test. Migrating a v1 profile *grants* read-only web search
it previously withheld, because v2 splits `external_calls` and D12 puts
`web.search` at every posture. That is a deliberate expansion of what the
agent may do, applied by a tool the user ran for another reason, so it has to
be said out loud rather than folded into the change list.
"""

import json
import os
import subprocess
import sys
import unittest

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, REPO_ROOT, load_fixture

MIGRATE_SCRIPT = os.path.join(
    REPO_ROOT, "builders/bootstrap-agent/scripts/migrate-config.py"
)


def leaves(node, prefix=""):
    """Every scalar in the document, by dotted path."""
    out = {}
    for key, value in (node or {}).items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            out.update(leaves(value, dotted))
        else:
            out[dotted] = value
    return out


class MigrateProfileTests(ToolkitTestCase):
    def setUp(self):
        super().setUp()
        self.original = load_fixture("baseline-v1-tools.yaml")
        self.profile = self.write("baseline.yaml", self.original)

    def migrate(self, *args, path=None):
        return subprocess.run(
            [sys.executable, MIGRATE_SCRIPT, path or self.profile, "--json", *args],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True,
        )

    def migrated_document(self):
        with open(self.profile, encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    # -- tests ---------------------------------------------------------------

    def test_m1_a_v1_profile_is_detected_stale(self):
        result = self.run_detect()
        self.assertEqual(result.stdout.strip(), "STALE")
        self.assertEqual(result.returncode, 0)

    def test_m2_migration_produces_a_valid_v2_profile(self):
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

        self.assertEqual(self.migrated_document()["schema_version"], 2)
        validated = self.run_validate_profile(self.profile)
        self.assertEqual(validated.returncode, 0, validated.stdout)

    def test_m3_every_unrelated_value_survives_unchanged(self):
        """
        The property a hand-written migration breaks. Only the three things
        the version bump is *about* may differ.
        """
        before = leaves(yaml.safe_load(self.original))
        self.migrate()
        after = leaves(self.migrated_document())

        expected_to_change = {
            "schema_version",
            "operating_constraints.permissions_scope.tools",
            "operating_constraints.permissions_scope.external_calls",
        }
        for path, value in before.items():
            if path in expected_to_change:
                continue
            self.assertIn(path, after, "%s was dropped by the migration" % path)
            self.assertEqual(after[path], value, "%s was altered" % path)

        # And specifically: a v1 value that v2 merely changed the *default* of
        # keeps the value the user had, rather than silently adopting the new
        # default.
        self.assertIs(
            after["operating_constraints.guardrails.output_validation"], False
        )

    def test_m4_the_v1_tool_vocabulary_maps_per_value(self):
        cases = {
            '["read"]': ["file.read"],
            '["write"]': ["file.read", "file.write"],
            '["search"]': ["file.search"],
            '["read", "search"]': ["file.read", "file.search"],
            '["read", "write", "search"]': ["file.read", "file.search", "file.write"],
        }
        for tools, expected_file_capabilities in cases.items():
            text = self.original.replace('tools: ["read", "write", "search"]',
                                         "tools: %s" % tools)
            path = self.write("case.yaml", text)
            result = subprocess.run(
                [sys.executable, MIGRATE_SCRIPT, path, "--json", "--dry-run"],
                env=self.env, cwd=REPO_ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            granted = json.loads(result.stdout)["data"]["profile"][
                "operating_constraints"]["permissions_scope"]["capabilities"]
            self.assertEqual(
                [c for c in granted if c.startswith("file.")],
                expected_file_capabilities,
                "tools: %s" % tools,
            )

    def test_m5_the_granted_web_default_is_stated_not_applied_silently(self):
        result = self.migrate()
        notes = json.loads(result.stdout)["data"]["notes"]
        web_note = [note for note in notes if "web.search" in note]
        self.assertTrue(web_note, "the changed web default was not reported")
        self.assertIn("GRANTS", web_note[0])

        granted = self.migrated_document()["operating_constraints"][
            "permissions_scope"]["capabilities"]
        self.assertIn("web.search", granted)
        self.assertNotIn("web.fetch", granted, "fetch is still withheld")

    def test_m6_external_calls_true_grants_both(self):
        text = self.original.replace("external_calls: false", "external_calls: true")
        path = self.write("open.yaml", text)
        result = self.migrate(path=path)
        self.assertEqual(result.returncode, 0, result.stdout)
        granted = json.loads(result.stdout)["data"]["profile"][
            "operating_constraints"]["permissions_scope"]["capabilities"]
        self.assertIn("web.search", granted)
        self.assertIn("web.fetch", granted)

    def test_m7_the_backup_is_the_original_byte_for_byte(self):
        result = self.migrate()
        backup = json.loads(result.stdout)["data"]["backup"]
        self.assertTrue(os.path.isfile(backup))
        with open(backup, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), self.original)
        self.assertTrue(backup.endswith(".bak-1"))

    def test_m8_a_second_run_refuses_to_overwrite_the_backup(self):
        """
        The backup is the only copy of the pre-migration profile. Re-running
        over it would destroy exactly what it exists to protect.
        """
        self.migrate()
        self.write("baseline.yaml", self.original)     # pretend it went wrong

        result = self.migrate()
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        self.assertFalse(envelope["ok"])
        self.assertIn("backup already exists", envelope["errors"][0]["message"])

        backup = self.profile + ".bak-1"
        with open(backup, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), self.original)

    def test_m9_dry_run_reports_everything_and_writes_nothing(self):
        result = self.migrate("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)["data"]

        self.assertTrue(data["dry_run"])
        self.assertEqual(data["profile"]["schema_version"], 2)
        self.assertTrue(data["notes"])

        with open(self.profile, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), self.original)
        self.assertFalse(os.path.exists(self.profile + ".bak-1"))

    def test_m10_an_unmapped_v1_tool_warns_rather_than_dropping_it_silently(self):
        text = self.original.replace('tools: ["read", "write", "search"]',
                                     'tools: ["read", "telepathy"]')
        path = self.write("odd.yaml", text)
        result = self.migrate(path=path)
        self.assertEqual(result.returncode, 0, result.stdout)
        warnings = json.loads(result.stdout)["warnings"]
        self.assertTrue(any("telepathy" in w["message"] for w in warnings))

    def test_m11_an_already_current_profile_is_left_alone(self):
        path = self.write("current.yaml", load_fixture("baseline-valid.yaml"))
        with open(path, encoding="utf-8") as fh:
            before = fh.read()

        result = self.migrate(path=path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(json.loads(result.stdout)["data"]["migrated"])

        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)
        self.assertFalse(os.path.exists(path + ".bak-2"))

    def test_m12_a_newer_profile_says_the_toolkit_is_out_of_date(self):
        path = self.write("newer.yaml", load_fixture("baseline-newer-schema.yaml"))
        result = self.migrate(path=path)
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        self.assertIn("newer than this toolkit", envelope["errors"][0]["message"])
        self.assertIn("toolkit is out of date", envelope["errors"][0]["message"])


class MigrateAgentFileTests(ToolkitTestCase):
    """
    M13-M14 — the same migrator, on an agent.yaml.

    It was written for baselines and fits agent files unchanged, because the
    v1-to-v2 change lives in `operating_constraints.permissions_scope`, which
    both schemas shared. That is why it is `migrate-config.py` and not
    `migrate-profile.py`.
    """

    V1_AGENT = """schema_version: 1
extends: "{{BASELINE}}"
name: "legacy"
description: "Made before v2."
voice_style:
  verbosity: "expansive"
operating_constraints:
  permissions_scope:
    tools: ["read", "write"]
    external_calls: true
"""

    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")
        self.agent_yaml = self.write(
            os.path.join("agents", "legacy", "agent.yaml"),
            self.V1_AGENT.replace("{{BASELINE}}", self.baseline_path.replace("\\", "/")),
        )

    def test_m13_a_v1_agent_migrates_with_its_overrides_intact(self):
        result = subprocess.run(
            [sys.executable, MIGRATE_SCRIPT, self.agent_yaml, "--json"],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        with open(self.agent_yaml, encoding="utf-8") as fh:
            migrated = yaml.safe_load(fh)

        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(migrated["voice_style"]["verbosity"], "expansive")
        scope = migrated["operating_constraints"]["permissions_scope"]
        self.assertEqual(
            scope["capabilities"],
            ["file.read", "file.write", "web.search", "web.fetch"],
        )
        self.assertNotIn("tools", scope)
        self.assertTrue(os.path.isfile(self.agent_yaml + ".bak-1"))

    def test_m14_validation_tells_a_stale_agent_to_migrate_not_repair(self):
        result = subprocess.run(
            [sys.executable,
             os.path.join(REPO_ROOT, "builders/create-agent/scripts/validate-agent.py"),
             self.agent_yaml, "--json"],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        errors = {e["field"]: e for e in json.loads(result.stdout)["errors"]}
        version_error = errors["schema_version"]
        self.assertIn("older than the current schema", version_error["message"])
        self.assertIn("migrating", version_error["message"])
        self.assertIn("migrate", version_error["fix"])


if __name__ == "__main__":
    unittest.main()
