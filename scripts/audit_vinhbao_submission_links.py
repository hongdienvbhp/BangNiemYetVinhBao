#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/thu-tuc.json"
EXPECTED={"provinceCode":"31","wardCode":"11824","commune":"WARD"}
# CI contract: every published TTHC must resolve through this exact Vĩnh Bảo scope.

def scoped(url:str)->bool:
    try:
        p=urlparse(url)
        q=parse_qs(p.query)
    except Exception:
        return False
    if p.scheme!="https" or (p.hostname or "").lower()!="dichvucong.gov.vn":
        return False
    return all((q.get(k) or [""])[0]==v for k,v in EXPECTED.items())

def main()->int:
    payload=json.loads(DATA.read_text(encoding="utf-8-sig"))
    rows=[x for x in payload.get("thuTuc") or [] if isinstance(x,dict)]
    bad=[]; missing=[]; fid_mismatch=[]; keyword=[]
    for row in rows:
        code=str(row.get("ma") or "").strip()
        url=str(row.get("nopHoSoUrl") or "").strip()
        fid=str(row.get("formalityId") or "").strip()
        if not url:
            missing.append(code); continue
        if not scoped(url):
            bad.append(code); continue
        q=parse_qs(urlparse(url).query)
        actual_fid=(q.get("formalityId") or [""])[0]
        actual_keyword=(q.get("keyword") or [""])[0]
        if fid and actual_fid!=fid:
            fid_mismatch.append({"ma":code,"formalityId":fid,"urlFormalityId":actual_fid})
        if not fid:
            keyword.append({"ma":code,"keyword":actual_keyword})
    report={
        "total":len(rows),
        "withFormalityId":sum(bool(str(x.get("formalityId") or "").strip()) for x in rows),
        "withSubmissionUrl":sum(bool(str(x.get("nopHoSoUrl") or "").strip()) for x in rows),
        "exactScoped":sum(scoped(str(x.get("nopHoSoUrl") or "")) for x in rows),
        "keywordFallback":len(keyword),
        "missing":missing,
        "invalidScope":bad,
        "formalityMismatch":fid_mismatch,
        "keywordRows":keyword,
    }
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if (missing or bad or fid_mismatch) else 0

if __name__=="__main__":
    raise SystemExit(main())
