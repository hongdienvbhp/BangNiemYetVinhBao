#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "data/priority-51-crosswalk.json"
MASTER = ROOT / "data/thu-tuc.json"
LIVE = ROOT / "data/source-audit/dvcqg-live-verification-current.json"
LEGAL = ROOT / "data/priority-51-legal-verification.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def legal_projection(row: dict | None) -> dict:
    if row is None:
        return {
            "status": "not_covered_by_legal_verification_manifest",
            "manifest": "data/priority-51-legal-verification.json",
        }
    sources = row.get("sources") or []
    urls = sorted({str(source.get("url") or "").strip() for source in sources if isinstance(source, dict) and str(source.get("url") or "").strip()})
    return {
        "status": row.get("legalStatus"),
        "communeScopeEvidence": bool(row.get("communeScopeEvidence")),
        "decisionNo": row.get("decisionNo"),
        "decisionDate": row.get("decisionDate"),
        "checkedAt": row.get("verificationCheckedAt"),
        "basis": row.get("legalStatusBasis"),
        "dvcqgRole": row.get("dvcqgRole"),
        "sourceUrls": urls,
    }


def main() -> int:
    crosswalk = load(CROSSWALK)
    master = load(MASTER)
    live = load(LIVE)
    legal = load(LEGAL)

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

    legal_rows = legal.get("rows") or []
    legal_by_code: dict[str, dict] = {}
    for row in legal_rows:
        code = str(row.get("code") or "").strip()
        if not code:
            raise ValueError("Priority-51 legal verification contains a row without code")
        if code in legal_by_code:
            raise ValueError(f"Priority-51 legal verification contains duplicate code {code}")
        if code not in crosswalk_codes:
            raise ValueError(f"Priority-51 legal verification code {code} is outside the crosswalk")
        legal_by_code[code] = row
    legal_summary = legal.get("summary") or {}
    expected_legal_rows = int(legal_summary.get("total") or 0)
    if expected_legal_rows != len(legal_rows):
        raise ValueError(f"Priority-51 legal verification summary says {expected_legal_rows} rows; found {len(legal_rows)}")

    missing_codes = {str(item.get("code") or "").strip() for item in items if str(item.get("code") or "").strip() not in master_by_code}
    missing_without_repeal_evidence = sorted(
        code for code in missing_codes
        if (legal_by_code.get(code) or {}).get("legalStatus") != "repealed_official_evidence"
    )
    if missing_without_repeal_evidence:
        raise ValueError(
            "Priority 51 code(s) are absent from Master Data without official repeal evidence: "
            + ", ".join(missing_without_repeal_evidence)
        )

    for item in items:
        code = str(item.get("code") or "").strip()
        master_row = master_by_code.get(code)
        live_row = live_by_code[code]
        legal_row = legal_by_code.get(code)
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
        item["legalVerification"] = legal_projection(legal_row)

    present = sum(1 for item in items if item.get("inCurrentMaster") is True)
    direct = [item for item in items if item.get("formalityId")]
    fallbacks = [item for item in items if item.get("mappingMode") == "keyword_fallback"]
    totals = live.get("totals") or {}
    legal_current = sum(1 for row in legal_rows if row.get("legalStatus") == "current_official_commune_evidence")
    legal_repealed = sum(1 for row in legal_rows if row.get("legalStatus") == "repealed_official_evidence")
    legal_needs_review = sum(1 for row in legal_rows if row.get("legalStatus") == "needs_verification")
    missing_repealed = sum(1 for code in missing_codes if (legal_by_code.get(code) or {}).get("legalStatus") == "repealed_official_evidence")
    missing_current = sum(1 for code in missing_codes if (legal_by_code.get(code) or {}).get("legalStatus") == "current_official_commune_evidence")
    missing_unknown = len(missing_codes) - missing_repealed - missing_current

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
            "legalVerificationCovered": len(legal_by_code),
            "legalCurrentOfficialCommune": legal_current,
            "legalRepealedOfficial": legal_repealed,
            "legalNeedsVerification": legal_needs_review,
            "missingFromMasterWithRepealedOfficialEvidence": missing_repealed,
            "missingFromMasterWithCurrentLegalEvidence": missing_current,
            "missingFromMasterWithoutLegalEvidence": missing_unknown,
        }
    )
    crosswalk["canonicalDatasetVersion"] = master.get("dataset_version")
    crosswalk["canonicalSourceCommit"] = master.get("source_commit")
    crosswalk["canonicalContract"] = "data/thu-tuc.json"
    crosswalk["liveVerificationManifest"] = "data/source-audit/dvcqg-live-verification-current.json"
    crosswalk["legalVerificationManifest"] = "data/priority-51-legal-verification.json"
    crosswalk["liveVerifiedAt"] = live.get("verified_at")
    crosswalk["namePolicy"] = (
        "Crosswalk name and formalityId are technical snapshots only. currentMasterName from data/thu-tuc.json "
        "is the canonical display name. legalVerification is copied from the separately reviewed official-source "
        "manifest data/priority-51-legal-verification.json; DVCQG identity evidence never establishes legal status."
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
                "missing_repealed_official": missing_repealed,
                "missing_current_legal_evidence": missing_current,
                "missing_without_legal_evidence": missing_unknown,
                "legal_verification_covered": len(legal_by_code),
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
