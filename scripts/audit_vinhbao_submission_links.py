#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/thu-tuc.json"
EXPECTED={"provinceCode":"31","wardCode":"11824","commune":"WARD"}
# CI contract: every published TTHC must resolve through this exact Vĩnh Bảo scope.

def route_ok(row:dict)->tuple[bool,str]:
    url=str(row.get("nopHoSoUrl") or "").strip()
    try:
        p=urlparse(url); q=parse_qs(p.query)
    except Exception:
        return False,"invalid_url"
    if p.scheme!="https" or (p.hostname or "").lower()!="dichvucong.gov.vn":
        return False,"invalid_host"
    if (q.get("provinceCode") or [""])[0]!="31":
        return False,"wrong_province"
    cap=str(row.get("cap") or "").strip().lower()
    if cap.startswith("cấp tỉnh"):
        if (q.get("isProvince") or [""])[0]!="1":
            return False,"province_missing_isProvince"
        for key in ("wardCode","ward","agency","departmentId","commune"):
            if (q.get(key) or [""])[0]:
                return False,"province_forced_to_ward"
        return True,"province"
    if (q.get("wardCode") or [""])[0]!="11824":
        return False,"wrong_ward"
    if (q.get("commune") or [""])[0]!="WARD":
        return False,"wrong_commune"
    if (q.get("isProvince") or [""])[0]!="0":
        return False,"ward_wrong_isProvince"
    return True,"ward"

def main()->int:
    payload=json.loads(DATA.read_text(encoding="utf-8-sig"))
    rows=[x for x in payload.get("thuTuc") or [] if isinstance(x,dict)]
    missing=[]; invalid=[]; fid_mismatch=[]; keyword=[]; routes={"ward":0,"province":0}
    for row in rows:
        code=str(row.get("ma") or "").strip()
        url=str(row.get("nopHoSoUrl") or "").strip()
        fid=str(row.get("formalityId") or "").strip()
        if not url:
            missing.append(code); continue
        ok,route=route_ok(row)
        if not ok:
            invalid.append({"ma":code,"cap":row.get("cap"),"reason":route,"url":url})
            continue
        routes[route]+=1
        q=parse_qs(urlparse(url).query)
        actual_fid=(q.get("formalityId") or [""])[0]
        actual_keyword=(q.get("keyword") or [""])[0]
        if fid and actual_fid!=fid:
            fid_mismatch.append({"ma":code,"formalityId":fid,"urlFormalityId":actual_fid})
        if not fid:
            keyword.append({"ma":code,"keyword":actual_keyword,"route":route})
    report={
        "total":len(rows),
        "withFormalityId":sum(bool(str(x.get("formalityId") or "").strip()) for x in rows),
        "withSubmissionUrl":sum(bool(str(x.get("nopHoSoUrl") or "").strip()) for x in rows),
        "routeCoverage":routes,
        "keywordFallback":len(keyword),
        "missing":missing,
        "invalidRoute":invalid,
        "formalityMismatch":fid_mismatch,
        "keywordRows":keyword,
    }
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 1 if (missing or invalid or fid_mismatch) else 0

if __name__=="__main__":
    raise SystemExit(main())
