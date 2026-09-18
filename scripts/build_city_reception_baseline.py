#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build verified city TTHC reception baseline from the official Hai Phong PDF."""
from __future__ import annotations
import argparse, hashlib, io, json, re
from pathlib import Path
from urllib.request import Request, urlopen
from pypdf import PdfReader

ARTICLE_URL = "https://haiphong.gov.vn/thu-tuc-hanh-chinh-76761/danh-muc-thu-tuc-hanh-chinh-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong--760833"
PDF_URL = "https://cdn.haiphong.gov.vn/gov-hpg/1/tintuc/2025/7/danh-muc-thu-tuc-hanh-chinh-thuc-hien-tiep-nhan-tai-trung-tam-phuc-vu-hanh-chinh-cong-thanh-pho-hai-phong638871741697189500.pdf"
PUBLISHED_DATE = "2025-07-03"
EXPECTED_SHA256 = "22c2a8ab6abc6aa0df4694da6eebafe51f5a75bf76bae97f22c19af5fa082425"
EXPECTED_PAGES = 114
CODE_RE = re.compile(r"^\d{1,2}\.\d{3,6}$")
AGENCY_RE = re.compile(r"^(?:[IVXLCDM]+\.|\d+\.)\s+(?:SỞ|BAN|VĂN PHÒNG|THANH TRA|CÔNG AN|UBND|ỦY BAN)", re.I)

def space(v): return re.sub(r"\s+", " ", v or "").strip()
def norm_code(v):
    v=v.strip().rstrip(".")
    if not CODE_RE.fullmatch(v): return v
    a,b=v.split(".",1)
    return f"{a}.{b.ljust(6,'0')}"
def fetch_pdf():
    req=Request(PDF_URL, headers={"User-Agent":"BangNiemYetVinhBao-City-Baseline/1.0"})
    with urlopen(req, timeout=60) as resp: data=resp.read()
    if not data.startswith(b"%PDF"): raise RuntimeError("Official attachment is not PDF")
    return data

def fragments(page):
    out=[]
    def visitor(text,cm,tm,font,size):
        value=space(text)
        if value: out.append((float(tm[5]),float(tm[4]),value))
    page.extract_text(visitor_text=visitor)
    return out

def column(items, lower, upper, xmin, xmax):
    selected=[z for z in items if lower < z[0] <= upper and xmin <= z[1] < xmax]
    buckets={}
    for z in selected: buckets.setdefault(round(z[0],1),[]).append(z)
    lines=[]
    for y in sorted(buckets, reverse=True):
        line=space(" ".join(z[2] for z in sorted(buckets[y],key=lambda q:q[1])))
        if line: lines.append(line)
    return space(" ".join(lines))

def extract_rows(reader):
    rows=[]; carried=""
    for page_no,page in enumerate(reader.pages,start=1):
        items=fragments(page)
        headings=[(y,space(t)) for y,x,t in items if x < 220 and AGENCY_RE.match(space(t))]
        headings.sort(key=lambda z:-z[0])
        codes=[]
        for y,x,t in items:
            c=t.strip().rstrip(".")
            if 105 <= x <= 175 and CODE_RE.fullmatch(c): codes.append((y,x,norm_code(c)))
        codes.sort(key=lambda z:-z[0])
        for i,(y,x,code) in enumerate(codes):
            upper=(codes[i-1][0]+y)/2 if i else min(730.0,y+58.0)
            lower=(y+codes[i+1][0])/2 if i+1<len(codes) else max(42.0,y-58.0)
            agency=carried
            above=[h for h in headings if h[0] > y]
            if above: agency=min(above,key=lambda h:h[0]-y)[1]
            if agency: carried=agency
            rows.append({
                "code":code,
                "name":column(items,lower,upper,180.0,443.0),
                "field":column(items,lower,upper,443.0,700.0),
                "agency":agency,
                "page":page_no,
            })
        if headings: carried=headings[-1][1]
    return rows

def dedupe(rows):
    out={}
    for row in rows:
        code=row["code"]
        prev=out.get(code)
        if not prev:
            out[code]=row; continue
        for key in ("name","field","agency"):
            old=space(str(prev.get(key,""))); new=space(str(row.get(key,"")))
            if old and new and old != new:
                if key in ("name","field"):
                    prev[key]=max((old,new), key=lambda value: (len(value), value))
                    continue
                if key == "agency":
                    prev[key]="; ".join(dict.fromkeys([*old.split("; "), *new.split("; ")]))
                    continue
                raise RuntimeError(f"Conflicting official baseline {code} {key}: {old!r} != {new!r}")
            if not old and new: prev[key]=new
    return sorted(out.values(),key=lambda r:r["code"])

def build(data):
    digest=hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256: raise RuntimeError(f"SHA256 changed: {digest}")
    reader=PdfReader(io.BytesIO(data))
    if len(reader.pages) != EXPECTED_PAGES: raise RuntimeError(f"Page count changed: {len(reader.pages)}")
    rows=dedupe(extract_rows(reader))
    if len(rows) < 300: raise RuntimeError(f"Implausibly small baseline: {len(rows)}")
    missing_name=[r["code"] for r in rows if not space(str(r.get("name","")))]
    if missing_name: raise RuntimeError(f"Rows without name: {missing_name[:20]}")
    return {
      "format":"haiphong-city-reception-baseline","version":1,
      "publishedDate":PUBLISHED_DATE,"articleUrl":ARTICLE_URL,"pdfUrl":PDF_URL,
      "pdfSha256":digest,"pageCount":len(reader.pages),
      "scope":"TTHC tiếp nhận tại Trung tâm Phục vụ hành chính công thành phố Hải Phòng",
      "rowCount":len(rows),"emptyFieldCount":sum(not space(str(r.get("field",""))) for r in rows),
      "rows":rows,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--pdf",type=Path); ap.add_argument("--output",type=Path,default=Path("data/source-audit/city-reception-baseline.json")); args=ap.parse_args()
    data=args.pdf.read_bytes() if args.pdf else fetch_pdf()
    payload=build(data)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:payload[k] for k in ("rowCount","emptyFieldCount","pageCount","pdfSha256")},ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
