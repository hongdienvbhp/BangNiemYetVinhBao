#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/source-audit/priority50-process-forms-current.json"
CROSSWALK = ROOT / "data/priority-51-crosswalk.json"
GUIDANCE = ROOT / "data/tthc-guidance-enrichment.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def exact_vinhbao_url(existing: str, formality_id: str) -> str:
    parsed = urlparse(existing)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.pop("keyword", None)
    query["formalityId"] = formality_id
    query["searchType"] = "PROVINCE"
    query["provinceCode"] = "31"
    query["wardCode"] = "11824"
    query["commune"] = "WARD"
    query["showAdvanced"] = "false"
    query["isProvince"] = "0"
    query["isMinistry"] = "0"
    return urlunparse((
        "https",
        "dichvucong.gov.vn",
        "/tim-kiem-thu-tuc-hanh-chinh",
        "",
        urlencode(query),
        "",
    ))


def main() -> int:
    snapshot = load(SNAPSHOT)
    crosswalk = load(CROSSWALK)
    guidance = load(GUIDANCE)
    verified_at = str(snapshot.get("capturedAt") or "")

    selected = {
        str(row.get("ma") or "").strip(): str(row.get("formalityId") or "").strip()
        for row in snapshot.get("rows") or []
        if isinstance(row, dict) and str(row.get("formalityId") or "").strip()
    }
    crosswalk_by_code = {
        str(row.get("code") or "").strip(): row
        for row in crosswalk.get("items") or []
        if isinstance(row, dict)
    }
    guidance_by_code = {
        str(row.get("ma") or "").strip(): row
        for row in guidance.get("rows") or []
        if isinstance(row, dict)
    }

    changed: list[dict] = []
    for code, formality_id in sorted(selected.items()):
        item = crosswalk_by_code.get(code)
        row = guidance_by_code.get(code)
        if item is None or row is None:
            continue
        current = str(item.get("formalityId") or "").strip()
        if current == formality_id:
            continue

        old_url = str(item.get("dvcUrl") or row.get("submissionUrl") or "").strip()
        new_url = exact_vinhbao_url(old_url, formality_id)
        changed.append({"ma": code, "old": current, "new": formality_id})

        item["formalityId"] = formality_id
        item["dvcUrl"] = new_url
        item["mappingMode"] = "formality_id"
        item["mappingStatus"] = "verified_dvcqg_api_identity"
        item["liveVerificationResult"] = "VERIFIED_API_CODE_IDENTITY"
        item["liveVerifiedAt"] = verified_at
        item["sourceAuditSnapshot"] = "data/source-audit/priority50-process-forms-current.json"
        item["note"] = (
            "formalityId được đối chiếu live bằng API công khai DVCQG; "
            "chỉ chấp nhận khi response data.code khớp tuyệt đối mã TTHC."
        )

        row["formalityId"] = formality_id
        row["submissionUrl"] = new_url
        dvctt = row.get("dvctt")
        if isinstance(dvctt, dict):
            dvctt["accessUrl"] = new_url
            dvctt["formalityId"] = formality_id
            dvctt["mappingMode"] = "formality_id"
            dvctt["verificationStatus"] = "vinhbao_scope_parameters_verified"
        for source in row.get("sources") or []:
            if isinstance(source, dict) and source.get("sourceRole") == "local_execution":
                source["url"] = new_url
                source["verifiedAt"] = verified_at

    CROSSWALK.write_text(json.dumps(crosswalk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    GUIDANCE.write_text(json.dumps(guidance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"changed": len(changed), "rows": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
