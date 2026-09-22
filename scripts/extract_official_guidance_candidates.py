#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source-audit" / "vinhbao-tthc-attachment-evidence-20260906.json"
OUT = ROOT / "data" / "source-audit" / "official-guidance-candidates.json"

CODE_RE = re.compile(r"\b\d{1,2}\.\d{3,6}\b")
DURATION_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ngày|giờ|tháng|năm)(?:\s+làm việc)?\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(r"\b\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?\s*đồng\b", re.IGNORECASE)
LEGAL_RE = re.compile(
    r"\b(?:Nghị định|Thông tư|Nghị quyết|Quyết định|Luật)\s+(?:số\s+)?"
    r"[A-ZÀ-Ỹ0-9./-]{2,}(?:\s+ngày\s+\d{1,2}/\d{1,2}/\d{4})?",
    re.IGNORECASE,
)

def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def procedure_segment(code: str, snippet: str) -> str:
    text = normalize_space(snippet)
    pos = text.find(code)
    if pos < 0:
        return ""
    tail = text[pos:]
    nxt = CODE_RE.search(tail, len(code))
    if nxt:
        tail = tail[:nxt.start()]
    return tail[:1800].strip()

def online_level(segment: str) -> str:
    folded = segment.lower()
    has_full = "toàn trình" in folded
    has_partial = "một phần" in folded
    if has_full and not has_partial:
        return "FULL"
    if has_partial and not has_full:
        return "PARTIAL"
    return "UNKNOWN"

def guidance_candidates(segment: str) -> dict:
    durations = list(dict.fromkeys(normalize_space(x) for x in DURATION_RE.findall(segment)))
    fees = list(dict.fromkeys(normalize_space(x) for x in MONEY_RE.findall(segment)))
    legal = list(dict.fromkeys(normalize_space(x) for x in LEGAL_RE.findall(segment)))
    folded = segment.lower()
    fee_status = ""
    if "miễn lệ phí" in folded or "miễn phí" in folded:
        fee_status = "EXEMPT"
    elif "không quy định" in folded and not fees:
        fee_status = "NOT_PUBLISHED"
    agency = []
    for label in (
        "Ủy ban nhân dân cấp xã",
        "UBND cấp xã",
        "Trung tâm Phục vụ hành chính công cấp xã",
        "Trung tâm PVHCC cấp xã",
        "Trung tâm Phục vụ hành chính công thành phố",
        "Trung tâm PVHCC thành phố",
    ):
        if label.lower() in folded and label not in agency:
            agency.append(label)
    return {
        "onlineServiceLevelCandidate": online_level(segment),
        "durationCandidates": durations[:6],
        "feeCandidates": fees[:6],
        "feeStatusCandidate": fee_status or "UNKNOWN",
        "legalBasisCandidates": legal[:12],
        "agencyCandidates": agency,
    }

def build(payload: dict) -> dict:
    by_code: dict[str, list[dict]] = {}
    for attachment in payload.get("attachments") or []:
        for item in attachment.get("code_snippets") or []:
            code = str(item.get("code") or "").strip()
            segment = procedure_segment(code, str(item.get("snippet") or ""))
            if not code or not segment:
                continue
            fields = guidance_candidates(segment)
            signal_count = sum([
                fields["onlineServiceLevelCandidate"] != "UNKNOWN",
                bool(fields["durationCandidates"]),
                bool(fields["feeCandidates"]),
                fields["feeStatusCandidate"] != "UNKNOWN",
                bool(fields["legalBasisCandidates"]),
                bool(fields["agencyCandidates"]),
            ])
            if not signal_count:
                continue
            by_code.setdefault(code, []).append({
                **fields,
                "segment": segment,
                "attachmentUrl": attachment.get("url"),
                "articleUrls": attachment.get("article_urls") or [],
                "decisionNumbers": attachment.get("decision_numbers") or [],
                "confidence": "candidate_only",
            })

    rows = []
    for code, evidence in sorted(by_code.items()):
        online_values = sorted({
            item["onlineServiceLevelCandidate"]
            for item in evidence
            if item["onlineServiceLevelCandidate"] != "UNKNOWN"
        })
        rows.append({
            "ma": code,
            "verificationStatus": "candidate_only_requires_field_validator",
            "onlineServiceLevelCandidate": online_values[0] if len(online_values) == 1 else "UNKNOWN",
            "durationCandidates": list(dict.fromkeys(
                value for item in evidence for value in item["durationCandidates"]
            ))[:12],
            "feeCandidates": list(dict.fromkeys(
                value for item in evidence for value in item["feeCandidates"]
            ))[:12],
            "feeStatusCandidates": sorted({
                item["feeStatusCandidate"]
                for item in evidence
                if item["feeStatusCandidate"] != "UNKNOWN"
            }),
            "legalBasisCandidates": list(dict.fromkeys(
                value for item in evidence for value in item["legalBasisCandidates"]
            ))[:24],
            "agencyCandidates": list(dict.fromkeys(
                value for item in evidence for value in item["agencyCandidates"]
            )),
            "evidence": evidence,
        })

    return {
        "format": "official-guidance-candidates",
        "version": 1,
        "source": str(SOURCE.relative_to(ROOT)),
        "policy": (
            "Candidate layer only. Không tự động ghi vào canonical. "
            "Mỗi trường phải qua field-level validator và provenance gate trước promotion."
        ),
        "summary": {
            "codes": len(rows),
            "onlineServiceLevelCandidates": sum(1 for x in rows if x["onlineServiceLevelCandidate"] != "UNKNOWN"),
            "durationCandidates": sum(1 for x in rows if x["durationCandidates"]),
            "feeCandidates": sum(1 for x in rows if x["feeCandidates"] or x["feeStatusCandidates"]),
            "legalBasisCandidates": sum(1 for x in rows if x["legalBasisCandidates"]),
            "agencyCandidates": sum(1 for x in rows if x["agencyCandidates"]),
        },
        "rows": rows,
    }

def main() -> int:
    payload = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
    result = build(payload)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
