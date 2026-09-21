#!/usr/bin/env python3
"""Deterministic guard for scheduled routines.

No network access. GitHub Actions history is supplied as JSON by the workflow.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ROUTINE_ID = "tthc-official-source-update"
WINDOW_START = time(6, 0)
WINDOW_END = time(12, 0)

def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

def parse_github_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LOCAL_TZ)

def local_now(value: str | None) -> datetime:
    if value:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=LOCAL_TZ)
        return dt.astimezone(LOCAL_TZ)
    return datetime.now(timezone.utc).astimezone(LOCAL_TZ)

def successful_run_in_period(history: dict, period_key: str, current_run_id: str) -> bool:
    for run in history.get("workflow_runs", []):
        if str(run.get("id")) == str(current_run_id):
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        created = run.get("created_at")
        if not created:
            continue
        if parse_github_ts(created).date().isoformat() == period_key:
            return True
    return False

def evaluate(*, now: datetime, event: str, paused: bool, force: bool, history: dict, current_run_id: str) -> dict:
    period_key = now.date().isoformat()

    if paused:
        return {"run": False, "status": "SKIPPED_PAUSED", "reason": "repository pause variable is enabled", "period_key": period_key}

    if event == "schedule":
        current_time = now.timetz().replace(tzinfo=None)
        if not (WINDOW_START <= current_time <= WINDOW_END):
            return {
                "run": False,
                "status": "SKIPPED_OUT_OF_WINDOW",
                "reason": f"scheduled fire outside {WINDOW_START.strftime('%H:%M')}-{WINDOW_END.strftime('%H:%M')} Asia/Ho_Chi_Minh",
                "period_key": period_key,
            }

    if not force and successful_run_in_period(history, period_key, current_run_id):
        return {"run": False, "status": "SKIPPED_ALREADY_RAN", "reason": "successful run already observed for period", "period_key": period_key}

    return {"run": True, "status": "READY", "reason": "guard passed", "period_key": period_key}

def write_github_outputs(path: str | None, result: dict) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"run={'true' if result['run'] else 'false'}\n")
        f.write(f"status={result['status']}\n")
        f.write(f"period_key={result['period_key']}\n")
        f.write(f"reason={result['reason']}\n")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--paused", default="false")
    parser.add_argument("--force", default="false")
    parser.add_argument("--now")
    parser.add_argument("--github-output")
    args = parser.parse_args()

    history = json.loads(Path(args.history).read_text(encoding="utf-8"))
    result = evaluate(
        now=local_now(args.now),
        event=args.event,
        paused=parse_bool(args.paused),
        force=parse_bool(args.force),
        history=history,
        current_run_id=args.run_id,
    )
    write_github_outputs(args.github_output, result)
    print(json.dumps({"routine_id": ROUTINE_ID, **result}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
