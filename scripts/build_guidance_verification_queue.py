#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data" / "thu-tuc.json"
LOCATORS = ROOT / "data" / "source-audit" / "dvcqg-formality-candidates-current.json"
OUT = ROOT / "data" / "source-audit" / "guidance-official-verification-queue.json"

REQUIRED_FIELDS = [
    "quyTrinh",
    "thanhPhanHoSo",
    "bieuMau",
    "lePhi",
    "thoiHan",
    "coQuanThucHien",
    "ketQua",
    "dvctt",
]


def norm(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def official_dvcqg_url(value: object) -> bool:
    try:
        parsed = urlparse(norm(value))
    except ValueError:
        return False
    return parsed.scheme == "https" and (parsed.hostname or "").lower() == "dichvucong.gov.vn"


def build(master: dict, locators: dict) -> dict:
    locator_by_code = {
        norm(row.get("ma")): row
        for row in locators.get("rows") or []
        if isinstance(row, dict) and norm(row.get("ma"))
    }
    rows = []
    active = [
        row for row in master.get("thuTuc") or []
        if isinstance(row, dict)
        and norm((row.get("lifecycle") or {}).get("status") or "active") == "active"
    ]
    for row in sorted(active, key=lambda item: norm(item.get("ma"))):
        if isinstance(row.get("huongDan"), dict):
            continue
        code = norm(row.get("ma"))
        locator = locator_by_code.get(code)
        canonical_fid = norm(row.get("formalityId"))
        canonical_name = norm(row.get("ten"))
        candidate_url = norm((locator or {}).get("sourceUrl"))
        exact_identity = bool(
            locator
            and canonical_fid
            and norm(locator.get("formalityId")) == canonical_fid
            and norm(locator.get("canonicalName")) == canonical_name
            and norm(locator.get("candidateName")) == canonical_name
            and official_dvcqg_url(candidate_url)
        )
        rows.append({
            "ma": code,
            "canonicalName": canonical_name,
            "cap": norm(row.get("cap")),
            "formalityId": canonical_fid,
            "localExecutionUrl": norm(row.get("nopHoSoUrl")),
            "candidateOfficialUrl": candidate_url if exact_identity else "",
            "candidateContentHash": norm((locator or {}).get("contentHash")) if exact_identity else "",
            "candidateScrapedAt": norm((locator or {}).get("scrapedAt")) if exact_identity else "",
            "identityMatch": exact_identity,
            "verificationStatus": (
                "awaiting_current_official_verification"
                if exact_identity else "official_locator_unresolved"
            ),
            "requiredFields": REQUIRED_FIELDS,
            "publishAllowed": False,
        })

    return {
        "format": "guidance-official-verification-queue",
        "version": 1,
        "canonicalDatasetVersion": norm(master.get("dataset_version")),
        "canonicalSourceCommit": norm(master.get("source_commit")),
        "policy": (
            "Queue only. Third-party snapshot may locate formalityId/sourceUrl but supplies no publishable content. "
            "publishAllowed remains false until current official DVCQG/government source is verified and field-level provenance passes."
        ),
        "summary": {
            "active": len(active),
            "existingGuidance": sum(isinstance(row.get("huongDan"), dict) for row in active),
            "queued": len(rows),
            "exactOfficialLocators": sum(row["identityMatch"] for row in rows),
            "unresolvedLocators": sum(not row["identityMatch"] for row in rows),
        },
        "rows": rows,
    }


def main() -> int:
    master = json.loads(MASTER.read_text(encoding="utf-8-sig"))
    locators = json.loads(LOCATORS.read_text(encoding="utf-8-sig"))
    result = build(master, locators)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
