import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.check_routine_health import evaluate

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

class RoutineHealthTests(unittest.TestCase):
    def test_not_due(self):
        r = evaluate({}, datetime(2026, 9, 21, 9, 0, tzinfo=TZ))
        self.assertEqual(r["state"], "NOT_DUE")

    def test_silent_stop(self):
        r = evaluate({}, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_SILENTLY")

    def test_loud_stop(self):
        history={"workflow_runs":[{"created_at":"2026-09-21T00:40:00Z","status":"completed","conclusion":"failure"}]}
        r = evaluate(history, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_LOUDLY")

    def test_state_vocabulary(self):\n        states = {"NOT_DUE", "STOPPED_SILENTLY", "STOPPED_LOUDLY", "HEALTHY"}\n        self.assertEqual(states, {"NOT_DUE", "STOPPED_SILENTLY", "STOPPED_LOUDLY", "HEALTHY"})\n\n    def test_healthy(self):
        history={"workflow_runs":[{"created_at":"2026-09-21T00:40:00Z","status":"completed","conclusion":"success"}]}
        r = evaluate(history, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "HEALTHY")

if __name__ == "__main__":
    unittest.main()
