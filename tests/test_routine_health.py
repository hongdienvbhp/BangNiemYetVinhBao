import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.check_routine_health import evaluate

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def run(run_id, *, created_at="2026-09-21T00:40:00Z", status="completed", conclusion="success"):
    return {
        "id": run_id,
        "created_at": created_at,
        "status": status,
        "conclusion": conclusion,
    }


def record(run_id, status, *, period_key="2026-09-21"):
    return {
        "run_id": str(run_id),
        "period_key": period_key,
        "status": status,
    }


class RoutineHealthTests(unittest.TestCase):
    def test_not_due(self):
        r = evaluate({}, {}, datetime(2026, 9, 21, 9, 0, tzinfo=TZ))
        self.assertEqual(r["state"], "NOT_DUE")

    def test_silent_stop(self):
        r = evaluate({}, {}, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_SILENTLY")

    def test_workflow_failure_is_loud_stop(self):
        history = {"workflow_runs": [run(1, conclusion="failure")]}
        r = evaluate(history, {}, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_LOUDLY")

    def test_workflow_success_without_terminal_record_is_loud_stop(self):
        history = {"workflow_runs": [run(1)]}
        r = evaluate(history, {}, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_LOUDLY")
        self.assertIn("without terminal", r["reason"])

    def test_ok_terminal_record_is_healthy(self):
        history = {"workflow_runs": [run(1)]}
        records = {"1": record(1, "OK")}
        r = evaluate(history, records, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "HEALTHY")

    def test_out_of_window_is_loud_stop_even_when_workflow_success(self):
        history = {"workflow_runs": [run(1)]}
        records = {"1": record(1, "SKIPPED_OUT_OF_WINDOW")}
        r = evaluate(history, records, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_LOUDLY")
        self.assertIn("SKIPPED_OUT_OF_WINDOW", r["reason"])

    def test_partial_is_loud_stop(self):
        history = {"workflow_runs": [run(1)]}
        records = {"1": record(1, "PARTIAL")}
        r = evaluate(history, records, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_LOUDLY")

    def test_paused_is_explicit_state(self):
        history = {"workflow_runs": [run(1)]}
        records = {"1": record(1, "SKIPPED_PAUSED")}
        r = evaluate(history, records, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "PAUSED")

    def test_duplicate_skip_requires_ok_record_same_period(self):
        history = {"workflow_runs": [run(2), run(1)]}
        only_skip = {"2": record(2, "SKIPPED_ALREADY_RAN")}
        r = evaluate(history, only_skip, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_LOUDLY")

        with_ok = {
            "2": record(2, "SKIPPED_ALREADY_RAN"),
            "1": record(1, "OK"),
        }
        r = evaluate(history, with_ok, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "HEALTHY")

    def test_in_progress_is_running(self):
        history = {"workflow_runs": [run(1, status="in_progress", conclusion=None)]}
        r = evaluate(history, {}, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "RUNNING")

    def test_record_from_other_period_does_not_count(self):
        history = {"workflow_runs": [run(1)]}
        records = {"1": record(1, "OK", period_key="2026-09-20")}
        r = evaluate(history, records, datetime(2026, 9, 21, 12, 30, tzinfo=TZ))
        self.assertEqual(r["state"], "STOPPED_LOUDLY")


if __name__ == "__main__":
    unittest.main()
