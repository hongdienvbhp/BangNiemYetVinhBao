#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data" / "thu-tuc.json"
CITY = ROOT / "data" / "source-audit" / "city-updates-current.json"
BASELINE = ROOT / "data" / "source-audit" / "phase1-authoritative-baseline.json"
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


def reconcile(canonical: dict, city: dict, baseline: dict) -> dict:
    latest = _latest_level_hints(city)
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
        is_province_cap = cap_lower.startswith("cấp tỉnh")
        newer_phase1 = bool(hint and hint.get("hint") in {"commune", "shared_including_commune"})

        conflict = False
        if hint:
            level = hint.get("hint")
            if level == "commune" and is_province_cap:
                conflict = True
            elif level == "shared_including_commune" and "dùng chung" not in cap_lower:
                conflict = True
            elif level == "province" and not is_province_cap:
                conflict = True

        if conflict:
            misclassified.append({
                "ma": code,
                "ten": row.get("ten"),
                "currentCap": cap,
                "latestEvidence": hint,
            })

        if not is_province_cap or newer_phase1:
            phase1_candidates.append(code)
        else:
            out_of_scope.append(code)

        if cap == "Xã":
            provisional_commune.append(code)
        if "Xã / điểm tiếp nhận cấp xã" in cap:
            ambiguous.append(code)
        if newer_phase1:
            evidenced.append({
                "ma": code,
                "scope": hint.get("hint"),
                "decisionNo": hint.get("decisionNo"),
                "date": hint.get("date"),
            })

    target = int(baseline["aggregate"]["combined"]["total"])
    candidate_count = len(set(phase1_candidates))
    minimum_missing = max(0, target - candidate_count)

    return {
        "format": "phase1-reconciliation",
        "version": 1,
        "canonicalDatasetVersion": canonical.get("dataset_version"),
        "canonicalSourceCommit": canonical.get("source_commit"),
        "baselineAsOf": baseline.get("asOf"),
        "baselineTarget": target,
        "canonicalTotal": len(canonical.get("thuTuc") or []),
        "summary": {
            "phase1CandidateCodes": candidate_count,
            "outOfScopeProvinceReceptionOnly": len(set(out_of_scope)),
            "misclassifiedByNewerOfficialEvidence": len(misclassified),
            "ambiguousCommuneOrShared": len(set(ambiguous)),
            "provisionalCommuneCapLabel": len(set(provisional_commune)),
            "directlyEvidencedPhase1FromCurrentCityUpdates": len(evidenced),
            "minimumMissingAgainstAggregateBaseline": minimum_missing,
            "exactMissingByCodeStatus": baseline["codeLevelList"]["status"],
        },
        "MATCHED": {
            "status": "partial_only",
            "items": evidenced,
            "note": "Direct newer city evidence exists, but final MATCHED also requires the authoritative 323-code baseline and v5 serviceScope/onlineServiceLevel."
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
            "note": "These records are retained in canonical because they are province-authority procedures receivable at commune; they are outside Phase 1, not deleted."
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
    drift = result["COUNT_DRIFT"]
    lines = [
        "# PHASE 1 — RECONCILIATION TTHC",
        "",
        f"- Canonical dataset: `{result.get('canonicalDatasetVersion')}`",
        f"- Baseline: {result.get('baselineAsOf')} — {result.get('baselineTarget')} TTHC (257 cấp xã + 66 dùng chung)",
        f"- Canonical hiện có: **{result.get('canonicalTotal')}** bản ghi",
        f"- Mã có khả năng thuộc Phase 1 theo dữ liệu hiện có: **{s['phase1CandidateCodes']}**",
        f"- TTHC cấp tỉnh chỉ tiếp nhận tại xã, ngoài Phase 1: **{s['outOfScopeProvinceReceptionOnly']}**",
        f"- Xung đột phân loại với quyết định Hải Phòng mới hơn: **{s['misclassifiedByNewerOfficialEvidence']}**",
        f"- Nhãn còn mơ hồ xã/dùng chung: **{s['ambiguousCommuneOrShared']}**",
        f"- Số thiếu tối thiểu so với baseline aggregate: **{s['minimumMissingAgainstAggregateBaseline']}**",
        "",
        "## Kết luận",
        "",
        "Chưa được phép sinh danh sách MISSING theo mã chỉ từ phép trừ số lượng. Cần materialize danh sách 323 mã từ nguồn chính thức. "
        "Các mã cấp tỉnh chỉ tiếp nhận tại xã vẫn thuộc canonical tổng thể nhưng không được tính vào 257+66 của Phase 1.",
        "",
        "## MISCLASSIFIED theo evidence mới hơn",
        "",
        "| Mã | Nhãn hiện tại | Evidence mới | Phân loại mới |",
        "|---|---|---|---|",
    ]
    for item in result["MISCLASSIFIED"]["items"]:
        ev = item["latestEvidence"]
        lines.append(
            f"| {item['ma']} | {item['currentCap']} | {ev.get('decisionNo')} ({ev.get('date')}) | {ev.get('hint')} |"
        )
    lines += [
        "",
        "## Gate tiếp theo",
        "",
        "1. Materialize authoritative code-level baseline 323 mã.",
        "2. Đối chiếu theo Mã TTHC để chốt MATCHED/MISSING/EXTRA/MISCLASSIFIED.",
        "3. Gán authorityLevel/serviceScope/onlineServiceLevel và provenance.",
        "4. Chỉ migrate canonical v5 sau khi validator PASS.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8-sig"))
    city = json.loads(CITY.read_text(encoding="utf-8-sig"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
    result = reconcile(canonical, city, baseline)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(result), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
