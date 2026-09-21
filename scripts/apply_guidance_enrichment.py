#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

try:
    from scripts.canonical_v4 import upgrade_record_to_v4
    from scripts.validate_tthc_guidance import validate, validate_vinhbao_submission_url
except ModuleNotFoundError:
    from canonical_v4 import upgrade_record_to_v4
    from validate_tthc_guidance import validate, validate_vinhbao_submission_url

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
PRIORITY51 = ROOT / "data/priority-51-crosswalk.json"
GUIDANCE = ROOT / "data/tthc-guidance-enrichment.json"
FALLBACK = ROOT / "js/master-data-fallback.js"

GUIDANCE_FIELDS = (
    "quyTrinh",
    "thanhPhanHoSo",
    "bieuMau",
    "lePhi",
    "thoiHan",
    "coQuanThucHien",
    "ketQua",
    "dvctt",
    "submissionUrl",
)


def _as_date(value: object) -> str:
    raw = str(value or "").strip()
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    return match.group(1) if match else ""


def _advance_dataset_version(result: dict, priority: dict, guidance: dict) -> None:
    dates = [
        str(result.get("dataset_version") or "").replace(".", "-"),
        str(result.get("sourceSnapshotDate") or ""),
    ]
    dates.extend(_as_date(item.get("liveVerifiedAt")) for item in priority.get("items") or [])
    dates.extend(_as_date(item.get("verifiedAt")) for item in guidance.get("rows") or [])
    valid = [value for value in dates if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or "")]
    if not valid:
        return
    latest = max(valid)
    result["dataset_version"] = latest.replace("-", ".")
    result["updatedAt"] = latest


def apply_enrichment(master: dict, priority: dict, guidance: dict) -> dict:
    errors = validate(guidance)
    if errors:
        raise ValueError("\n".join(errors))

    result = deepcopy(master)
    rows = result.get("thuTuc") or []
    by_code = {
        str(row.get("ma") or "").strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("ma") or "").strip()
    }

    priority_links = 0
    for item in priority.get("items") or []:
        code = str(item.get("code") or "").strip()
        row = by_code.get(code)
        if not row:
            continue
        url = str(item.get("dvcUrl") or "").strip()
        formality_id = str(item.get("formalityId") or row.get("formalityId") or "").strip()
        if not url or validate_vinhbao_submission_url(url, formality_id):
            continue
        row["nopHoSoUrl"] = url
        row["nopHoSoScope"] = {
            "provinceCode": "31",
            "provinceName": "Hải Phòng",
            "wardCode": "11824",
            "wardName": "Vĩnh Bảo",
            "commune": "WARD",
        }
        row["submissionLinkStatus"] = "vinhbao_scope_parameters_verified"
        row["submissionLinkSource"] = "priority-51-crosswalk"
        if item.get("liveVerifiedAt"):
            row["submissionLinkCheckedAt"] = item["liveVerifiedAt"]
        priority_links += 1

    guidance_count = 0
    for item in guidance.get("rows") or []:
        code = str(item.get("ma") or "").strip()
        row = by_code.get(code)
        if not row:
            continue
        guide = {
            field: deepcopy(item[field])
            for field in GUIDANCE_FIELDS
            if item.get(field) not in (None, "", [], {})
        }
        guide["verificationStatus"] = item["verificationStatus"]
        guide["verifiedAt"] = item.get("verifiedAt") or ""
        guide["sources"] = deepcopy(item.get("sources") or [])
        guide["fieldProvenance"] = deepcopy(item.get("fieldProvenance") or {})
        row["huongDan"] = guide
        if guide.get("submissionUrl"):
            guide_url = str(guide["submissionUrl"]).strip()
            root_formality_id = str(row.get("formalityId") or "").strip()
            # A legacy keyword guidance URL must never replace a newer exact-formality
            # canonical URL. Only promote guidance when it validates against the
            # current canonical formality identity (or no formalityId exists).
            if not validate_vinhbao_submission_url(guide_url, root_formality_id):
                row["nopHoSoUrl"] = guide_url
                row["submissionLinkStatus"] = "verified_official_guidance"
                row["submissionLinkSource"] = "tthc-guidance-enrichment"
                if guide.get("verifiedAt"):
                    row["submissionLinkCheckedAt"] = guide["verifiedAt"]
        guidance_count += 1

    as_of = str(result.get("sourceSnapshotDate") or result.get("updatedAt") or "")
    result["thuTuc"] = [
        upgrade_record_to_v4(row, as_of)
        for row in rows
        if isinstance(row, dict)
    ]

    summary = result.setdefault("summary", {})
    summary["priority51VinhBaoSubmissionLinks"] = priority_links
    summary["officialGuidanceEnriched"] = guidance_count
    _advance_dataset_version(result, priority, guidance)
    return result


def write_fallback(master: dict) -> None:
    payload = json.dumps(master, ensure_ascii=False, separators=(",", ":"))
    FALLBACK.write_text(
        "/* Generated by scripts/build_master_data.py + apply_guidance_enrichment.py. Do not edit manually. */\n"
        f"window.TTHC_MASTER_DATA={payload};\n"
        "window.TTHC_DATA={...(window.TTHC_DATA||{}),"
        "updatedAt:window.TTHC_MASTER_DATA.updatedAt,"
        "source:window.TTHC_MASTER_DATA.source,"
        "sourceSnapshotDate:window.TTHC_MASTER_DATA.sourceSnapshotDate,"
        "thuTuc:window.TTHC_MASTER_DATA.thuTuc};\n",
        encoding="utf-8",
    )


def main() -> int:
    master = json.loads(MASTER.read_text(encoding="utf-8"))
    priority = json.loads(PRIORITY51.read_text(encoding="utf-8"))
    guidance = json.loads(GUIDANCE.read_text(encoding="utf-8"))
    enriched = apply_enrichment(master, priority, guidance)
    MASTER.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_fallback(enriched)
    print(json.dumps({
        "procedures": len(enriched.get("thuTuc") or []),
        "priority51VinhBaoSubmissionLinks": enriched.get("summary", {}).get("priority51VinhBaoSubmissionLinks", 0),
        "officialGuidanceEnriched": enriched.get("summary", {}).get("officialGuidanceEnriched", 0),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
