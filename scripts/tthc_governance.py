#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Governance/audit layer for the canonical TTHC dataset.

Reqwise-inspired principles:
- one canonical source, many generated views;
- deterministic validators before AI review;
- patch/change-set instead of whole-dataset regeneration;
- machine-verifiable evidence and drift detection;
- single-writer / many-readers agent contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data/thu-tuc.json"
POLICY = ROOT / "config/tthc-policy-registry.json"
REPORT_DIR = ROOT / "data/governance"
REVIEW_QUEUE = REPORT_DIR / "review-queue.json"
TELEMETRY = REPORT_DIR / "telemetry.jsonl"
AUDIT_REPORT = REPORT_DIR / "latest-audit.json"
DIAGRAM = ROOT / "docs/TTHC_CANONICAL_PIPELINE.mmd"


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    procedure: str | None = None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def dataset_version(payload: dict[str, Any]) -> str:
    return f"{payload.get('version', 'unknown')}@{payload.get('sourceSnapshotDate', 'unknown')}"


def fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def audit(payload: dict[str, Any], policy: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    procedures = payload.get("thuTuc")
    if not isinstance(procedures, list):
        return [Finding("error", "CANONICAL_SHAPE", "thuTuc must be an array")]

    required = policy["rules"]["requiredCanonicalFields"]["fields"]
    seen: set[str] = set()

    for item in procedures:
        code = str(item.get("ma", "")).strip()
        if not code:
            findings.append(Finding("error", "MISSING_CODE", "Procedure code is empty"))
            continue
        if code in seen:
            findings.append(Finding("error", "DUPLICATE_CODE", f"Duplicate procedure code {code}", code))
        seen.add(code)

        for field in required:
            value = item.get(field)
            if value in (None, "", []):
                findings.append(Finding("error", "MISSING_FIELD", f"{field} is required", code))

        evidence = item.get("sourceEvidence", [])
        if isinstance(evidence, list):
            for idx, ev in enumerate(evidence):
                if not isinstance(ev, dict):
                    findings.append(Finding("error", "BAD_EVIDENCE", f"sourceEvidence[{idx}] must be object", code))
                    continue
                for field in policy["rules"]["provenance"]["minimumEvidenceFields"]:
                    if not ev.get(field):
                        findings.append(
                            Finding("error", "MISSING_PROVENANCE", f"sourceEvidence[{idx}].{field} is required", code)
                        )
        else:
            findings.append(Finding("error", "BAD_EVIDENCE", "sourceEvidence must be an array", code))

        # Deterministic cross-field consistency.
        cap = str(item.get("cap", "")).lower()
        if item.get("tiepNhanCapXa") is True and "xã" not in cap and "xa" not in cap:
            findings.append(
                Finding("warning", "AUTHORITY_RECEPTION_MISMATCH", "tiepNhanCapXa=true but cap does not mention commune reception", code)
            )

        if item.get("dvctt") and item.get("submissionUrl"):
            url = str(item.get("submissionUrl", ""))
            if not url.startswith("https://"):
                findings.append(Finding("error", "BAD_SUBMISSION_URL", "submissionUrl must use https", code))

    if payload.get("format") != "bangniemyet-vinhbao-master-data":
        findings.append(Finding("error", "FORMAT", "Unexpected canonical format"))
    if not payload.get("sourceSnapshotDate"):
        findings.append(Finding("error", "MISSING_SNAPSHOT", "sourceSnapshotDate is required"))

    return findings


def build_review_queue(findings: list[Finding]) -> dict[str, Any]:
    items = [
        {
            "id": f"{f.code}:{f.procedure or 'dataset'}",
            "status": "NEW",
            "severity": f.severity,
            "procedure": f.procedure,
            "reason": f.message,
        }
        for f in findings
        if f.severity in {"error", "warning"}
    ]
    return {"version": 1, "generatedAt": now_iso(), "items": items}


def extract_codes_from_fallback(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8-sig")
    return set(re.findall(r'["\']ma["\']\s*:\s*["\']([^"\']+)["\']', text))


def drift(payload: dict[str, Any]) -> dict[str, Any]:
    canonical_codes = {str(x.get("ma", "")).strip() for x in payload.get("thuTuc", []) if x.get("ma")}
    fallback_codes = extract_codes_from_fallback(ROOT / "js/master-data-fallback.js")
    missing = sorted(canonical_codes - fallback_codes)
    extra = sorted(fallback_codes - canonical_codes)
    return {
        "canonicalCount": len(canonical_codes),
        "fallbackCount": len(fallback_codes),
        "missingInFallback": missing,
        "extraInFallback": extra,
        "drift": len(missing) + len(extra),
    }


def changeset(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    def index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(x.get("ma", "")): x for x in payload.get("thuTuc", []) if x.get("ma")}

    a, b = index(old), index(new)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    modified = []
    for code in sorted(set(a) & set(b)):
        if fingerprint(a[code]) != fingerprint(b[code]):
            modified.append(code)
    return {
        "id": "CHANGESET-" + datetime.now().strftime("%Y%m%d-%H%M%S"),
        "generatedAt": now_iso(),
        "added": added,
        "removed": removed,
        "modified": modified,
    }


def diagram_text() -> str:
    return """flowchart TD
    A[Official Sources] --> B[Source Adapters]
    B --> C[Parser / Normalizer]
    C --> D[Diff Engine]
    D --> E[Deterministic Validators]
    E -->|PASS| F[Canonical TTHC]
    E -->|Exception| G[AI Exception Review]
    G --> H[Human QC]
    H --> F
    F --> I[Website View]
    F --> J[Dashboard View]
    F --> K[Monitor]
    F --> L[Agent Guidance]
    F --> M[Reports]
    N[Policy Registry] --> E
    O[Single Writer] --> F
    P[Many Readers] --> I
    P --> J
    P --> K
    P --> L
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_outputs(payload: dict[str, Any], findings: list[Finding]) -> dict[str, Any]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = {
        "datasetVersion": dataset_version(payload),
        "sourceCommit": git_head(),
        "datasetFingerprint": fingerprint(payload),
    }
    d = drift(payload)
    report = {
        "generatedAt": now_iso(),
        "metadata": metadata,
        "summary": {
            "procedures": len(payload.get("thuTuc", [])),
            "errors": sum(f.severity == "error" for f in findings),
            "warnings": sum(f.severity == "warning" for f in findings),
            "drift": d["drift"],
        },
        "drift": d,
        "findings": [asdict(x) for x in findings],
    }
    AUDIT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REVIEW_QUEUE.write_text(json.dumps(build_review_queue(findings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DIAGRAM.write_text(diagram_text(), encoding="utf-8")
    with TELEMETRY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "runId": datetime.now().strftime("%Y%m%d%H%M%S"),
            "timestamp": now_iso(),
            "recordsProcessed": len(payload.get("thuTuc", [])),
            "success": report["summary"]["errors"] == 0,
            "errors": report["summary"]["errors"],
            "warnings": report["summary"]["warnings"],
            "drift": report["summary"]["drift"],
            **metadata,
        }, ensure_ascii=False) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--changeset-from", type=Path)
    parser.add_argument("--write", action="store_true", help="write audit/review/telemetry/diagram outputs")
    args = parser.parse_args()

    payload = load_json(CANONICAL)
    policy = load_json(POLICY)
    findings = audit(payload, policy)

    if args.changeset_from:
        old = load_json(args.changeset_from)
        print(json.dumps(changeset(old, payload), ensure_ascii=False, indent=2))

    report = None
    if args.write or args.all:
        report = write_outputs(payload, findings)
    else:
        d = drift(payload)
        report = {
            "datasetVersion": dataset_version(payload),
            "sourceCommit": git_head(),
            "errors": sum(f.severity == "error" for f in findings),
            "warnings": sum(f.severity == "warning" for f in findings),
            "drift": d["drift"],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Errors fail CI. Drift is also a gate because generated consumers must match canonical.
    errors = sum(f.severity == "error" for f in findings)
    d = drift(payload)
    return 1 if errors or d["drift"] else 0


if __name__ == "__main__":
    sys.exit(main())
