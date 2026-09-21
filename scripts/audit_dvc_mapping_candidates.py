#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MASTER=json.loads((ROOT/"data/thu-tuc.json").read_text(encoding="utf-8-sig"))
MAP=json.loads((ROOT/"data/source-audit/dvcqg-mapping-candidates-20260907.json").read_text(encoding="utf-8-sig"))
codes={str(x.get("ma") or "").strip() for x in MASTER.get("thuTuc") or []}
rows=[x for x in MAP.get("rows") or [] if str(x.get("code") or "").strip() in codes]
by={}
for x in rows:
    by.setdefault(str(x.get("code") or "").strip(),[]).append(x)
summary={
 "canonical":len(codes),
 "candidateCodes":len(by),
 "candidateRows":len(rows),
 "withFormalityId":len({c for c,v in by.items() if any(str(x.get("formalityId") or "").strip() for x in v)}),
 "wardCandidates":len({c for c,v in by.items() if any(bool(x.get("is_ward")) for x in v)}),
 "verifiedCandidates":len({c for c,v in by.items() if any(str(x.get("verificationStatus") or "").lower().startswith("verified_") for x in v)}),
 "missingCodes":sorted(codes-set(by)),
 "multiCandidate":sorted([{"ma":c,"count":len(v)} for c,v in by.items() if len(v)>1],key=lambda x:(-x["count"],x["ma"]))[:50],
}
print(json.dumps(summary,ensure_ascii=False,indent=2))
