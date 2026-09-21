#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/"data/thu-tuc.json"
OUT=ROOT/"data/source-audit/dvcqg-formality-candidates-current.json"

def norm(v): return str(v or "").strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--parquet",type=Path,required=True)
    args=ap.parse_args()
    master=json.loads(MASTER.read_text(encoding="utf-8-sig"))
    codes={norm(x.get("ma")):x for x in master.get("thuTuc") or [] if norm(x.get("ma"))}
    cols=["code","formality_id","procedure_name","is_ward","is_province","source_url","source","content_hash","scraped_at"]
    rows=pq.read_table(args.parquet,columns=cols).to_pylist()
    by={}
    for row in rows:
        code=norm(row.get("code"))
        fid=norm(row.get("formality_id"))
        if code not in codes or not fid: continue
        by.setdefault(code,[]).append(row)

    resolved=[]; missing=[]
    for code,canonical in sorted(codes.items()):
        variants=by.get(code,[])
        variants.sort(key=lambda r:(bool(r.get("is_ward")),not bool(r.get("is_province")),norm(r.get("scraped_at"))),reverse=True)
        if not variants:
            missing.append(code); continue
        best=variants[0]
        resolved.append({
            "ma":code,
            "canonicalName":norm(canonical.get("ten")),
            "formalityId":norm(best.get("formality_id")),
            "candidateName":norm(best.get("procedure_name")),
            "isWard":bool(best.get("is_ward")),
            "isProvince":bool(best.get("is_province")),
            "sourceUrl":norm(best.get("source_url")),
            "sourceHost":norm(best.get("source")),
            "contentHash":norm(best.get("content_hash")),
            "scrapedAt":norm(best.get("scraped_at")),
            "technicalCandidateOnly":True
        })
    payload={
      "format":"dvcqg-formality-candidates-current","version":1,
      "policy":"Technical identity candidates only; exact TTHC code match. Legal lifecycle is never derived from this source.",
      "target":len(codes),"resolved":len(resolved),
      "wardResolved":sum(x["isWard"] for x in resolved),
      "missing":missing,"rows":resolved
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:payload[k] for k in ("target","resolved","wardResolved")}|{"missing":len(missing)},ensure_ascii=False))
if __name__=="__main__": main()
