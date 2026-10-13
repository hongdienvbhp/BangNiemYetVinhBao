"""Cross-PR integration contract for pending TTHC candidate review.

The terminal status writer is proposed by PR #164. The evaluator policy is
from the exact reviewed head of PR #163, loaded from git history so these tests
exercise the two PR contracts together without copying production logic.
"""
import subprocess
import types
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
UPDATE_WORKFLOW = ROOT / ".github" / "workflows" / "official-data-update.yml"
PR163_HEALTH_COMMIT = "0fe61253b859af19965a26aec03135d74487aa5f"
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
PERIOD = "2026-10-13"
NOW = datetime(2026, 10, 13, 12, 30, tzinfo=TZ)
RUN_ID = "integration-pending-review"


def load_pr163_health_evaluator():
    """Load the exact #163 evaluator from the repository's fetched Git history."""
    result = subprocess.run(
        [
            "git",
            "show",
            f"{PR163_HEALTH_COMMIT}:scripts/check_routine_health.py",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    module = types.ModuleType("pr163_check_routine_health")
    module.__file__ = f"{PR163_HEALTH_COMMIT}:scripts/check_routine_health.py"
    exec(compile(result.stdout, module.__file__, "exec"), module.__dict__)
    return module


def history(conclusion="success"):
    return {
        "workflow_runs": [
            {
                "id": RUN_ID,
                "created_at": "2026-10-13T02:00:00Z",
                "status": "completed",
                "conclusion": conclusion,
            }
        ]
    }


def terminal_record(status):
    return {
        RUN_ID: {
            "run_id": RUN_ID,
            "period_key": PERIOD,
            "status": status,
            "note": "official source scan completed; automated candidate PR remains under review",
        }
    }


class PendingReviewIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.health = load_pr163_health_evaluator()
        cls.workflow = UPDATE_WORKFLOW.read_text(encoding="utf-8")

    def test_pr164_terminal_record_maps_to_pr163_review_gate(self):
        # Assert the writer in #164 produces the interface consumed by #163.
        self.assertIn('status="BLOCKED_HUMAN_APPROVAL"', self.workflow)
        self.assertIn('elif [ "${REVIEW_PENDING:-}" = "true" ]; then', self.workflow)
        self.assertIn('elif [ "$JOB_STATUS" = "failure" ]; then', self.workflow)
        self.assertIn('elif [ "${VALIDATION_OUTCOME:-}" != "success" ]', self.workflow)

        result = self.health.evaluate(
            history("success"),
            terminal_record("BLOCKED_HUMAN_APPROVAL"),
            NOW,
        )
        self.assertEqual(result["state"], "BLOCKED_FOR_REVIEW")
        self.assertNotIn(result["state"], self.health.UNHEALTHY_STATES)
        self.assertIn("human approval", result["reason"])

    def test_failed_workflow_cannot_be_masked_by_pr164_review_status(self):
        result = self.health.evaluate(
            history("failure"),
            terminal_record("BLOCKED_HUMAN_APPROVAL"),
            NOW,
        )
        self.assertEqual(result["state"], "STOPPED_LOUDLY")
        self.assertIn("failure", result["reason"])

    def test_incomplete_scan_remains_operationally_unhealthy(self):
        result = self.health.evaluate(
            history("success"),
            terminal_record("PARTIAL"),
            NOW,
        )
        self.assertEqual(result["state"], "STOPPED_LOUDLY")


if __name__ == "__main__":
    unittest.main()
