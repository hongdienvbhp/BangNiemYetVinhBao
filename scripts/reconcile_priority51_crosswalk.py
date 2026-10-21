#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "data/priority-51-crosswalk.json"
MASTER = ROOT / "data/thu-tuc.json"
LIVE = ROOT / "data/source-audit/dvcqg-live-verification-current.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    crosswalk = load(CROSSWALK)
    master = load(MASTER)
    live = load(LIVE)

    items = crosswalk.get("items") or []
    rows = master.get("thuTuc") or []
    live_items = live.get("items") or []
    if len(items) != 51:
        raise ValueError(f"Expected 51 crosswalk items, found {len(items)}")
    if len(live_items) != 51:
        raise ValueError(f"Expected 51 live verification items, found {len(live_items)}")

    master_by_code = {str(row.get("ma") or "").strip(): row for row in rows}
    live_by_code = {str(row.get("code") or "").strip(): row for row in live_items}
    crosswalk_codes = {str(item.get("code") or "").strip() for item in items}
    if set(live_by_code) != crosswalk_codes:
        raise ValueError("Live DVCQG manifest and priority-51 crosswalk code sets differ")

    for item in items:
        code = str(item.get("code") or "").strip()
        master_row = master_by_code.get(code)
        live_row = live_by_code[code]
        if master_row:
            item["inCurrentMaster"] = True
            item["currentMasterName"] = master_row.get("ten")
            item["exactNameMatch"] = item.get("name") == master_row.get("ten")
        else:
            item["inCurrentMaster"] = False
            item["currentMasterName"] = None
            item["exactNameMatch"] = None

        item["liveVerificationResult"] = live_row.get("result")
        item["liveNameVisible"] = bool(live_row.get("name_visible"))
        item["liveAgencyVisible"] = bool(live_row.get("vinh_bao_agency_visible"))
        item["liveVerifiedAt"] = live.get("verified_at")

    present = sum(1 for item in items if item.get("inCurrentMaster") is True)
    direct = [item for item in items if item.get("formalityId")]
    fallbacks = [item for item in items if item.get("mappingMode") == "keyword_fallback"]
    totals = live.get("totals") or {}

    summary = crosswalk.setdefault("summary", {})
    summary.update(
        {
            "total": len(items),
            "uniqueCodes": len(crosswalk_codes),
            "directFormalityIds": len(direct),
            "uniqueFormalityIds": len({item["formalityId"] for item in direct}),
            "keywordFallbacks": len(fallbacks),
            "inCurrentMaster": present,
            "missingFromCurrentMaster": len(items) - present,
            "liveVerifiedIdentity": int(totals.get("verified_identity_only") or 0)
            + int(totals.get("verified_identity_and_agency") or 0),
            "liveVerifiedIdentityAndAgency": int(totals.get("verified_identity_and_agency") or 0),
            "liveUnresolved": int(totals.get("unresolved") or 0),
            "liveWafRejected": int(totals.get("waf_rejected") or 0),
        }
    )
    crosswalk["canonicalDatasetVersion"] = master.get("dataset_version")
    crosswalk["canonicalSourceCommit"] = master.get("source_commit")
    crosswalk["canonicalContract"] = "data/thu-tuc.json"
    crosswalk["liveVerificationManifest"] = "data/source-audit/dvcqg-live-verification-current.json"
    crosswalk["liveVerifiedAt"] = live.get("verified_at")
    crosswalk["namePolicy"] = (
        "Crosswalk name is a technical snapshot only. currentMasterName from data/thu-tuc.json "
        "is the canonical display name; legal status is never inferred from this crosswalk."
    )

    CROSSWALK.write_text(
        json.dumps(crosswalk, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "priority51": len(items),
                "in_current_master": present,
                "missing": len(items) - present,
                "live_verified_identity": summary["liveVerifiedIdentity"],
                "live_unresolved": summary["liveUnresolved"],
                "live_waf_rejected": summary["liveWafRejected"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
