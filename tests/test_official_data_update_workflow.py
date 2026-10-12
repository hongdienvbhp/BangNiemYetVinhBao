import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "official-data-update.yml"
)


class OfficialDataUpdateWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_open_candidate_does_not_skip_source_scan(self):
        self.assertIn('echo "review_pending=true" >> "$GITHUB_OUTPUT"', self.workflow)
        self.assertNotIn("steps.existing.outputs.skip", self.workflow)
        self.assertIn(
            "- name: Scan official sources\n"
            "        if: steps.guard.outputs.run == 'true'",
            self.workflow,
        )

    def test_open_candidate_is_preserved_and_reported_as_human_gate(self):
        self.assertIn("Preserve delta while candidate review is pending", self.workflow)
        self.assertIn("Upload pending candidate review delta", self.workflow)
        self.assertIn(
            "steps.existing.outputs.review_pending != 'true' && steps.changes.outputs.changed == 'true'",
            self.workflow,
        )
        self.assertIn("status=\"BLOCKED_HUMAN_APPROVAL\"", self.workflow)
        self.assertIn("official source scan completed; automated PR", self.workflow)


if __name__ == "__main__":
    unittest.main()
