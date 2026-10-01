#!/usr/bin/env python3
import json, os, sys
from datetime import datetime
from pathlib import Path
import requests

BASE = "https://dichvucong.gov.vn"
ROOT_ID = "019d2be3-6a85-74ec-a349-88e0abf6a032"
YEAR = int(os.getenv("YEAR", "2026"))
MONTH = int(os.getenv("MONTH", "9"))
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "300"))

payload = {
    "timeType": "month",
    "year": YEAR,
    "month": MONTH,
    "rootDepartmentId": ROOT_ID,
    "currentPage": 1,
    "pageSize": PAGE_SIZE,
}
url = BASE + "/api/v1/reporting/evaluation/dossier-digitized"
out = Path(os.getenv("OUTPUT_DIR", "out"))
out.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().astimezone().isoformat()
try:
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
except Exception as exc:
    print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(2)
raw_path = out / f"dossier-digitized-{YEAR}-{MONTH:02d}.json"
raw_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
rows = data.get("data", {}).get("evaluation", [])
vb = next((x for x in rows if x.get("departmentName") == "UBND xã Vĩnh Bảo"), None)
if not vb:
    print("UBND xã Vĩnh Bảo không có trong data.evaluation")
    sys.exit(3)
metrics = vb.get("metrics") or []
snapshot = {
    "collected_at": stamp,
    "source": url,
    "payload": payload,
    "departmentName": vb.get("departmentName"),
    "metrics": [
        {
            "code": m.get("code"),
            "numerator": m.get("numerator"),
            "denominator": m.get("denominator"),
            "ratio": m.get("ratio"),
            "score": m.get("score"),
        }
        for m in metrics
    ],
}
(out / f"snapshot-{YEAR}-{MONTH:02d}.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({
    "departmentName": vb.get("departmentName"),
    "metric_count": len(metrics),
    "REUSED_DIGITIZED_DATA": next((x for x in snapshot["metrics"] if x["code"] == "REUSED_DIGITIZED_DATA"), None),
    "raw_file": str(raw_path)
}, ensure_ascii=False, indent=2))
