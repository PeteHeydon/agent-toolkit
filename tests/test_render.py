"""
test_render.py — render-agent.py, cases W1-W10 (permissions) and
G1-G8 (the generated CLAUDE.md region) from docs/testing.md.

One renderer, one test file. render-agent.py writes both artefacts in a single
pass from a single resolved config, because two renderers would mean two
config hashes and two answers to "is this agent stale".

This is the step that makes a permission field real, so the tests that matter
are the ones about what an agent *cannot* do. W3 and W4 are the pair worth
reading: a withheld high-consequence capability is denied rather than merely
left out, and a read-only filesystem denies writing even where the capability
was granted.

W7 is the one that protects someone else's repository: an agent scaffolded
into a project with `--path` gets its own settings and never touches the
project's.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, REPO_ROOT, load_fixture

RENDER_SCRIPT = os.path.join(
    REPO_ROOT, "builders/create-agent/scripts/render-agent.py"
)
RUNTIME_FILE = os.path.join(REPO_ROOT, "runtimes", "claude-code.yaml")


class RenderPermissionsTests(ToolkitTestCase):
    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")

    # -- helpers -------------------------------------------------------------

    def make_agent(self, capabilities=None, filesystem=None, web=None):
        """An agent directory whose baseline grants exactly what's asked for."""
        if capabilities is not None or filesystem is not None or web is not None:
            text = load_fixture("baseline-valid.yaml")
            if capabilities is not None:
                text = text.replace(
                    '    capabilities: ["file.read", "file.search", "file.write", '
                    '"web.search", "web.fetch"]',
                    "    capabilities: %s" % json.dumps(capabilities),
                )
            if filesystem is not None:
                text = text.replace(
                    'filesystem: "workspace_only"', 'filesystem: "%s"' % filesystem
                )
            if web is not None:
                text = text.replace(
                    "    capabilities:",
                    "    web:\n%s\n    capabilities:"
                    % "\n".join(
                        "      %s: %s" % (key, json.dumps(value))
                        for key, value in web.items()
                    ),
                )
            self.baseline_path = self.write("baseline.yaml", text)

        agent_dir = os.path.join(self.tmp, "agents", "probe")
        os.makedirs(agent_dir, exist_ok=True)
        self.write(
            os.path.join("agents", "probe", "agent.yaml"),
            load_fixture("agent-minimal.yaml", BASELINE=self.baseline_path),
        )
        return agent_dir

    def render(self, agent_dir, *args):
        return subprocess.run(
            [sys.executable, RENDER_SCRIPT, agent_dir, "--json", *args],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True,
        )

    def permissions(self, agent_dir, **kwargs):
        result = self.render(agent_dir, **kwargs)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)["data"]["permissions"]

    # -- tests ---------------------------------------------------------------

    def test_w1_granted_web_capabilities_reach_the_allow_list(self):
        """D12's whole point: an agent can search and fetch by default."""
        agent_dir = self.make_agent()
        allow = self.permissions(agent_dir)["allow"]
        self.assertIn("WebSearch", allow)
        self.assertIn("WebFetch", allow)

    def test_w2_every_capability_maps_to_its_tools(self):
        agent_dir = self.make_agent(capabilities=[
            "file.read", "file.search", "file.write", "shell",
            "web.search", "web.fetch", "subagent",
        ], filesystem="full")
        allow = set(self.permissions(agent_dir)["allow"])
        for tool in ("Read", "Glob", "Grep", "Write", "Edit", "NotebookEdit",
                     "Bash", "WebSearch", "WebFetch", "Task"):
            self.assertIn(tool, allow, "%s missing from allow" % tool)

    def test_w3_withheld_shell_is_denied_not_merely_unlisted(self):
        """
        An un-allowed tool prompts; a denied tool cannot run. A capability
        deliberately withheld has to be the second kind.
        """
        agent_dir = self.make_agent(capabilities=["file.read", "file.search"])
        permissions = self.permissions(agent_dir)
        self.assertIn("Bash", permissions["deny"])
        self.assertNotIn("Bash", permissions["allow"])

    def test_w4_read_only_denies_writing_even_when_granted(self):
        """
        `file.write` with `filesystem: read_only` is contradictory. The safe
        reading of a contradiction is the restrictive one.
        """
        agent_dir = self.make_agent(
            capabilities=["file.read", "file.search", "file.write"],
            filesystem="read_only",
        )
        permissions = self.permissions(agent_dir)
        for tool in ("Write", "Edit", "NotebookEdit"):
            self.assertIn(tool, permissions["deny"])
            self.assertNotIn(tool, permissions["allow"])

    def test_w5_allow_and_deny_never_overlap(self):
        agent_dir = self.make_agent(
            capabilities=["file.read", "file.write", "web.fetch"],
            filesystem="read_only",
        )
        permissions = self.permissions(agent_dir)
        self.assertEqual(
            set(permissions["allow"]) & set(permissions["deny"]), set(),
            "a settings file that both grants and forbids a tool decides nothing",
        )

    def test_w6_render_is_deterministic_and_carries_a_config_hash(self):
        """
        D11 rule 3: a rendered artefact is a cache with a validity check.
        No timestamp, so an unchanged config renders byte-identically.
        """
        agent_dir = self.make_agent()
        first = self.render(agent_dir)
        second = self.render(agent_dir)
        self.assertEqual(first.stdout, second.stdout)

        state_path = os.path.join(agent_dir, ".agent", "render.json")
        self.assertTrue(os.path.isfile(state_path))
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
        self.assertEqual(
            state["config_hash"], json.loads(first.stdout)["data"]["config_hash"]
        )
        self.assertNotIn("rendered_at", state)

    def test_w7_a_parent_projects_settings_are_never_touched(self):
        """
        `--path` scaffolds into someone's repository. Its `.claude/settings.json`
        is theirs; the agent gets its own, one directory down.
        """
        project = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(project, ".claude"))
        parent_settings = os.path.join(project, ".claude", "settings.json")
        original = '{"permissions": {"allow": ["Bash"]}, "note": "theirs"}'
        with open(parent_settings, "w", encoding="utf-8") as fh:
            fh.write(original)

        result = self.run_scaffold(
            "--name", "embedded", "--description", "In a project.",
            "--dest", project, "--extends", self.baseline_path,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

        with open(parent_settings, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), original, "the project's own settings were rewritten")

        agent_settings = os.path.join(project, "embedded", ".claude", "settings.json")
        self.assertTrue(os.path.isfile(agent_settings))

    def test_w8_an_unmapped_capability_is_an_error_naming_the_known_set(self):
        agent_dir = self.make_agent()
        # Written whole rather than appended: appending depended on which key
        # the fixture happened to end with, so a fixture edit moved this block
        # somewhere harmless and the test passed while testing nothing.
        with open(os.path.join(agent_dir, "agent.yaml"), "w", encoding="utf-8") as fh:
            fh.write(
                'schema_version: 2\n'
                'extends: "%s"\n'
                'name: "probe"\n'
                'description: "Test probe."\n'
                'operating_constraints:\n'
                '  permissions_scope:\n'
                '    capabilities: ["telepathy"]\n'
                % self.baseline_path.replace("\\", "/")
            )

        result = self.render(agent_dir)
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        self.assertFalse(envelope["ok"])
        error = envelope["errors"][0]
        self.assertIn("telepathy", error["message"])
        self.assertIn("file.read", error["legal"])


