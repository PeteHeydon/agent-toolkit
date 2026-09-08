"""
test_schema_sync.py — the baseline and agent-override schemas define their
enums independently (an override must obey the same legal values as the
baseline). Nothing stops them drifting apart by hand-editing one schema and
not the other, so assert it here. See HANDOFF.md, "Known gaps" #1.

Same check as the one scripts/verify-toolkit.sh runs inline — kept here too
so it runs under `python3 -m unittest discover` without needing bash.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import schema_utils

BASELINE_SCHEMA = os.path.join(
    REPO_ROOT, "builders/bootstrap-agent/schema/baseline-profile.schema.json"
)
OVERRIDE_SCHEMA = os.path.join(
    REPO_ROOT, "builders/create-agent/schema/agent-override.schema.json"
)


class SchemaSyncTests(unittest.TestCase):
    def test_shared_enum_fields_agree_between_schemas(self):
        baseline_enums = schema_utils.extract_enums(schema_utils.load_schema(BASELINE_SCHEMA))
        override_enums = schema_utils.extract_enums(schema_utils.load_schema(OVERRIDE_SCHEMA))

        shared = set(baseline_enums) & set(override_enums)
        self.assertGreater(len(shared), 0, "expected at least one enum field shared by both schemas")

        for path in sorted(shared):
            self.assertEqual(
                baseline_enums[path], override_enums[path],
                "%s: baseline has %s, override has %s"
                % (path, sorted(baseline_enums[path]), sorted(override_enums[path])),
            )


if __name__ == "__main__":
    unittest.main()
