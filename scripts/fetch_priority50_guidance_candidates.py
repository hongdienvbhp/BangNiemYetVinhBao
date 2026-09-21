#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
OUTPUT = ROOT / "data/source-audit/priority50-guidance-candidates.json"

API = "https://datasets-server.huggingface.co/filter"
DATASET = "tmquan/dichvucong-gov-vn"
CONFIG = "procedures"
SPLIT = "train"
BATCH_SIZE = 5
TARGET = 50

FIELDS = (
    "execution_methods",
    "profile_components",
    "fees",
    "results",
    "executing_agencies",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fetch_filter(codes: list[str]) -> list[dict]:
    where = " OR ".join('"code" = ' + repr(code) for code in codes)
    params = urlencode({
        "dataset": DATASET,
        "config": CONFIG,
        "split": SPLIT,
        "where": where,
        "offset": 0,
        "length": 100,
    })
    request = Request(
        API + "?" + params,
        headers={"User-Agent": "BangNiemYetVinhBao/1.0"},
    )
    delay = 2
    for attempt in range(5):
        try:
            with urlopen(request, timeout=45) as response:
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


def score(row: dict, canonical: dict) -> tuple:
    fid = str(canonical.get("formalityId") or "").strip()
    return (
        str(row.get("formality_id") or "").strip() == fid and bool(fid),
        bool(row.get("is_ward")),
        bool(row.get("is_province")),
        sum(bool(str(row.get(field) or "").strip()) for field in FIELDS),
        str(row.get("scraped_at") or ""),
    )


def fetch_parquet(path: Path, codes: set[str]) -> list[dict]:
    import pyarrow.parquet as pq
    columns = [
        "formality_id", "code", "procedure_name", "is_ward", "is_province",
        "is_full_process", "execution_methods", "profile_components", "fees",
        "results", "executing_agencies", "source_url", "source", "content_hash",
        "scraped_at",
    ]
    table = pq.read_table(path, columns=columns)
    data = table.to_pylist()
    return [
        row for row in data
        if str(row.get("code") or "").strip() in codes
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", type=Path)
    args = parser.parse_args()
    master = load(MASTER)
    target_rows = [
        row for row in master.get("thuTuc") or []
        if isinstance(row, dict) and row.get("priority51") is True
    ]
    if len(target_rows) != TARGET:
        raise ValueError(f"Expected {TARGET} active priority procedures, found {len(target_rows)}")

    by_code = {str(row["ma"]).strip(): row for row in target_rows}
    codes = sorted(by_code)
    if args.parquet:
        fetched = fetch_parquet(args.parquet, set(codes))
    else:
        fetched: list[dict] = []
        for offset in range(0, len(codes), BATCH_SIZE):
            fetched.extend(fetch_filter(codes[offset:offset + BATCH_SIZE]))
            if offset + BATCH_SIZE < len(codes):
                time.sleep(0.5)

    candidates: list[dict] = []
    missing: list[str] = []
    for code in codes:
        variants = [
            row for row in fetched
            if str(row.get("code") or "").strip() == code
        ]
        if not variants:
            missing.append(code)
            continue
        variants.sort(key=lambda row: score(row, by_code[code]), reverse=True)
        best = variants[0]
        canonical = by_code[code]
        candidates.append({
            "ma": code,
            "canonicalName": canonical.get("ten") or "",
            "candidateName": best.get("procedure_name") or "",
            "canonicalFormalityId": canonical.get("formalityId") or "",
            "candidateFormalityId": best.get("formality_id") or "",
            "nameExact": (canonical.get("ten") or "").strip() == (best.get("procedure_name") or "").strip(),
            "formalityIdExact": bool(canonical.get("formalityId")) and (
                str(canonical.get("formalityId")) == str(best.get("formality_id") or "")
            ),
            "isWard": bool(best.get("is_ward")),
            "isProvince": bool(best.get("is_province")),
            "isFullProcess": bool(best.get("is_full_process")),
            "coQuanThucHien": best.get("executing_agencies") or "",
            "thanhPhanHoSo": best.get("profile_components") or "",
            "thoiHan": best.get("execution_methods") or "",
            "lePhi": best.get("fees") or "",
            "ketQua": best.get("results") or "",
            "sourceUrl": best.get("source_url") or "",
            "sourceHost": best.get("source") or "",
            "contentHash": best.get("content_hash") or "",
            "scrapedAt": best.get("scraped_at") or "",
            "candidateOnly": True,
            "verificationPolicy": (
                "Third-party structured snapshot of official DVCQG. Candidate only; "
                "must not publish until official-source verification passes."
            ),
        })

    payload = {
        "format": "priority50-guidance-candidates",
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dataset": DATASET,
        "datasetConfig": CONFIG,
        "sourcePolicy": (
            "Candidate-only technical extraction from a third-party snapshot of DVCQG. "
            "Canonical publication requires current official-source verification."
        ),
        "target": TARGET,
        "matched": len(candidates),
        "missing": missing,
        "rows": candidates,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target": TARGET,
        "matched": len(candidates),
        "missing": len(missing),
        "nameExact": sum(row["nameExact"] for row in candidates),
        "formalityIdExact": sum(row["formalityIdExact"] for row in candidates),
        "fieldCoverage": {
            field: sum(bool(str(row.get(field) or "").strip()) for row in candidates)
            for field in ("coQuanThucHien","thanhPhanHoSo","thoiHan","lePhi","ketQua")
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
