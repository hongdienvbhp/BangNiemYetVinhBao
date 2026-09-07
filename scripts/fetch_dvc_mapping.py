#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch slim technical DVCQG mappings for the candidate code set.

The upstream dataset is a third-party snapshot of dichvucong.gov.vn and is
used only for technical formalityId/name/category assistance, never for legal
current/repealed status.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE_CANDIDATES = ROOT / "data/source-audit/web010-vinhbao-commune-code-candidates-20260906.json"
CITY_UPDATES = ROOT / "data/source-audit/city-updates-current.json"
OUTPUT = ROOT / "data/source-audit/dvcqg-mapping-candidates-20260907.json"

API = "https://datasets-server.huggingface.co/filter"
DATASET = "tmquan/dichvucong-gov-vn"
CONFIG = "procedures"
SPLIT = "train"
BATCH_SIZE = 5


def target_codes() -> set[str]:
    base = json.loads(BASE_CANDIDATES.read_text(encoding="utf-8"))
    codes = {
        x["procedure_code"].strip()
        for x in base.get("candidates", [])
        if x.get("procedure_code")
    }
    if CITY_UPDATES.exists():
        city = json.loads(CITY_UPDATES.read_text(encoding="utf-8"))
        codes.update(
            x["code"].strip()
            for x in city.get("rows", [])
            if x.get("code")
        )
    return codes


def fetch_filter(codes: list[str]) -> list[dict]:
    predicates = ['"code" = ' + repr(c) for c in codes]
    where = " OR ".join(predicates)
    params = urlencode({
        "dataset": DATASET,
        "config": CONFIG,
        "split": SPLIT,
        "where": where,
        "offset": 0,
        "length": 100,
    })
    req = Request(
        API + "?" + params,
        headers={"User-Agent": "BangNiemYetVinhBao/1.0"},
    )
    delay = 4
    for attempt in range(5):
        try:
            with urlopen(req, timeout=40) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return [item.get("row") or {} for item in payload.get("rows", [])]
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 4:
                raise
        except URLError:
            if attempt == 4:
                raise
        time.sleep(delay)
        delay *= 2
    return []


def main() -> int:
    targets = sorted(target_codes())
    raw_rows = []
    for i in range(0, len(targets), BATCH_SIZE):
        batch = targets[i : i + BATCH_SIZE]
        raw_rows.extend(fetch_filter(batch))
        if i + BATCH_SIZE < len(targets):
            time.sleep(1.2)

    rows = []
    seen = set()
    for row in raw_rows:
        code = str(row.get("code") or "").strip()
        fid = str(row.get("formality_id") or "").strip()
        source_url = str(row.get("source_url") or "")
        key = (code, fid, source_url)
        if code not in targets or key in seen:
            continue
        seen.add(key)
        rows.append({
            "code": code,
            "formalityId": fid,
            "procedureName": row.get("procedure_name") or "",
            "categoryName": row.get("category_name") or "",
            "decisionNo": row.get("decision_no") or "",
            "departmentPromulgate": row.get("department_promulgate") or "",
            "is_ministry": bool(row.get("is_ministry")),
            "is_province": bool(row.get("is_province")),
            "is_ward": bool(row.get("is_ward")),
            "is_vertical": bool(row.get("is_vertical")),
            "is_full_process": bool(row.get("is_full_process")),
            "sourceUrl": source_url,
            "scrapedAt": row.get("scraped_at") or "",
            "verificationStatus": "third_party_snapshot_of_dvcqg_technical_mapping",
        })

    rows.sort(key=lambda x: (
        x["code"],
        not x["is_ward"],
        not x["is_province"],
        x["formalityId"],
    ))
    mapped = {x["code"] for x in rows if x.get("formalityId")}
    payload = {
        "format": "dvcqg-technical-mapping-candidates",
        "version": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET,
        "datasetConfig": CONFIG,
        "sourcePolicy": (
            "Technical mapping only. Third-party snapshot of dichvucong.gov.vn; "
            "not evidence of TTHC legal/current status."
        ),
        "targetCandidateCodes": len(targets),
        "mappedCodes": len(mapped),
        "unmappedCodes": sorted(set(targets) - mapped),
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "targetCandidateCodes": len(targets),
        "matchedRows": len(rows),
        "mappedCodes": len(mapped),
        "unmappedCodes": len(set(targets) - mapped),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
