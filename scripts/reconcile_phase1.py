#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "thu-tuc.json"
CITY = ROOT / "data" / "source-audit" / "city-updates-current.json"
BASELINE = ROOT / "data" / "source-audit" / "phase1-authoritative-baseline.json"
TABLE_LEVELS = ROOT / "data" / "source-audit" / "official-table-level-classification.json"
OUT_JSON = ROOT / "data" / "reconciliation" / "phase1-current.json"
OUT_MD = ROOT / "data" / "reconciliation" / "PHASE1_RECONCILIATION.md"


def _latest_level_hints(city: dict) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for decision in city.get("decisions") or []:
        date = str(decision.get("decisionDate") or decision.get("publishedDate") or "")
        for row in decision.get("rows") or []:
            code = str(row.get("code") or "").strip()
            hint = str(row.get("levelHint") or "").strip()
            if not code or not hint:
                continue
            item = {
                "hint": hint,
                "sectionStatus": row.get("sectionStatus"),
                "decisionNo": decision.get("decisionNo"),
                "date": date,
            }
            if code not in latest or date >= str(latest[code].get("date") or ""):
                latest[code] = item
    return latest


def reconcile(
    canonical: dict,
    city: dict,
    baseline: dict,
    table_levels: dict | None = None,
) -> dict:
    latest = _latest_level_hints(city)
    table_map = {
        str(item.get("ma") or "").strip(): str(item.get("classification") or "").strip()
        for item in (table_levels or {}).get("rows") or []
    }

    phase1_candidates: list[str] = []
    out_of_scope: list[str] = []
    ambiguous: list[str] = []
    provisional_commune: list[str] = []
    evidenced: list[dict] = []
    misclassified: list[dict] = []

    for row in canonical.get("thuTuc") or []:
        code = str(row.get("ma") or "").strip()
        cap = str(row.get("cap") or "").strip()
        cap_lower = cap.lower()
        hint = latest.get(code)
        table_level = table_map.get(code)
        is_province_cap = cap_lower.startswith("cấp tỉnh")

        resolved: str | None = None
        evidence: dict | None = None

        if hint:
            level = str(hint.get("hint") or "")
            if level == "commune":
                resolved = "COMMUNE"
            elif level == "shared_including_commune":
                resolved = "SHARED"
            elif level == "province":
                resolved = "PROVINCE"
            if resolved:
                evidence = {
                    "source": "city_update",
                    "decisionNo": hint.get("decisionNo"),
                    "date": hint.get("date"),
                }

        if resolved is None and table_level in {"COMMUNE", "SHARED", "PROVINCE"}:
            resolved = table_level
            evidence = {"source": "official_table_heading"}

        conflict = (
            (resolved == "COMMUNE" and is_province_cap)
            or (resolved == "SHARED" and "dùng chung" not in cap_lower)
            or (resolved == "PROVINCE" and not is_province_cap)
        )

        if conflict:
            misclassified.append({
                "ma": code,
                "ten": row.get("ten"),
                "currentCap": cap,
                "resolvedClassification": resolved,
                "latestEvidence": evidence,
            })

        is_province_resolved = resolved == "PROVINCE" or (
            resolved is None and is_province_cap
        )
        if is_province_resolved:
            out_of_scope.append(code)
        else:
            phase1_candidates.append(code)

        if cap == "Xã":
            provisional_commune.append(code)
        if "Xã / điểm tiếp nhận cấp xã" in cap and resolved is None:
            ambiguous.append(code)

        if resolved in {"COMMUNE", "SHARED"}:
            evidenced.append({
                "ma": code,
                "scope": resolved,
                **(evidence or {}),
            })

    target = int(baseline["aggregate"]["combined"]["total"])
    candidate_count = len(set(phase1_candidates))
    minimum_missing = max(0, target - candidate_count)

    return {
        "format": "phase1-reconciliation",
        "version": 2,
        "canonicalDatasetVersion": canonical.get("dataset_version"),
        "canonicalSourceCommit": canonical.get("source_commit"),
        "baselineAsOf": baseline.get("asOf"),
        "baselineTarget": target,
        "canonicalTotal": len(canonical.get("thuTuc") or []),
        "summary": {
            "phase1CandidateCodes": candidate_count,
            "outOfScopeProvinceReceptionOnly": len(set(out_of_scope)),
            "misclassifiedByOfficialEvidence": len(misclassified),
            "ambiguousCommuneOrShared": len(set(ambiguous)),
            "provisionalCommuneCapLabel": len(set(provisional_commune)),
            "directlyEvidencedPhase1": len(evidenced),
            "officialTableClassifiedCodes": len(table_map),
            "minimumMissingAgainstAggregateBaseline": minimum_missing,
            "exactMissingByCodeStatus": baseline["codeLevelList"]["status"],
        },
        "MATCHED": {
            "status": "partial_only",
            "items": evidenced,
            "note": "Đã dùng quyết định thành phố và heading phụ lục chính thức; final MATCHED vẫn cần authoritative 323-code baseline và onlineServiceLevel."
        },
        "MISSING": {
            "status": "not_finalizable_without_authoritative_code_list",
            "minimumCount": minimum_missing,
            "items": [],
        },
        "EXTRA": {
            "status": "phase1_out_of_scope",
            "count": len(set(out_of_scope)),
            "items": sorted(set(out_of_scope)),
            "note": "TTHC cấp tỉnh vẫn giữ trong canonical tổng thể nhưng không tính vào Phase 1."
        },
        "MISCLASSIFIED": {
            "count": len(misclassified),
            "items": misclassified,
        },
        "COUNT_DRIFT": {
            "baseline": target,
            "phase1CandidatesCurrent": candidate_count,
            "delta": candidate_count - target,
            "minimumMissing": minimum_missing,
            "canonicalTotalVsBaselineDelta": len(canonical.get("thuTuc") or []) - target,
        },
        "AMBIGUOUS": sorted(set(ambiguous)),
        "PROVISIONAL_COMMUNE": sorted(set(provisional_commune)),
    }


