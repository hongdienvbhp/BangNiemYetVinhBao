#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

try:
    from scripts.validate_tthc_guidance import validate, validate_vinhbao_submission_url
except ModuleNotFoundError:
    from validate_tthc_guidance import validate, validate_vinhbao_submission_url

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
GUIDANCE = ROOT / "data/tthc-guidance-enrichment.json"
CANDIDATE_DIR = ROOT / "data/source-audit/central-guidance-candidates"
COVERAGE = ROOT / "data/source-audit/priority50-guidance-coverage.json"

PUBLISH_FIELDS = (
    "quyTrinh",
    "thanhPhanHoSo",
    "bieuMau",
    "lePhi",
    "thoiHan",
    "coQuanThucHien",
    "ketQua",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def official_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "dichvucong.gov.vn"
        or host.endswith(".dichvucong.gov.vn")
        or host.endswith(".gov.vn")
    )


def load_candidates() -> dict[str, list[dict]]:
    by_code: dict[str, list[dict]] = {}
    if not CANDIDATE_DIR.exists():
        return by_code
    for path in sorted(CANDIDATE_DIR.glob("*.json")):
        payload = load(path)
        if payload.get("format") != "central-guidance-candidates":
            continue
        for item in payload.get("procedures") or []:
            if not isinstance(item, dict):
                continue
            by_code.setdefault(str(item.get("ma") or "").strip(), []).append(item)
    return by_code


def candidate_is_publishable(item: dict, code: str) -> bool:
    evidence = item.get("httpEvidence") or {}
    return (
        item.get("candidateStatus") == "candidate"
        and not (item.get("issues") or [])
        and str(evidence.get("detectedCode") or "").strip() == code
        and len(str(evidence.get("sha256") or "")) == 64
        and official_url(str(item.get("sourceUrl") or ""))
        and item.get("sourceRole") in {"central_content_reference", "local_legal_effect", "local_execution"}
    )


def build_row(master_row: dict, candidates: list[dict]) -> tuple[dict | None, dict]:
    code = str(master_row.get("ma") or "").strip()
    row: dict = {
        "ma": code,
        "verificationStatus": "verified_official",
        "verifiedAt": "2026-09-21",
        "sources": [],
        "fieldProvenance": {},
    }
    source_ids: set[str] = set()
    published: list[str] = []
    rejected = 0

    role_rank = {"local_legal_effect": 0, "central_content_reference": 1, "local_execution": 2}
    candidates = sorted(
        candidates,
        key=lambda item: role_rank.get(str(item.get("sourceRole") or ""), 99),
    )
    for candidate in candidates:
        if not candidate_is_publishable(candidate, code):
            rejected += 1
            continue
        source_id = str(candidate.get("sourceId") or "").strip()
        if not source_id:
            rejected += 1
            continue
        if source_id not in source_ids:
            row["sources"].append({
                "id": source_id,
                "url": candidate["sourceUrl"],
                "sourceRole": candidate.get("sourceRole") or "central_content_reference",
                "authority": candidate.get("authority") or "",
                "classification": (
                    "official_local_tthc_detail"
                    if candidate.get("sourceRole") == "local_legal_effect"
                    else "dvcqg_tthc_detail"
                    if candidate.get("sourceRole") == "local_execution"
                    else "official_ministry_tthc_detail"
                ),
                "sha256": (candidate.get("httpEvidence") or {}).get("sha256"),
            })
            source_ids.add(source_id)
        extracted = candidate.get("extracted") or {}
        for field in PUBLISH_FIELDS:
            if row.get(field) not in (None, "", [], {}):
                continue
            value = extracted.get(field)
            if value in (None, "", [], {}):
                continue
            row[field] = deepcopy(value)
            row["fieldProvenance"][field] = [source_id]
            published.append(field)

    formality_id = str(master_row.get("formalityId") or "").strip()
    submission_url = str(master_row.get("nopHoSoUrl") or "").strip()
    dvc_published = False
    if formality_id and submission_url and not validate_vinhbao_submission_url(submission_url, formality_id):
        execution_id = "dvcqg-vinhbao"
        row["sources"].append({
            "id": execution_id,
            "url": submission_url,
            "sourceRole": "local_execution",
            "classification": "dvcqg_submission_link",
            "verifiedAt": master_row.get("submissionLinkCheckedAt") or "",
        })
        row["formalityId"] = formality_id
        row["submissionUrl"] = submission_url
        row["fieldProvenance"]["submissionUrl"] = [execution_id]
        dvc_published = True

    has_guidance = any(row.get(field) not in (None, "", [], {}) for field in PUBLISH_FIELDS)
    if not has_guidance:
        return None, {
            "ma": code,
            "reviewed": True,
            "publishedFields": [],
            "centralCandidateCount": len(candidates),
            "rejectedCandidates": rejected,
            "dvcExact": dvc_published,
            "status": "unresolved_no_verified_central_content",
        }

    return row, {
        "ma": code,
        "reviewed": True,
        "publishedFields": sorted(set(published)),
        "centralCandidateCount": len(candidates),
        "rejectedCandidates": rejected,
        "dvcExact": dvc_published,
        "status": "verified_guidance",
    }


def main() -> int:
    master = load(MASTER)
    current = load(GUIDANCE)
    candidates = load_candidates()
    priority = [row for row in master.get("thuTuc") or [] if row.get("priority51")]

    rows = []
    coverage = []
    for master_row in sorted(priority, key=lambda item: item.get("priority51Ordinal") or 999):
        code = str(master_row.get("ma") or "").strip()
        row, status = build_row(master_row, candidates.get(code, []))
        status["priority51Ordinal"] = master_row.get("priority51Ordinal")
        status["linhVuc"] = master_row.get("linhVuc") or ""
        if row is not None:
            rows.append(row)
        coverage.append(status)

    result = deepcopy(current)
    result["rows"] = rows
    errors = validate(result)
    if errors:
        raise SystemExit("\n".join(errors))
    GUIDANCE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    all_fields = list(PUBLISH_FIELDS)
    field_counts = {
        field: sum(field in item["publishedFields"] for item in coverage)
        for field in all_fields
    }
    report = {
        "format": "priority50-guidance-coverage",
        "version": 1,
        "canonicalDatasetVersion": master.get("dataset_version"),
        "canonicalSourceCommit": master.get("source_commit"),
        "reviewed": len(coverage),
        "verifiedGuidanceRows": len(rows),
        "unresolvedRows": sum(item["status"] != "verified_guidance" for item in coverage),
        "dvcExactRows": sum(bool(item["dvcExact"]) for item in coverage),
        "fieldCoverage": field_counts,
        "rows": coverage,
    }
    COVERAGE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "reviewed": report["reviewed"],
        "verifiedGuidanceRows": report["verifiedGuidanceRows"],
        "unresolvedRows": report["unresolvedRows"],
        "dvcExactRows": report["dvcExactRows"],
        "fieldCoverage": report["fieldCoverage"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
