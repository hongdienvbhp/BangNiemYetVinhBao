#!/usr/bin/env python3
"""Write a minimal, non-sensitive routine terminal run record."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ALLOWED = {
    "OK",
    "PARTIAL",
    "FAILED",
    "SKIPPED_ALREADY_RAN",
    "SKIPPED_OUT_OF_WINDOW",
    "SKIPPED_PAUSED",
    "BLOCKED_AUTH",
    "BLOCKED_SOURCE",
    "BLOCKED_HUMAN_APPROVAL",
}

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--routine-id", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--period-key", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--status", required=True, choices=sorted(ALLOWED))
    p.add_argument("--source-commit", required=True)
    p.add_argument("--guard-status", required=True)
    p.add_argument("--validation", default="unknown")
    p.add_argument("--changed", default="unknown")
    p.add_argument("--note", default="")
    args = p.parse_args()

    payload = {
        "schema_version": "1.0.0",
        "routine_id": args.routine_id,
        "run_id": str(args.run_id),
        "period_key": args.period_key,
        "event": args.event,
        "status": args.status,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": args.source_commit,
        "guard_status": args.guard_status,
        "validation": args.validation,
        "changed": args.changed,
        "note": args.note[:240],
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