class GeneratedRegionTests(ToolkitTestCase):
    """
    The generated CLAUDE.md region, G1-G8.

    G3 is the one the whole design rests on: `CLAUDE.md` is the only artefact
    that reaches the model, and everything outside the markers is the user's.
    A renderer that cannot be trusted with the rest of the file is a renderer
    nobody will run twice.
    """

    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")

    def make_agent(self, name="probe", overrides="", **baseline_edits):
        """
        An agent that overrides nothing unless asked to.

        Deliberately not built from a fixture: these tests assert what the
        *baseline* puts into the region, and a fixture that quietly pins a
        field would make them assert against the fixture instead.
        """
        if baseline_edits:
            text = load_fixture("baseline-valid.yaml")
            for old, new in baseline_edits.get("replacements", []):
                text = text.replace(old, new)
            self.baseline_path = self.write("baseline.yaml", text)

        agent_dir = os.path.join(self.tmp, "agents", name)
        os.makedirs(agent_dir, exist_ok=True)
        self.write(
            os.path.join("agents", name, "agent.yaml"),
            'schema_version: 2\nextends: "%s"\nname: "%s"\n'
            'description: "Test probe."\n%s'
            % (self.baseline_path.replace("\\", "/"), name, overrides),
        )
        return agent_dir

    def render(self, agent_dir, *args):
        return subprocess.run(
            [sys.executable, RENDER_SCRIPT, agent_dir, *args],
            env=self.env, cwd=REPO_ROOT, capture_output=True, text=True,
        )

    def region_of(self, agent_dir):
        with open(os.path.join(agent_dir, "CLAUDE.md"), encoding="utf-8") as fh:
            text = fh.read()
        start = text.index("<!-- BEGIN GENERATED")
        end = text.index("<!-- END GENERATED -->") + len("<!-- END GENERATED -->")
        return text[start:end]

    def test_g1_the_baselines_personalised_values_reach_the_region(self):
        """
        The item's Why: every one of these is in the baseline and currently
        reaches the model only if the user retypes it.
        """
        agent_dir = self.make_agent()
        self.assertEqual(self.render(agent_dir).returncode, 0)
        region = self.region_of(agent_dir)

        for expected in ("general", "internal team", "en-AU", "neutral, direct",
                         "concise", "markdown", "./output"):
            self.assertIn(expected, region, "%r never reached CLAUDE.md" % expected)

    def test_g2_the_region_stays_within_the_size_budget(self):
        agent_dir = self.make_agent()
        result = self.render(agent_dir, "--stdout", "--json")
        data = json.loads(result.stdout)["data"]
        self.assertLessEqual(
            data["lines"], 80,
            "the region is past its 80-line target; check every line still "
            "changes behaviour",
        )

    def test_g3_content_outside_the_markers_survives_byte_for_byte(self):
        agent_dir = self.make_agent()
        self.render(agent_dir)

        path = os.path.join(agent_dir, "CLAUDE.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        mine = "\n## Process\n\n1. A step I wrote, with `backticks` and — punctuation.\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + mine)

        self.render(agent_dir)
        with open(path, encoding="utf-8") as fh:
            after = fh.read()
        self.assertTrue(after.endswith(mine), "hand-written content was altered")

    def test_g4_defaults_render_nothing(self):
        """
        D13's size rule. A guardrail at its schema default changes no
        behaviour, so a line about it spends tokens to say nothing.
        """
        agent_dir = self.make_agent()
        region = self.render(agent_dir, "--stdout").stdout
        self.assertNotIn("input_filtering", region)
        self.assertNotIn("Pause and ask for approval", region)

        loud = self.make_agent(name="loud", replacements=[
            ("human_in_the_loop: false", "human_in_the_loop: true"),
        ])
        self.assertIn("Pause and ask for approval", self.render(loud, "--stdout").stdout)

    def test_g5_a_withheld_capability_is_stated(self):
        """The acceptance case: an agent without web.fetch has to know it."""
        agent_dir = self.make_agent(replacements=[
            ('    capabilities: ["file.read", "file.search", "file.write", '
             '"web.search", "web.fetch"]',
             '    capabilities: ["file.read", "file.search", "web.search"]'),
        ])
        region = self.render(agent_dir, "--stdout").stdout
        self.assertIn("cannot", region)
        self.assertIn("fetch web pages", region)

    def test_g6_two_baselines_produce_visibly_different_regions(self):
        first = self.make_agent(name="one")
        self.render(first)
        second = self.make_agent(name="two", replacements=[
            ('domain: "general"', 'domain: "commercial litigation"'),
            ('verbosity: "concise"', 'verbosity: "expansive"'),
        ])
        self.render(second)
        self.assertNotEqual(self.region_of(first), self.region_of(second))
        self.assertIn("commercial litigation", self.region_of(second))

    def test_g7_json_and_markdown_describe_the_same_sections(self):
        """
        D18: the markdown is one renderer over the structure, not a separate
        construction. If they can disagree, the structured output is a lie.
        """
        agent_dir = self.make_agent()
        result = self.render(agent_dir, "--stdout", "--json")
        data = json.loads(result.stdout)["data"]

        for item in data["sections"]:
            self.assertIn("## %s" % item["heading"], data["markdown"])
            for line in item["lines"]:
                self.assertIn(line, data["markdown"])
            self.assertTrue(item["fields"], "%s names no source fields" % item["id"])

    def test_g8_a_lone_marker_is_refused_rather_than_guessed_at(self):
        agent_dir = self.make_agent()
        with open(os.path.join(agent_dir, "CLAUDE.md"), "w", encoding="utf-8") as fh:
            fh.write("# probe\n\nOnly one marker below.\n\n<!-- END GENERATED -->\n")

        result = self.render(agent_dir, "--json")
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        self.assertFalse(envelope["ok"])
        self.assertIn("only one of the two generated markers",
                      envelope["errors"][0]["message"])


class ScaffoldRendersPermissionsTests(ToolkitTestCase):
    """Scaffolding an agent must leave it with permissions, not just config."""

    def setUp(self):
        super().setUp()
        self.write_baseline("baseline-valid.yaml")

    def test_w9_scaffold_writes_settings_and_reports_them(self):
        result = self.run_scaffold("--name", "probe", "--description", "Probe.")
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)["data"]

        self.assertIn(".claude/settings.json", data["files"])
        self.assertIn("WebSearch", data["permissions"]["allow"])

        settings = os.path.join(self.tmp, "agents", "probe", ".claude", "settings.json")
        self.assertTrue(os.path.isfile(settings))
        with open(settings, encoding="utf-8") as fh:
            self.assertIn("WebSearch", json.load(fh)["permissions"]["allow"])

    def test_w10_dry_run_predicts_the_generated_files_too(self):
        dry = self.run_scaffold(
            "--name", "probe", "--description", "Probe.", "--dry-run"
        )
        real = self.run_scaffold("--name", "probe", "--description", "Probe.")
        self.assertEqual(
            json.loads(dry.stdout)["data"]["files"],
            json.loads(real.stdout)["data"]["files"],
        )


if __name__ == "__main__":
    unittest.main()
