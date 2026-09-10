"""
base.py — shared test scaffolding.

Not itself a test module (no Test* classes). Each test_*.py inserts this
directory onto sys.path and does `from base import ...` — plain, not a
package import — so the suite runs the same via `python3 -m unittest
discover -s tests` regardless of the caller's working directory.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
FIXTURES = os.path.join(TESTS_DIR, "fixtures")

DETECT_SCRIPT = os.path.join(REPO_ROOT, "builders/bootstrap-agent/scripts/detect-profile.sh")
DETECT_PY = os.path.join(REPO_ROOT, "builders/bootstrap-agent/scripts/detect-profile.py")
VALIDATE_PROFILE_SCRIPT = os.path.join(REPO_ROOT, "builders/bootstrap-agent/scripts/validate-profile.py")
VALIDATE_AGENT_SCRIPT = os.path.join(REPO_ROOT, "builders/create-agent/scripts/validate-agent.py")
RESOLVE_SCRIPT = os.path.join(REPO_ROOT, "builders/create-agent/scripts/resolve-config.py")
SCAFFOLD_SCRIPT = os.path.join(REPO_ROOT, "builders/create-agent/scripts/scaffold-agent.py")


def as_yaml_path(path):
    r"""
    Render a filesystem path so it survives being substituted into a
    double-quoted YAML scalar.

    Every fixture placeholder lands inside `extends: "{{BASELINE}}"`. On
    Windows a native path is `C:\Users\...`, and inside a double-quoted YAML
    scalar `\U` starts an escape sequence — so the fixture fails to parse and
    the test reports a resolver bug that isn't there. Forward slashes are
    accepted by the resolver on both platforms (it runs every path through
    os.path.abspath), so normalising here is a fix, not a workaround.
    """
    return str(path).replace("\\", "/")


def load_fixture(name, **substitutions):
    """
    Read a fixture and fill in any {{PLACEHOLDER}} tokens. Fixtures that
    reference a baseline or themselves (extends: "{{BASELINE}}", "{{SELF}}")
    can't bake in a real path — it only exists once a test copies them into
    its own tmpdir — so callers pass the resolved path in as a kwarg.

    Every substitution is a path, so all of them go through as_yaml_path().
    """
    path = os.path.join(FIXTURES, name)
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    for key, value in substitutions.items():
        text = text.replace("{{%s}}" % key, as_yaml_path(value))
    return text


class ToolkitTestCase(unittest.TestCase):
    """
    Isolates $AGENT_TOOLKIT_HOME to a fresh tmpdir per test, per the design
    point in docs/testing.md: a test that writes to a real ~/.agent-toolkit
    will eventually destroy someone's profile.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="agent-toolkit-test-")
        self.env = dict(os.environ)
        self.env["AGENT_TOOLKIT_HOME"] = self.tmp

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, relpath, content):
        path = os.path.join(self.tmp, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def write_baseline(self, fixture_name="baseline-valid.yaml"):
        return self.write("baseline.yaml", load_fixture(fixture_name))

    def run_detect(self, *args, **env_overrides):
        """Through the bash wrapper — the interpreter-probe entry point."""
        env = dict(self.env)
        env.update(env_overrides)
        return subprocess.run(
            ["bash", DETECT_SCRIPT, *args], env=env, cwd=REPO_ROOT,
            capture_output=True, text=True,
        )

    def run_detect_py(self, *args, **env_overrides):
        """
        The Python script directly, which is what the builders call.

        Both entry points are tested because they can drift: the wrapper is
        the only thing that can report a missing interpreter, and the .py is
        the only thing that reads the profile.
        """
        env = dict(self.env)
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, DETECT_PY, *args], env=env, cwd=REPO_ROOT,
            capture_output=True, text=True,
        )

    def run_validate_profile(self, path, *args):
        return subprocess.run(
            [sys.executable, VALIDATE_PROFILE_SCRIPT, path, *args], env=self.env, cwd=REPO_ROOT,
            capture_output=True, text=True,
        )

    def run_validate_agent(self, path, *args):
        return subprocess.run(
            [sys.executable, VALIDATE_AGENT_SCRIPT, path, *args], env=self.env, cwd=REPO_ROOT,
            capture_output=True, text=True,
        )

    def run_resolve(self, *args):
        return subprocess.run(
            [sys.executable, RESOLVE_SCRIPT, *args], env=self.env, cwd=REPO_ROOT,
            capture_output=True, text=True,
        )

    def run_scaffold(self, *args):
        return subprocess.run(
            [sys.executable, SCAFFOLD_SCRIPT, *args], env=self.env, cwd=REPO_ROOT,
            capture_output=True, text=True,
        )
