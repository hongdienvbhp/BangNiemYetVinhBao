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

def classify_terminal_status(
    *,
    history_outcome: str,
    guard_run: str,
    guard_status: str,
    job_status: str,
    existing_pr: str,
    validation_outcome: str,
    changed: str,
    candidate_matches_open_pr: str,
) -> tuple[str, str]:
    """Classify the real terminal outcome without treating an open PR as success by itself."""
    if history_outcome != "success":
        return "FAILED", "workflow history could not be read"
    if guard_run != "true":
        status = guard_status if guard_status in ALLOWED else "FAILED"
        return status, "guard did not authorize execution"
    if job_status != "success":
        return "FAILED", "one or more execution steps failed"
    if validation_outcome not in {"success", "skipped"}:
        return "PARTIAL", "candidate validation needs review"
    if existing_pr == "true":
        if changed == "true" and candidate_matches_open_pr != "true":
            return "PARTIAL", "new candidate differs from open automated PR; preserved for review"
        if changed == "true":
            return "OK", "source scan and validation passed; current candidate matches open PR"
        return "OK", "source scan and validation passed; no new source changes; open PR preserved"
    return "OK", "completed"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--routine-id", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--period-key", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--status", choices=sorted(ALLOWED))
    p.add_argument("--source-commit", required=True)
    p.add_argument("--guard-status", required=True)
    p.add_argument("--validation", default="unknown")
    p.add_argument("--changed", default="unknown")
    p.add_argument("--note")
    p.add_argument("--history-outcome", default="success")
    p.add_argument("--guard-run", default="true")
    p.add_argument("--job-status", default="success")
    p.add_argument("--existing-pr", default="false")
    p.add_argument("--candidate-matches-open-pr", default="unknown")
    args = p.parse_args()

    if args.status:
        status = args.status
        note = args.note or ""
    else:
        status, note = classify_terminal_status(
            history_outcome=args.history_outcome,
            guard_run=args.guard_run,
            guard_status=args.guard_status,
            job_status=args.job_status,
            existing_pr=args.existing_pr,
            validation_outcome=args.validation,
            changed=args.changed,
            candidate_matches_open_pr=args.candidate_matches_open_pr,
        )
        if args.note is not None:
            note = args.note

    payload = {
        "schema_version": "1.0.0",
        "routine_id": args.routine_id,
        "run_id": str(args.run_id),
        "period_key": args.period_key,
        "event": args.event,
        "status": status,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": args.source_commit,
        "guard_status": args.guard_status,
        "validation": args.validation,
        "changed": args.changed,
        "note": note[:240],
    }
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