def render_md(result: dict) -> str:
    s = result["summary"]
    lines = [
        "# PHASE 1 — RECONCILIATION TTHC",
        "",
        f"- Canonical dataset: `{result.get('canonicalDatasetVersion')}`",
        f"- Baseline: {result.get('baselineAsOf')} — {result.get('baselineTarget')} TTHC (257 cấp xã + 66 dùng chung)",
        f"- Canonical hiện có: **{result.get('canonicalTotal')}** bản ghi",
        f"- Mã có khả năng thuộc Phase 1: **{s['phase1CandidateCodes']}**",
        f"- TTHC cấp tỉnh ngoài Phase 1: **{s['outOfScopeProvinceReceptionOnly']}**",
        f"- Mã được parser heading chính thức phân loại: **{s['officialTableClassifiedCodes']}**",
        f"- Xung đột phân loại với evidence chính thức: **{s['misclassifiedByOfficialEvidence']}**",
        f"- Nhãn còn mơ hồ xã/dùng chung: **{s['ambiguousCommuneOrShared']}**",
        f"- Số thiếu tối thiểu so với baseline aggregate: **{s['minimumMissingAgainstAggregateBaseline']}**",
        "",
        "## Kết luận",
        "",
        "Chưa được phép sinh danh sách MISSING theo mã chỉ từ phép trừ số lượng. "
        "Parser heading chỉ nhận phân loại có section heading chính thức rõ ràng; "
        "địa điểm tiếp nhận tại cấp xã không được dùng để suy ra thẩm quyền.",
        "",
        "## MISCLASSIFIED theo evidence hiện có",
        "",
        "| Mã | Nhãn hiện tại | Evidence | Phân loại đúng |",
        "|---|---|---|---|",
    ]
    for item in result["MISCLASSIFIED"]["items"]:
        ev = item.get("latestEvidence") or {}
        evidence_label = ev.get("decisionNo") or ev.get("source") or "official evidence"
        if ev.get("date"):
            evidence_label += f" ({ev.get('date')})"
        lines.append(
            f"| {item['ma']} | {item['currentCap']} | {evidence_label} | {item.get('resolvedClassification')} |"
        )
    lines += [
        "",
        "## Gate tiếp theo",
        "",
        "1. Mở rộng parser trên toàn bộ phụ lục chính thức để tăng coverage.",
        "2. Materialize authoritative 323-code baseline.",
        "3. Chốt MATCHED/MISSING/EXTRA/MISCLASSIFIED theo Mã TTHC.",
        "4. Gán authorityLevel/serviceScope/onlineServiceLevel + provenance.",
        "5. Chỉ migrate canonical v5 sau khi validator PASS.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8-sig"))
    city = json.loads(CITY.read_text(encoding="utf-8-sig"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
    table_levels = (
        json.loads(TABLE_LEVELS.read_text(encoding="utf-8-sig"))
        if TABLE_LEVELS.exists()
        else {}
    )
    result = reconcile(canonical, city, baseline, table_levels)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OUT_MD.write_text(render_md(result), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
