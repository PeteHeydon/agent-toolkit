"""
test_agent_status.py — agent-status.py and render staleness, cases T1-T7 from
docs/testing.md.

T2 is the one that reconciles rendering with D2. Agents read their baseline at
runtime, but `CLAUDE.md` is rendered once — so a baseline edit reaches an
agent's *config* immediately and its *rendered instructions* not at all.
Without something that says so, the toolkit has quietly become the
copy-at-creation system the whole design exists to avoid.

T3 is the same property from the other side, and the more convincing half: an
agent that overrode the edited field is **not** stale, because its resolved
config genuinely did not change. Staleness tracks what an agent actually
resolves to, not whether the baseline file was touched.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, REPO_ROOT, load_fixture

STATUS_SCRIPT = os.path.join(REPO_ROOT, "builders/create-agent/scripts/agent-status.py")
RENDER_SCRIPT = os.path.join(REPO_ROOT, "builders/create-agent/scripts/render-agent.py")


class AgentStatusTests(ToolkitTestCase):
    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")

    # -- helpers -------------------------------------------------------------

    def status(self, *args):
        return subprocess.run(
            [sys.executable, STATUS_SCRIPT, "--json", *args],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True,
        )

    def agents(self):
        result = self.status()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return {a["name"]: a for a in json.loads(result.stdout)["data"]["agents"]}

    def build(self, name, *set_args):
        result = self.run_scaffold(
            "--name", name, "--description", "Probe.",
            "--extends", self.baseline_path, *set_args
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def edit_baseline(self, old, new):
        with open(self.baseline_path, encoding="utf-8") as fh:
            text = fh.read()
        with open(self.baseline_path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new))

    # -- tests ---------------------------------------------------------------

    def test_t1_an_empty_agents_directory_exits_cleanly(self):
        result = subprocess.run(
            [sys.executable, STATUS_SCRIPT], env=self.env, cwd=REPO_ROOT,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("No agents", result.stdout)

    def test_t2_a_baseline_edit_makes_an_inheriting_agent_stale(self):
        self.build("tracks")
        self.assertIs(self.agents()["tracks"]["rendered"], True)

        self.edit_baseline('verbosity: "concise"', 'verbosity: "standard"')
        self.assertIs(self.agents()["tracks"]["rendered"], False)

    def test_t3_an_agent_that_pinned_the_field_is_not_stale(self):
        """
        The convincing half. Staleness follows what an agent *resolves to*,
        not whether the baseline file was touched — so an override that
        already pinned the field means nothing changed for that agent.
        """
        self.build("pins", "--set", "voice_style.verbosity=expansive")
        self.edit_baseline('verbosity: "concise"', 'verbosity: "standard"')
        self.assertIs(self.agents()["pins"]["rendered"], True)

    def test_t4_re_rendering_clears_staleness(self):
        self.build("tracks")
        self.edit_baseline('verbosity: "concise"', 'verbosity: "standard"')
        self.assertIs(self.agents()["tracks"]["rendered"], False)

        agent_dir = os.path.join(self.tmp, "agents", "tracks")
        subprocess.run([sys.executable, RENDER_SCRIPT, agent_dir],
                       env=self.env, cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertIs(self.agents()["tracks"]["rendered"], True)

    def test_t5_check_exits_non_zero_on_a_stale_agent(self):
        self.build("tracks")
        agent_dir = os.path.join(self.tmp, "agents", "tracks")

        fresh = subprocess.run(
            [sys.executable, RENDER_SCRIPT, agent_dir, "--check"],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(fresh.returncode, 0)

        self.edit_baseline('verbosity: "concise"', 'verbosity: "standard"')
        stale = subprocess.run(
            [sys.executable, RENDER_SCRIPT, agent_dir, "--check", "--json"],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(stale.returncode, 1)
        envelope = json.loads(stale.stdout)
        self.assertTrue(envelope["data"]["stale"])
        self.assertIn("rendered from a different configuration",
                      envelope["errors"][0]["message"])

    def test_t6_the_report_names_what_each_agent_pins(self):
        """
        Overrides are the fields a baseline edit will *not* reach, which is
        the thing to know when deciding whether an edit did what you wanted.
        """
        self.build("pins", "--set", "voice_style.verbosity=expansive")
        self.build("tracks")
        agents = self.agents()
        self.assertEqual(agents["pins"]["overrides"], ["voice_style.verbosity"])
        self.assertEqual(agents["tracks"]["overrides"], [])

    def test_t7_an_unfinished_agent_is_reported_as_such(self):
        self.build("fresh")
        self.assertIs(self.agents()["fresh"]["finished"], False)

        path = os.path.join(self.tmp, "agents", "fresh", "CLAUDE.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("2. TODO: the work this agent does. Replace this step.",
                                  "2. Do the actual work."))
        self.assertIs(self.agents()["fresh"]["finished"], True)


if __name__ == "__main__":
    unittest.main()
