#!/usr/bin/env python3
"""Evaluate whether the daily Official TTHC Update produced an expected successful run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
EXPECTED_BY = time(12, 15)

def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LOCAL_TZ)

def evaluate(history: dict, now: datetime) -> dict:
    local = now.astimezone(LOCAL_TZ)
    period_key = local.date().isoformat()
    if local.timetz().replace(tzinfo=None) < EXPECTED_BY:
        return {"state": "NOT_DUE", "period_key": period_key, "reason": "health deadline not reached"}

    today = []
    for run in history.get("workflow_runs", []):
        created = run.get("created_at")
        if created and parse_ts(created).date().isoformat() == period_key:
            today.append(run)

    if any(r.get("status") == "completed" and r.get("conclusion") == "success" for r in today):
        return {"state": "HEALTHY", "period_key": period_key, "reason": "successful workflow run observed"}

    if today:
        return {"state": "STOPPED_LOUDLY", "period_key": period_key, "reason": "run observed but no successful completion"}

    return {"state": "STOPPED_SILENTLY", "period_key": period_key, "reason": "expected run missing"}

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--history", required=True)
    p.add_argument("--now")
    p.add_argument("--github-output")
    args = p.parse_args()

    history = json.loads(Path(args.history).read_text(encoding="utf-8"))
    if args.now:
        now = datetime.fromisoformat(args.now)
        if now.tzinfo is None:
            now = now.replace(tzinfo=LOCAL_TZ)
    else:
        now = datetime.now(timezone.utc)
    result = evaluate(history, now)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            for key in ("state", "period_key", "reason"):
                f.write(f"{key}={result[key]}\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
