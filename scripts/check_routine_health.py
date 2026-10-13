#!/usr/bin/env python3
"""Evaluate daily routine health from workflow history and terminal run records."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
EXPECTED_BY = time(12, 15)
UNHEALTHY_STATES = {"STOPPED_LOUDLY", "STOPPED_SILENTLY"}
HEALTHY_TERMINAL = {"OK"}
# A pending human approval is an explicit review gate, not an operational failure.
# It is handled as BLOCKED_FOR_REVIEW below and must remain outside LOUD_TERMINAL.
LOUD_TERMINAL = {
    "PARTIAL",
    "FAILED",
    "SKIPPED_OUT_OF_WINDOW",
    "BLOCKED_AUTH",
    "BLOCKED_SOURCE",
}


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LOCAL_TZ)


def local_now(value: str | None) -> datetime:
    if value:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt.astimezone(LOCAL_TZ)
    return datetime.now(timezone.utc).astimezone(LOCAL_TZ)


def period_runs(history: dict, period_key: str) -> list[dict]:
    rows = []
    for run in history.get("workflow_runs", []):
        created = run.get("created_at")
        if created and parse_ts(created).date().isoformat() == period_key:
            rows.append(run)
    return rows


def load_records(records_dir: str | None) -> dict[str, dict]:
    if not records_dir:
        return {}
    root = Path(records_dir)
    if not root.exists():
        return {}

    records: dict[str, dict] = {}
    for path in root.rglob("routine-run-record.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run_id = str(record.get("run_id") or "").strip()
        if run_id:
            records[run_id] = record
    return records


def evaluate(history: dict, records: dict[str, dict], now: datetime) -> dict:
    local = now.astimezone(LOCAL_TZ)
    period_key = local.date().isoformat()
    if local.timetz().replace(tzinfo=None) < EXPECTED_BY:
        return {
            "state": "NOT_DUE",
            "period_key": period_key,
            "reason": "health deadline not reached",
        }

    today = period_runs(history, period_key)
    if not today:
        return {
            "state": "STOPPED_SILENTLY",
            "period_key": period_key,
            "reason": "expected run missing",
        }

    today_ids = {str(run.get("id") or "") for run in today}
    today_records = {
        run_id: record
        for run_id, record in records.items()
        if run_id in today_ids and record.get("period_key") == period_key
    }

    # Evaluate the latest run, not any historical OK. GitHub returns runs by
    # creation time; use the timestamp and preserve list order for equal times.
    latest_index, latest_run = max(
        enumerate(today),
        key=lambda item: (str(item[1].get("created_at") or ""), -item[0]),
    )
    latest_run_id = str(latest_run.get("id") or "")
    latest_record = today_records.get(latest_run_id)
    latest_status = str((latest_record or {}).get("status") or "")

    if latest_run.get("status") in {"queued", "in_progress", "waiting", "requested", "pending"}:
        return {
            "state": "RUNNING",
            "period_key": period_key,
            "reason": "latest workflow run still active",
        }

    if not latest_record:
        if latest_run.get("conclusion") not in {"success", "skipped"}:
            reason = "workflow completed unsuccessfully"
        else:
            reason = "latest workflow run observed without terminal routine record"
        return {
            "state": "STOPPED_LOUDLY",
            "period_key": period_key,
            "reason": reason,
        }

    # A terminal record cannot override a failed or cancelled GitHub run.
    # This guards against post-step/runner failures after an OK record was written.
    if (
        latest_status in HEALTHY_TERMINAL | {"SKIPPED_ALREADY_RAN", "SKIPPED_PAUSED", "BLOCKED_HUMAN_APPROVAL"}
        and latest_run.get("conclusion") != "success"
    ):
        conclusion = str(latest_run.get("conclusion") or "unknown")
        return {
            "state": "STOPPED_LOUDLY",
            "period_key": period_key,
            "reason": (
                "latest workflow conclusion is "
                + conclusion
                + " despite terminal routine status: "
                + latest_status
            ),
        }

    if latest_status == "BLOCKED_HUMAN_APPROVAL":
        # A completed scan awaiting a person is a visible gate, not a failed routine.
        # The workflow-conclusion guard above still prevents this record masking failure.
        note = str(latest_record.get("note") or "").strip()
        reason = "human approval is required for the pending official TTHC candidate"
        if note:
            reason += ": " + note
        return {
            "state": "BLOCKED_FOR_REVIEW",
            "period_key": period_key,
            "reason": reason,
        }

    if latest_status in HEALTHY_TERMINAL:
        return {
            "state": "HEALTHY",
            "period_key": period_key,
            "reason": "latest terminal OK record observed",
        }

    if latest_status == "SKIPPED_ALREADY_RAN":
        latest_created = str(latest_run.get("created_at") or "")
        # A duplicate skip is benign only when a prior run in this period
        # has a real OK record. A later PARTIAL/FAILED run must never be masked.
        prior_ok = False
        for index, run in enumerate(today):
            run_id = str(run.get("id") or "")
            record = today_records.get(run_id)
            if run_id == latest_run_id or not record or record.get("status") != "OK":
                continue
            created = str(run.get("created_at") or "")
            if created < latest_created or (created == latest_created and index > latest_index):
                prior_ok = True
                break
        if prior_ok:
            return {
                "state": "HEALTHY",
                "period_key": period_key,
                "reason": "latest run was a duplicate skip; prior OK record exists for period",
            }
        return {
            "state": "STOPPED_LOUDLY",
            "period_key": period_key,
            "reason": "duplicate-skip observed without a prior OK run record for the period",
        }

    if latest_status == "SKIPPED_PAUSED":
        return {
            "state": "PAUSED",
            "period_key": period_key,
            "reason": "routine explicitly paused",
        }

    if latest_status in LOUD_TERMINAL:
        return {
            "state": "STOPPED_LOUDLY",
            "period_key": period_key,
            "reason": "latest terminal routine status: " + latest_status,
        }

    return {
        "state": "STOPPED_LOUDLY",
        "period_key": period_key,
        "reason": "no healthy latest terminal routine status observed",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--history", required=True)
    p.add_argument("--records-dir")
    p.add_argument("--now")
    p.add_argument("--github-output")
    p.add_argument("--fail-unhealthy", action="store_true")
    p.add_argument("--print-period-run-ids", action="store_true")
    args = p.parse_args()

    history = json.loads(Path(args.history).read_text(encoding="utf-8"))
    now = local_now(args.now)
    period_key = now.date().isoformat()

    if args.print_period_run_ids:
        for run in period_runs(history, period_key):
            run_id = str(run.get("id") or "").strip()
            if run_id:
                print(run_id)
        return 0

    result = evaluate(history, load_records(args.records_dir), now)

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            for key in ("state", "period_key", "reason"):
                f.write(f"{key}={result[key]}\n")

    print(json.dumps(result, ensure_ascii=False))
    if args.fail_unhealthy and result["state"] in UNHEALTHY_STATES:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
