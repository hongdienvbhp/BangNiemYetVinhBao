#!/usr/bin/env python3
import json
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import parse_qs,urlparse

ROOT=Path(__file__).resolve().parents[1]
p=json.loads((ROOT/"data/thu-tuc.json").read_text(encoding="utf-8-sig"))
rows=[x for x in p.get("thuTuc") or [] if isinstance(x,dict)]
by=defaultdict(list)
for x in rows:
    cap=str(x.get("cap") or "").strip()
    by[cap].append({
      "ma":x.get("ma"),"ten":x.get("ten"),
      "tiepNhanCapXa":x.get("tiepNhanCapXa"),
      "formalityId":x.get("formalityId"),
      "nopHoSoUrl":x.get("nopHoSoUrl"),
      "scope":x.get("nopHoSoScope"),
      "verificationStatus":x.get("verificationStatus")
    })
out={
 "total":len(rows),
 "capCounts":{k:len(v) for k,v in sorted(by.items(),key=lambda kv:(-len(kv[1]),kv[0]))},
 "samples":{k:v[:8] for k,v in by.items()},
 "tiepNhanCapXa":Counter(str(bool(x.get("tiepNhanCapXa"))) for x in rows),
}
print(json.dumps(out,ensure_ascii=False,indent=2))
