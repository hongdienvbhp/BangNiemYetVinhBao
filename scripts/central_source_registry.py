#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/source-audit/central-source-registry.json"
MASTER = ROOT / "data/thu-tuc.json"
PLAN = ROOT / "data/source-audit/central-guidance-plan.json"

ALLOWED_STATUS = {"ready", "ready_search", "discovery_only"}
ALLOWED_ADAPTERS = {
    "direct_code_detail",
    "search_listing_by_code",
    "search_listing_by_code_or_name",
    "official_decision_catalog",
    "official_portal_discovery",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_registry(payload: dict) -> list[str]:
    errors: list[str] = []
    if payload.get("format") != "central-tthc-source-registry":
        errors.append("registry format invalid")
    if payload.get("version") != 1:
        errors.append("registry version must be 1")
    if payload.get("sourceRole") != "central_content_reference":
        errors.append("registry sourceRole must be central_content_reference")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        return errors + ["registry sources must be a non-empty list"]

    seen: set[str] = set()
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            errors.append(f"sources[{index}] must be an object")
            continue
        source_id = str(source.get("id") or "").strip()
        if not source_id:
            errors.append(f"sources[{index}] missing id")
        elif source_id in seen:
            errors.append(f"duplicate source id: {source_id}")
        seen.add(source_id)
        status = str(source.get("status") or "")
        if status not in ALLOWED_STATUS:
            errors.append(f"{source_id or index}: invalid status {status}")
        adapter = str(source.get("adapter") or "")
        if adapter not in ALLOWED_ADAPTERS:
            errors.append(f"{source_id or index}: invalid adapter {adapter}")
        fields = source.get("fields")
        if not isinstance(fields, list) or not fields:
            errors.append(f"{source_id or index}: fields must be non-empty")
        domains = source.get("domains")
        if not isinstance(domains, list) or not domains:
            errors.append(f"{source_id or index}: domains must be non-empty")
        else:
            for domain in domains:
                if not isinstance(domain, str) or "." not in domain or "://" in domain:
                    errors.append(f"{source_id or index}: invalid domain {domain!r}")
        if adapter == "direct_code_detail":
            template = str(source.get("detailUrlTemplate") or "")
            if "{code}" not in template:
                errors.append(f"{source_id or index}: direct adapter requires {{code}} template")
            elif not _url_matches_domains(template.replace("{code}", "1.000001"), domains):
                errors.append(f"{source_id or index}: detail template host not in domains")
        else:
            listing = str(source.get("listingUrl") or "")
            if not listing or not _url_matches_domains(listing, domains):
                errors.append(f"{source_id or index}: listingUrl host not in domains")
        if source.get("legalUse") not in {
            "content_only_no_local_effect",
            "discovery_only_until_code_detail_verified",
            "status_review_required_before_enrichment",
        }:
            errors.append(f"{source_id or index}: legalUse invalid")
    return errors


def _url_matches_domains(value: str, domains: list[str]) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        host == domain.lower() or host.endswith("." + domain.lower())
        for domain in domains
    )


def sources_for_field(registry: dict, field: str) -> list[dict]:
    return [
        source
        for source in registry.get("sources") or []
        if field in (source.get("fields") or [])
    ]


def build_plan(master: dict, registry: dict, priority_only: bool = True) -> dict:
    errors = validate_registry(registry)
    if errors:
        raise ValueError("\n".join(errors))

    rows = []
    source_counts: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for procedure in master.get("thuTuc") or []:
        if priority_only and not procedure.get("priority51"):
            continue
        code = str(procedure.get("ma") or "").strip()
        field = str(procedure.get("linhVuc") or "").strip()
        candidates = sources_for_field(registry, field)
        candidate_rows = []
        for source in candidates:
            source_id = source["id"]
            status = source["status"]
            entry = {
                "sourceId": source_id,
                "authority": source["authority"],
                "adapter": source["adapter"],
                "status": status,
                "legalUse": source["legalUse"],
            }
            if source["adapter"] == "direct_code_detail":
                entry["candidateUrl"] = source["detailUrlTemplate"].format(code=code)
            else:
                entry["candidateUrl"] = source["listingUrl"]
                entry["queryCode"] = code
            candidate_rows.append(entry)
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1
        rows.append({
            "ma": code,
            "ten": procedure.get("ten") or "",
            "linhVuc": field,
            "priority51Ordinal": procedure.get("priority51Ordinal"),
            "formalityId": procedure.get("formalityId") or "",
            "submissionUrl": procedure.get("nopHoSoUrl") or "",
            "sources": candidate_rows,
            "sourceCoverage": "ready" if any(x["status"] in {"ready", "ready_search"} for x in candidate_rows) else "discovery_only" if candidate_rows else "missing",
        })
    return {
        "format": "central-guidance-plan",
        "version": 1,
        "priorityOnly": priority_only,
        "policy": "Candidate plan only. It never mutates canonical or legal status.",
        "summary": {
            "procedures": len(rows),
            "withReadySource": sum(1 for row in rows if row["sourceCoverage"] == "ready"),
            "discoveryOnly": sum(1 for row in rows if row["sourceCoverage"] == "discovery_only"),
            "missingSource": sum(1 for row in rows if row["sourceCoverage"] == "missing"),
            "sourceAssignments": source_counts,
            "assignmentStatuses": statuses,
        },
        "procedures": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Plan all active canonical procedures instead of Priority 50")
    parser.add_argument("--check", action="store_true", help="Validate registry only")
    args = parser.parse_args()

    registry = load_json(REGISTRY)
    errors = validate_registry(registry)
    if errors:
        raise SystemExit("\n".join(errors))
    if args.check:
        print(json.dumps({"status": "PASS", "sources": len(registry["sources"])}, ensure_ascii=False))
        return 0

    master = load_json(MASTER)
    plan = build_plan(master, registry, priority_only=not args.all)
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
