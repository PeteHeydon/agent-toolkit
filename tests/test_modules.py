"""
test_modules.py — the module library, cases L1-L14 from docs/testing.md.

L1-L6 cover the format and loader (6.1), L7-L9 the nine shipped modules and
their index (6.2), L10-L11 composition into the generated region (6.3), and
L12-L14 the semantic checks (6.4).

L12 is the one the section was written for: an agent composed of research
guidance with no web access is exactly the failure this toolkit used to
produce in silence, discovered at run time. A module the agent cannot run is
worse than an absent one, because the agent has been told to do something it
cannot.

L5 is the quiet one. A personal module shadows a shipped module of the same
name — that is the point, so `git pull` cannot overwrite your guidance — but a
shadow nobody reports is a miserable thing to debug.
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import ToolkitTestCase, REPO_ROOT, load_fixture

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import module_utils

LIBRARY = os.path.join(REPO_ROOT, "library")
RENDER_SCRIPT = os.path.join(REPO_ROOT, "builders/create-agent/scripts/render-agent.py")

MODULE = """---
name: %(name)s
kind: %(kind)s
summary: %(summary)s
requires_capabilities: %(requires)s
conflicts_with: %(conflicts)s
schema_version: 1
---

- Do the thing.
"""


def module_text(name, kind="routine", summary="A test module.",
                requires="[]", conflicts="[]"):
    return MODULE % {"name": name, "kind": kind, "summary": summary,
                     "requires": requires, "conflicts": conflicts}


class ModuleFormatTests(ToolkitTestCase):
    """6.1 — the format and the loader."""

    def write_user_module(self, kind, name, text):
        path = os.path.join(self.tmp, "library", kind, "%s.md" % name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def setUp(self):
        super().setUp()
        # module_utils reads AGENT_TOOLKIT_HOME at call time, so point the
        # process at this test's tmpdir rather than the real one.
        os.environ["AGENT_TOOLKIT_HOME"] = self.tmp

    def tearDown(self):
        os.environ.pop("AGENT_TOOLKIT_HOME", None)
        super().tearDown()

    def test_l1_a_module_without_frontmatter_names_the_file(self):
        path = self.write_user_module("routine", "bare", "- Just a body.\n")
        with self.assertRaises(module_utils.ModuleError) as caught:
            module_utils.load("routine/bare")
        self.assertEqual(caught.exception.path, path)
        self.assertIn("frontmatter", str(caught.exception))

    def test_l2_a_missing_required_field_names_the_field(self):
        self.write_user_module(
            "routine", "nameless",
            "---\nkind: routine\nsummary: No name.\n---\n\n- Body.\n")
        with self.assertRaises(module_utils.ModuleError) as caught:
            module_utils.load("routine/nameless")
        self.assertEqual(caught.exception.field, "name")

    def test_l3_the_directory_and_the_frontmatter_must_agree(self):
        self.write_user_module("routine", "misfiled",
                               module_text("misfiled", kind="role"))
        with self.assertRaises(module_utils.ModuleError) as caught:
            module_utils.load("routine/misfiled")
        self.assertEqual(caught.exception.field, "kind")

    def test_l4_a_name_that_exists_nowhere_names_both_search_paths(self):
        with self.assertRaises(module_utils.ModuleError) as caught:
            module_utils.load("routine/nonexistent")
        message = str(caught.exception)
        self.assertIn(self.tmp, message)
        self.assertIn(LIBRARY, message)

    def test_l5_a_user_module_shadows_a_shipped_one_and_says_so(self):
        self.write_user_module(
            "routine", "web-research",
            module_text("web-research", summary="Mine, not theirs."))

        module = module_utils.load("routine/web-research")
        self.assertEqual(module["summary"], "Mine, not theirs.")
        self.assertTrue(module["shadows"], "shadowing was not reported")
        self.assertIn(LIBRARY, module["shadows"][0])

    def test_l6_an_overlong_body_warns(self):
        body = "\n".join("- Directive %d." % i for i in range(50))
        self.write_user_module(
            "routine", "verbose",
            "---\nname: verbose\nkind: routine\nsummary: Too long.\n---\n\n" + body)
        module = module_utils.load("routine/verbose")
        self.assertTrue(any("40-line limit" in w for w in module["warnings"]))


class ShippedLibraryTests(unittest.TestCase):
    """6.2 — the nine that ship, and the index."""

    def setUp(self):
        os.environ.pop("AGENT_TOOLKIT_HOME", None)
        self.modules, self.problems = module_utils.list_modules()

    def test_l7_every_shipped_module_loads_and_validates(self):
        self.assertEqual(
            [str(p) for p in self.problems], [], "a shipped module failed to load"
        )
        self.assertEqual(len(self.modules), 9, [m["id"] for m in self.modules])
        for module in self.modules:
            self.assertEqual(module["warnings"], [], module["id"])

    def test_l8_every_pattern_has_one_todo_step(self):
        patterns = [m for m in self.modules if m["kind"] == "pattern"]
        self.assertEqual(len(patterns), 3)
        for module in patterns:
            steps = [l for l in module["body"].splitlines()
                     if l[:1].isdigit() and l[1:2] in (".", ")")]
            self.assertGreaterEqual(len(steps), 4, module["id"])
            todos = [l for l in module["body"].splitlines() if "TODO:" in l]
            self.assertEqual(len(todos), 1, "%s: %d TODO steps" % (module["id"], len(todos)))

    def test_l9_the_index_matches_the_files_on_disk(self):
        """
        The README is the index. A module added without a row here, or a row
        left behind by a deleted module, fails the suite rather than quietly
        misleading whoever reads it.
        """
        with open(os.path.join(LIBRARY, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()

        for module in self.modules:
            self.assertIn(
                "`%s`" % module["id"], readme,
                "%s is on disk but not in library/README.md" % module["id"],
            )
            self.assertIn(module["summary"], readme, module["id"])

        listed = {line.split("`")[1] for line in readme.splitlines()
                  if line.startswith("| `") and "/" in line.split("`")[1]}
        self.assertEqual(
            listed - {m["id"] for m in self.modules}, set(),
            "library/README.md lists a module that is not on disk",
        )


class CompositionTests(ToolkitTestCase):
    """6.3 and 6.4 — composing into the region, and refusing what cannot work."""

    def setUp(self):
        super().setUp()
        self.baseline_path = self.write_baseline("baseline-valid.yaml")

    def build(self, name, *extra):
        result = self.run_scaffold(
            "--name", name, "--description", "Probe.",
            "--extends", self.baseline_path, *extra
        )
        return result.returncode, json.loads(result.stdout)

    def region(self, name):
        path = os.path.join(self.tmp, "agents", name, "CLAUDE.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        return text[text.index("<!-- BEGIN GENERATED"):text.index("<!-- END GENERATED -->")]

    def narrow_baseline(self, capabilities):
        """Rewrite from the fixture, not from the current file — narrowing twice
        off an already-narrowed baseline silently does nothing."""
        text = load_fixture("baseline-valid.yaml")
        self.baseline_path = self.write("baseline.yaml", text.replace(
            '    capabilities: ["file.read", "file.search", "file.write", '
            '"web.search", "web.fetch"]',
            "    capabilities: %s" % json.dumps(capabilities)))

    def test_l10_a_composed_module_is_inlined_and_removing_it_removes_it(self):
        code, _ = self.build("agent", "--compose", "routine/web-research")
        self.assertEqual(code, 0)
        region = self.region("agent")
        self.assertIn("## Composed modules", region)
        self.assertIn("Corroborate load-bearing claims", region)

        # Drop the module and re-render: the guidance goes with it.
        agent_dir = os.path.join(self.tmp, "agents", "agent")
        path = os.path.join(agent_dir, "agent.yaml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("- routine/web-research\n", ""))

        subprocess.run([sys.executable, RENDER_SCRIPT, agent_dir],
                       env=self.env, cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertNotIn("Composed modules", self.region("agent"))

    def test_l11_composing_nothing_renders_no_heading(self):
        self.build("plain")
        self.assertNotIn("Composed modules", self.region("plain"))

    def test_l12_a_module_whose_capabilities_are_missing_is_refused(self):
        """
        The failure this section exists to catch: research guidance on an
        agent that cannot reach the web.
        """
        self.narrow_baseline(["file.read", "file.search", "web.search"])
        code, envelope = self.build("no-fetch", "--compose", "routine/web-research")

        self.assertEqual(code, 1)
        self.assertFalse(envelope["ok"])
        error = [e for e in envelope["errors"] if e["field"] == "compose"][0]
        self.assertIn("routine/web-research", error["message"])
        self.assertIn("web.fetch", error["message"])
        self.assertIn("web.fetch", error["fix"])

        # Granting it makes the same agent pass.
        self.narrow_baseline(["file.read", "file.search", "web.search", "web.fetch"])
        code, envelope = self.build("with-fetch", "--compose", "routine/web-research")
        self.assertEqual(code, 0, envelope)

    def test_l13_more_than_four_modules_warns_but_passes(self):
        code, envelope = self.build(
            "many",
            "--compose", "role/researcher", "--compose", "role/reviewer",
            "--compose", "role/editor", "--compose", "routine/web-research",
            "--compose", "routine/document-summarise",
        )
        self.assertEqual(code, 0, envelope)
        self.assertTrue(
            [w for w in envelope["warnings"] if w.get("field") == "compose"],
            "five composed modules should warn",
        )

    def test_l14_composing_a_pattern_points_at_the_pattern_field(self):
        code, envelope = self.build("wrong", "--compose", "pattern/pipeline")
        self.assertEqual(code, 1)
        error = envelope["errors"][0]
        self.assertIn("patterns are not composed", error["message"])
        self.assertIn("operating_constraints.pattern", error["fix"])


if __name__ == "__main__":
    unittest.main()
