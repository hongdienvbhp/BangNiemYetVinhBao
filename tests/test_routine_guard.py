import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.routine_guard import evaluate

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

class RoutineGuardTests(unittest.TestCase):
    def test_pause_wins(self):
        r = evaluate(now=datetime(2026, 9, 21, 7, 30, tzinfo=TZ), event="schedule", paused=True, force=False, history={}, current_run_id="2")
        self.assertEqual(r["status"], "SKIPPED_PAUSED")

    def test_scheduled_out_of_window_skips(self):
        r = evaluate(now=datetime(2026, 9, 21, 13, 0, tzinfo=TZ), event="schedule", paused=False, force=False, history={}, current_run_id="2")
        self.assertEqual(r["status"], "SKIPPED_OUT_OF_WINDOW")

    def test_success_same_period_skips_duplicate(self):
        history = {"workflow_runs":[{"id":1,"status":"completed","conclusion":"success","created_at":"2026-09-21T00:40:00Z"}]}
        r = evaluate(now=datetime(2026, 9, 21, 8, 0, tzinfo=TZ), event="schedule", paused=False, force=False, history=history, current_run_id="2")
        self.assertEqual(r["status"], "SKIPPED_ALREADY_RAN")

    def test_failed_same_period_allows_retry(self):
        history = {"workflow_runs":[{"id":1,"status":"completed","conclusion":"failure","created_at":"2026-09-21T00:40:00Z"}]}
        r = evaluate(now=datetime(2026, 9, 21, 8, 0, tzinfo=TZ), event="schedule", paused=False, force=False, history=history, current_run_id="2")
        self.assertTrue(r["run"])

    def test_manual_force_can_repeat_but_pause_still_wins(self):
        history = {"workflow_runs":[{"id":1,"status":"completed","conclusion":"success","created_at":"2026-09-21T00:40:00Z"}]}
        r = evaluate(now=datetime(2026, 9, 21, 20, 0, tzinfo=TZ), event="workflow_dispatch", paused=False, force=True, history=history, current_run_id="2")
        self.assertTrue(r["run"])

if __name__ == "__main__":
    unittest.main()
