"""
test_scaffold.py — scaffold-agent.py, cases S1-S17 from docs/testing.md.

Unlike the other scripts under test, scaffold-agent.py has a side effect
(files on disk) as well as an exit code and stdout, so most of these tests
check both: what the JSON envelope claims happened, and what actually landed
in $AGENT_TOOLKIT_HOME/agents/.

S5 is the one that matters most for D19: a form-only caller has to be able to
preview the exact manifest a real run will produce, with nothing written,
before committing to it.

scaffold-agent.py emits the cli_output envelope unconditionally (D16) — there
is no plain-text mode to fall back to — so every assertion here reads
`data["data"]` for the payload and `data["errors"]` for what went wrong.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, load_fixture


class ScaffoldAgentTests(ToolkitTestCase):
    def setUp(self):
        super().setUp()
        self.write_baseline("baseline-valid.yaml")

    def agent_dir(self, name):
        return os.path.join(self.tmp, "agents", name)

    def test_s1_minimal_agent_is_valid_no_warnings(self):
        result = self.run_scaffold("--name", "probe", "--description", "Test probe.")
        self.assertEqual(result.returncode, 0, result.stdout)
        envelope = json.loads(result.stdout)

        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["errors"], [])
        self.assertTrue(envelope["data"]["validation"]["ok"])

        # A fresh agent is valid but *unfinished*: its process still carries
        # the seeded TODO: step. That is the one warning it should have, and
        # it should have it — see S11.
        self.assertEqual(
            [w["field"] for w in envelope["warnings"]], ["CLAUDE.md"],
            "a fresh scaffold should warn about its unwritten intent and nothing else",
        )

        target = self.agent_dir("probe")
        for rel in ("agent.yaml", "CLAUDE.md", "README.md", "steering.md", "output/.gitkeep"):
            self.assertTrue(
                os.path.isfile(os.path.join(target, *rel.split("/"))),
                "%s was not written" % rel,
            )

        with open(os.path.join(target, "CLAUDE.md"), encoding="utf-8") as fh:
            claude_md = fh.read()
        self.assertIn("# probe", claude_md)
        self.assertNotIn("{{AGENT_NAME}}", claude_md)
        self.assertNotIn("{{AGENT_DESCRIPTION}}", claude_md)

    def test_s2_agent_with_two_overrides_resolves_both(self):
        result = self.run_scaffold(
            "--name", "probe",
            "--description", "Test probe.",
            "--set", "operating_constraints.pattern=pipeline",
            "--set", "voice_style.verbosity=expansive",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)["data"]

        self.assertEqual(
            data["overrides"]["operating_constraints"]["pattern"], "pipeline"
        )
        self.assertEqual(data["overrides"]["voice_style"]["verbosity"], "expansive")
        self.assertTrue(data["validation"]["ok"])

        agent_yaml = os.path.join(self.agent_dir("probe"), "agent.yaml")
        result = self.run_validate_agent(agent_yaml)
        self.assertEqual(result.returncode, 0, result.stdout)

        resolved = self.run_resolve(agent_yaml, "--json")
        resolved_data = json.loads(resolved.stdout)["data"]
        self.assertEqual(
            resolved_data["resolved"]["operating_constraints"]["pattern"], "pipeline"
        )
        self.assertEqual(
            resolved_data["resolved"]["voice_style"]["verbosity"], "expansive"
        )

    def test_s3_existing_directory_is_refused_without_force(self):
        first = self.run_scaffold("--name", "probe", "--description", "Test probe.")
        self.assertEqual(first.returncode, 0, first.stdout)

        second = self.run_scaffold("--name", "probe", "--description", "Second attempt.")
        self.assertEqual(second.returncode, 1)
        envelope = json.loads(second.stdout)
        self.assertFalse(envelope["ok"])
        self.assertEqual(len(envelope["errors"]), 1)
        self.assertIn("already exists", envelope["errors"][0]["message"])
        self.assertIsNotNone(envelope["errors"][0]["fix"])

        # --force clears the way (rewriting agent.yaml; see S6 for what it leaves).
        third = self.run_scaffold(
            "--name", "probe", "--description", "Overwritten.", "--force"
        )
        self.assertEqual(third.returncode, 0, third.stdout)
        with open(os.path.join(self.agent_dir("probe"), "agent.yaml"), encoding="utf-8") as fh:
            self.assertIn("Overwritten.", fh.read())

    def test_s4_bad_slug_is_refused(self):
        result = self.run_scaffold("--name", "Not_A_Slug!", "--description", "Test.")
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        self.assertFalse(envelope["ok"])
        self.assertEqual(len(envelope["errors"]), 1)
        self.assertEqual(envelope["errors"][0]["field"], "name")
        self.assertIn("not a valid slug", envelope["errors"][0]["message"])
        self.assertFalse(os.path.exists(self.agent_dir("Not_A_Slug!")))

    def test_s6_force_preserves_everything_the_user_owns(self):
        """
        The agent-directory ownership rule, enforced. `--force` used to
        rmtree the directory, which silently destroyed the process the user
        had written, their steering notes, and every result in output/.
        Only agent.yaml is the toolkit's to rewrite — see docs/architecture.md.
        """
        first = self.run_scaffold("--name", "probe", "--description", "First.")
        self.assertEqual(first.returncode, 0, first.stdout)

        target = self.agent_dir("probe")
        mine = {
            "CLAUDE.md": "\n5. a step I wrote myself\n",
            "steering.md": "\nalways name the owner of an action item\n",
        }
        for rel, extra in mine.items():
            with open(os.path.join(target, rel), "a", encoding="utf-8") as fh:
                fh.write(extra)
        result_file = os.path.join(target, "output", "report.md")
        with open(result_file, "w", encoding="utf-8") as fh:
            fh.write("a result worth keeping")

        second = self.run_scaffold(
            "--name", "probe", "--description", "Second.", "--force"
        )
        self.assertEqual(second.returncode, 0, second.stdout)
        data = json.loads(second.stdout)["data"]

        self.assertEqual(data["written"], ["agent.yaml"])
        self.assertIn("steering.md", data["preserved"])
        self.assertIn("CLAUDE.md", data["preserved"])

        for rel, extra in mine.items():
            with open(os.path.join(target, rel), encoding="utf-8") as fh:
                self.assertIn(extra.strip(), fh.read(), "%s was clobbered" % rel)

        self.assertTrue(os.path.isfile(result_file), "output/ was destroyed")
        with open(result_file, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "a result worth keeping")

        # The point of --force is still that the config gets updated.
        with open(os.path.join(target, "agent.yaml"), encoding="utf-8") as fh:
            self.assertIn("Second.", fh.read())

    def _capabilities_written(self, name):
        with open(os.path.join(self.agent_dir(name), "agent.yaml"), encoding="utf-8") as fh:
            import yaml
            return (yaml.safe_load(fh) or {}).get(
                "operating_constraints", {}
            ).get("permissions_scope", {}).get("capabilities")

    def test_s7_no_web_writes_the_whole_set_minus_web(self):
        """
        The array-replace trap. `--no-web` cannot be written as a delta:
        `capabilities` replaces the inherited list wholesale, so writing only
        the web entries would strip the file access nobody asked to remove.
        """
        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.", "--no-web"
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)["data"]

        self.assertEqual(data["capabilities"]["removed"], ["web.search", "web.fetch"])
        self.assertEqual(data["capabilities"]["source"], "--no-web")

        written = self._capabilities_written("probe")
        self.assertEqual(written, ["file.read", "file.search", "file.write"])
        self.assertNotIn("web.search", written)

        permissions = data["permissions"]
        self.assertNotIn("WebSearch", permissions["allow"])
        self.assertNotIn("WebFetch", permissions["allow"])
        # Deliberately withheld, so denied outright rather than left to prompt.
        self.assertIn("WebSearch", permissions["deny"])
        self.assertIn("WebFetch", permissions["deny"])

    def test_s8_web_on_a_cautious_baseline_adds_only_what_is_missing(self):
        text = load_fixture("baseline-valid.yaml").replace(
            '    capabilities: ["file.read", "file.search", "file.write", '
            '"web.search", "web.fetch"]',
            '    capabilities: ["file.read", "file.search", "web.search"]',
        )
        baseline = self.write("baseline.yaml", text)

        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.",
            "--extends", baseline, "--web",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        capabilities = json.loads(result.stdout)["data"]["capabilities"]

        # web.search is granted at every posture (D12), so only fetch is new.
        self.assertEqual(capabilities["added"], ["web.fetch"])
        self.assertEqual(capabilities["removed"], [])
        self.assertEqual(
            capabilities["effective"],
            ["file.read", "file.search", "web.search", "web.fetch"],
        )

    def test_s9_a_web_flag_that_changes_nothing_writes_no_override(self):
        """
        `--web` on a baseline that already grants both. Restating an inherited
        value pins the field against future baseline edits — D3, and the
        hygiene warning validate-agent.py raises for exactly this.
        """
        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.", "--web"
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        envelope = json.loads(result.stdout)

        self.assertEqual(
            envelope["data"]["capabilities"]["source"], "baseline (unchanged)"
        )
        self.assertIsNone(self._capabilities_written("probe"))
        self.assertEqual(
            [w for w in envelope["warnings"] if "same value as the baseline" in w["message"]],
            [],
            "a no-op web flag should not produce a redundant override",
        )

    def test_s10_a_web_flag_conflicting_with_an_explicit_set_is_refused(self):
        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.", "--no-web",
            "--set", "operating_constraints.permissions_scope.capabilities=[\"file.read\"]",
        )
        self.assertEqual(result.returncode, 1)
        envelope = json.loads(result.stdout)
        self.assertFalse(envelope["ok"])
        self.assertIn("both set the capability list", envelope["errors"][0]["message"])

    def test_s11_the_process_is_seeded_from_the_pattern(self):
        """
        The open question this backlog carried from the start. Guessing at
        *intent* produces confident nonsense, but the scaffolding around it —
        confirm the inputs, check the result — is a property of the pattern,
        so the toolkit can write it. Only the intent step stays the user's.
        """
        result = self.run_scaffold("--name", "probe", "--description", "Probe.")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["data"]["pattern"], "standalone")

        with open(os.path.join(self.agent_dir("probe"), "CLAUDE.md"), encoding="utf-8") as fh:
            text = fh.read()
        process = text[text.index("## Process"):text.index("## Notes")]

        steps = [l for l in process.splitlines() if l[:2] in ("1.", "2.", "3.", "4.")]
        self.assertEqual(len(steps), 4, process)
        self.assertEqual(len([s for s in steps if "TODO:" in s]), 1)
        self.assertNotIn("{{PROCESS}}", text)

    def test_s11b_the_seeded_process_carries_no_module_frontmatter(self):
        """
        A pattern module is markdown with YAML frontmatter, and the frontmatter
        is metadata for the toolkit rather than instructions for the agent.
        Seeding once read the file raw, which put a `---` block naming `kind`
        and `requires_capabilities` at the top of the user's Process section.
        """
        result = self.run_scaffold("--name", "probe", "--description", "Probe.")
        self.assertEqual(result.returncode, 0, result.stdout)

        with open(os.path.join(self.agent_dir("probe"), "CLAUDE.md"), encoding="utf-8") as fh:
            text = fh.read()
        process = text[text.index("## Process"):text.index("## Notes")]

        for leaked in ("---", "kind:", "requires_capabilities:", "conflicts_with:",
                       "schema_version:", "summary:"):
            self.assertNotIn(leaked, process, process)

        # The first non-blank line after the header is the first step.
        body = process.splitlines()[1:]
        first = next(l for l in body if l.strip())
        self.assertTrue(first.startswith("1."), first)

    def test_s12_a_different_pattern_gets_a_different_skeleton(self):
        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.",
            "--set", "operating_constraints.pattern=evaluator-optimizer",
            "--set", "operating_constraints.evaluation_loop.enabled=true",
            "--set", "operating_constraints.evaluation_loop.reviewer=self",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            json.loads(result.stdout)["data"]["pattern"], "evaluator-optimizer"
        )

        with open(os.path.join(self.agent_dir("probe"), "CLAUDE.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("Review your own draft", text)
        # max_cycles is substituted from the resolved config, not left a token.
        self.assertIn("at most 3 times", text)
        self.assertNotIn("{{MAX_CYCLES}}", text)

    def test_s13_validation_warns_until_the_intent_is_written(self):
        self.run_scaffold("--name", "probe", "--description", "Probe.")
        agent_yaml = os.path.join(self.agent_dir("probe"), "agent.yaml")

        result = self.run_validate_agent(agent_yaml, "--json")
        warnings = json.loads(result.stdout)["warnings"]
        self.assertTrue(any("TODO:" in w["message"] for w in warnings))

        # Write the intent, and the warning goes away.
        path = os.path.join(self.agent_dir("probe"), "CLAUDE.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(
                "2. TODO: the work this agent does. Replace this step.",
                "2. Read the contract and list every clause that shifts risk.",
            ))

        result = self.run_validate_agent(agent_yaml, "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        warnings = json.loads(result.stdout)["warnings"]
        self.assertFalse([w for w in warnings if "TODO:" in w["message"]])

    def test_s14_merge_keeps_every_override_it_was_not_asked_about(self):
        """
        The trap `--merge` exists to close. Without it, scaffold rewrites
        agent.yaml from the flags it was given, so editing one field silently
        drops the rest — the same family of loss as the rmtree 3.5 removed.
        """
        self.run_scaffold(
            "--name", "probe", "--description", "Probe.",
            "--set", "voice_style.verbosity=expansive",
            "--set", "operating_constraints.model=claude-opus-5",
            "--compose", "role/reviewer",
        )

        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.",
            "--merge", "--set", "voice_style.verbosity=standard",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

        overrides = json.loads(result.stdout)["data"]["overrides"]
        self.assertEqual(overrides["voice_style"]["verbosity"], "standard")
        self.assertEqual(
            overrides["operating_constraints"]["model"], "claude-opus-5",
            "the model override was dropped by an edit that never mentioned it",
        )
        self.assertEqual(overrides["compose"], ["role/reviewer"])

    def test_s15_merge_preserves_sibling_leaves(self):
        """Same leaf-merge rule the resolver uses, applied within one file."""
        self.run_scaffold(
            "--name", "probe", "--description", "Probe.",
            "--set", "operating_constraints.guardrails.human_in_the_loop=true",
        )
        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.", "--merge",
            "--set", "operating_constraints.guardrails.output_validation=false",
        )
        guardrails = json.loads(result.stdout)["data"]["overrides"][
            "operating_constraints"]["guardrails"]
        self.assertIs(guardrails["human_in_the_loop"], True)
        self.assertIs(guardrails["output_validation"], False)

    def test_s16_without_merge_the_old_behaviour_is_unchanged(self):
        """
        `--force` alone still replaces. That is correct for re-creating an
        agent from a fresh interview, which is what it was built for.
        """
        self.run_scaffold(
            "--name", "probe", "--description", "Probe.",
            "--set", "operating_constraints.model=claude-opus-5",
        )
        result = self.run_scaffold(
            "--name", "probe", "--description", "Probe.",
            "--force", "--set", "voice_style.verbosity=standard",
        )
        overrides = json.loads(result.stdout)["data"]["overrides"]
        self.assertNotIn("operating_constraints", overrides)

    def test_s17_merging_into_an_agent_that_does_not_exist_yet_is_a_scaffold(self):
        result = self.run_scaffold(
            "--name", "fresh", "--description", "Probe.", "--merge",
            "--set", "voice_style.verbosity=standard",
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            json.loads(result.stdout)["data"]["overrides"],
            {"voice_style": {"verbosity": "standard"}},
        )

    def test_s5_dry_run_manifest_matches_a_real_run_and_writes_nothing(self):
        dry = self.run_scaffold(
            "--name", "probe", "--description", "Test probe.",
            "--set", "operating_constraints.pattern=pipeline",
            "--dry-run",
        )
        self.assertEqual(dry.returncode, 0, dry.stdout)
        dry_data = json.loads(dry.stdout)["data"]
        self.assertTrue(dry_data["dry_run"])
        self.assertFalse(os.path.exists(self.agent_dir("probe")))

        real = self.run_scaffold(
            "--name", "probe", "--description", "Test probe.",
            "--set", "operating_constraints.pattern=pipeline",
        )
        self.assertEqual(real.returncode, 0, real.stdout)
        real_data = json.loads(real.stdout)["data"]

        self.assertEqual(dry_data["files"], real_data["files"])
        self.assertEqual(dry_data["overrides"], real_data["overrides"])
        self.assertEqual(dry_data["target"], real_data["target"])
        self.assertTrue(os.path.isdir(self.agent_dir("probe")))


if __name__ == "__main__":
    unittest.main()
