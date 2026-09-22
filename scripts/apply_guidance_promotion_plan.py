#!/usr/bin/env python3
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from scripts.canonical_v4 import normalize_evidence
    from scripts.apply_guidance_enrichment import write_fallback
except ModuleNotFoundError:
    from canonical_v4 import normalize_evidence
    from apply_guidance_enrichment import write_fallback

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "thu-tuc.json"
PLAN = ROOT / "data" / "source-audit" / "official-guidance-promotion-plan.json"
RESULT = ROOT / "data" / "source-audit" / "official-guidance-promotion-result.json"

ALLOWED_FIELDS = {
    "onlineServiceLevel",
    "thoiHan",
    "phiLePhi",
    "canCuPhapLy",
    "coQuanThucHien",
}


def _missing(value: Any) -> bool:
    return value in (None, "", [], {})


def _canonical_value(field: str, value: Any) -> Any:
    if field != "phiLePhi":
        return deepcopy(value)
    if value == "NOT_PUBLISHED":
        return {"status": "not_published", "items": []}
    if value == "EXEMPT":
        return {
            "status": "verified",
            "items": [{"type": "exempt", "value": "Miễn phí/lệ phí"}],
        }
    if isinstance(value, dict):
        return deepcopy(value)
    if isinstance(value, list):
        return {"status": "verified", "items": deepcopy(value)}
    return {"status": "verified", "items": [{"mucThu": value}]}


def _promotion_evidence(item: dict) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for source in item.get("provenance") or []:
        article_urls = [
            str(url).strip()
            for url in source.get("articleUrls") or []
            if str(url).strip()
        ]
        evidence = {
            "sourceRole": "local_legal_effect",
            "articleUrl": article_urls[0] if article_urls else None,
            "attachmentUrl": source.get("attachmentUrl"),
            "decisionNumbers": source.get("decisionNumbers") or [],
            "classification": "official_guidance_field_promotion",
            "repealContext": False,
        }
        if not evidence["articleUrl"] and not evidence["attachmentUrl"]:
            continue
        normalized = normalize_evidence(evidence, "local_legal_effect")
        ev_id = normalized["evidenceId"]
        if ev_id not in seen:
            out.append(normalized)
            seen.add(ev_id)
    return out


def apply_plan(master: dict, plan: dict) -> tuple[dict, dict]:
    result = deepcopy(master)
    rows = result.get("thuTuc") or []
    by_code = {
        str(row.get("ma") or "").strip(): row
        for row in rows
        if isinstance(row, dict) and str(row.get("ma") or "").strip()
    }
    summary = {
        "planProcedures": len(plan.get("procedures") or []),
        "canonicalProcedures": len(rows),
        "promotedFields": 0,
        "alreadySameFields": 0,
        "conflicts": 0,
        "skippedNotCanonical": 0,
        "skippedInactive": 0,
        "skippedInvalid": 0,
        "byField": {field: 0 for field in sorted(ALLOWED_FIELDS)},
    }
    conflicts: list[dict] = []
    promoted: list[dict] = []

    for procedure in plan.get("procedures") or []:
        code = str(procedure.get("ma") or "").strip()
        row = by_code.get(code)
        if not row:
            summary["skippedNotCanonical"] += 1
            continue
        lifecycle = row.get("lifecycle") if isinstance(row.get("lifecycle"), dict) else {}
        if lifecycle.get("status") != "active":
            summary["skippedInactive"] += 1
            continue

        for promotion in procedure.get("promotions") or []:
            field = str(promotion.get("field") or "").strip()
            target = str(promotion.get("targetPath") or "").strip()
            if (
                promotion.get("status") != "ready_for_schema_gate"
                or field not in ALLOWED_FIELDS
                or target != field
            ):
                summary["skippedInvalid"] += 1
                continue

            proposed = _canonical_value(field, promotion.get("value"))
            existing = row.get(target)
            evidence = _promotion_evidence(promotion)
            if not evidence:
                summary["skippedInvalid"] += 1
                continue

            if not _missing(existing) and existing != proposed:
                summary["conflicts"] += 1
                conflicts.append({
                    "ma": code,
                    "field": field,
                    "existing": existing,
                    "proposed": proposed,
                    "action": "kept_existing",
                })
                continue

            existing_evidence = {
                str(item.get("evidenceId") or ""): item
                for item in row.get("sourceEvidence") or []
                if isinstance(item, dict) and str(item.get("evidenceId") or "")
            }
            ids: list[str] = []
            for item in evidence:
                ev_id = item["evidenceId"]
                existing_evidence.setdefault(ev_id, item)
                ids.append(ev_id)
            row["sourceEvidence"] = list(existing_evidence.values())

            field_sources = row.setdefault("fieldSources", {})
            refs = list(field_sources.get(target) or [])
            for ev_id in ids:
                if ev_id not in refs:
                    refs.append(ev_id)
            field_sources[target] = refs

            if _missing(existing):
                row[target] = proposed
                summary["promotedFields"] += 1
                summary["byField"][field] += 1
                promoted.append({"ma": code, "field": field, "value": proposed})
            else:
                summary["alreadySameFields"] += 1

    result["thuTuc"] = rows
    audit = {
        "format": "official-guidance-promotion-result",
        "version": 1,
        "policy": (
            "Chỉ promote field verified có provenance vào TTHC active đang có trong canonical. "
            "Không ghi đè giá trị canonical khác; conflict được giữ để rà soát."
        ),
        "summary": summary,
        "promoted": promoted,
        "conflicts": conflicts,
    }
    return result, audit


def main() -> int:
    master = json.loads(MASTER.read_text(encoding="utf-8-sig"))
    plan = json.loads(PLAN.read_text(encoding="utf-8-sig"))
    promoted, audit = apply_plan(master, plan)
    MASTER.write_text(
        json.dumps(promoted, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    RESULT.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_fallback(promoted)
    print(json.dumps(audit["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
