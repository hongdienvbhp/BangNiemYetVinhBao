#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

SOURCE_ROLES = {
    "central_content_reference",
    "local_legal_effect",
    "local_execution",
}
SOURCE_COMMIT_KIND = "verified_source_bundle_git_sha1"
LIFECYCLE_STATUSES = {"active", "future_effective", "repealed"}

# Inputs that are allowed to influence the canonical dataset. Generated outputs
# are deliberately excluded so source_commit never self-references thu-tuc.json.
SOURCE_BUNDLE_PATHS = (
    "data/source-audit/web010-vinhbao-commune-code-candidates-20260906.json",
    "data/source-audit/vinhbao-tthc-attachment-evidence-20260906.json",
    "data/source-audit/dvcqg-mapping-candidates-20260907.json",
    "data/formalityId-mapping-mau.csv",
    "data/priority-51-legal-verification.json",
    "data/source-audit/city-updates-current.json",
    "data/source-audit/dvcqg-live-verification-current.json",
    "data/source-audit/dvcqg-formality-candidates-current.json",
    "data/tthc-guidance-enrichment.json",
    "js/data.js",
)

_DATE_KEYS = {
    "asOf",
    "baselineDate",
    "checkedAt",
    "generatedAt",
    "legalVerificationCheckedAt",
    "liveVerifiedAt",
    "sourceLatestDate",
    "sourceSnapshotDate",
    "submissionLinkCheckedAt",
    "verifiedAt",
}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_VERSION_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def compute_source_commit(root: Path) -> str:
    """Return a deterministic SHA-1 fingerprint of verified source inputs.

    This is intentionally not the SHA of the commit containing canonical output.
    It is a content-addressed fingerprint over Git-blob hashes of source inputs.
    """
    entries: list[str] = []
    for rel in SOURCE_BUNDLE_PATHS:
        path = root / rel
        if not path.exists():
            continue
        blob_sha = _git_blob_sha(path.read_bytes())
        entries.append(f"{rel}\0{blob_sha}\n")
    if not entries:
        raise ValueError("Không tìm thấy nguồn đầu vào để tính source_commit")
    manifest = "".join(sorted(entries)).encode("utf-8")
    return hashlib.sha1(manifest).hexdigest()


def _collect_dates(value: Any, out: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _DATE_KEYS and isinstance(item, str):
                date = item[:10]
                if _DATE_RE.fullmatch(date):
                    out.add(date)
            _collect_dates(item, out)
    elif isinstance(value, list):
        for item in value:
            _collect_dates(item, out)


def derive_dataset_date(root: Path, existing_version: str = "") -> str:
    """Choose the newest verified snapshot/enrichment date without version rollback."""
    dates: set[str] = set()
    if _VERSION_RE.fullmatch(existing_version or ""):
        dates.add(existing_version.replace(".", "-"))
    for rel in SOURCE_BUNDLE_PATHS:
        path = root / rel
        if not path.exists() or path.suffix.lower() not in {".json"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        _collect_dates(payload, dates)
    if not dates:
        raise ValueError("Không xác định được ngày nguồn để sinh dataset_version")
    return max(dates)


def _stable_evidence_payload(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceRole": evidence.get("sourceRole"),
        "url": evidence.get("url"),
        "articleUrl": evidence.get("articleUrl"),
        "attachmentUrl": evidence.get("attachmentUrl"),
        "attachmentSha256": evidence.get("attachmentSha256"),
        "decisionNumbers": evidence.get("decisionNumbers") or [],
        "publishedDate": evidence.get("publishedDate"),
        "effectiveDate": evidence.get("effectiveDate"),
        "classification": evidence.get("classification"),
        "repealContext": bool(evidence.get("repealContext")),
    }


def evidence_id(evidence: dict[str, Any]) -> str:
    raw = json.dumps(
        _stable_evidence_payload(evidence),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "ev_" + hashlib.sha1(raw).hexdigest()[:24]


def _official_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "dichvucong.gov.vn"
        or host.endswith(".dichvucong.gov.vn")
        or host.endswith(".gov.vn")
    )


def _infer_role(evidence: dict[str, Any]) -> str:
    role = str(evidence.get("sourceRole") or "").strip()
    if role in SOURCE_ROLES:
        return role
    urls = [
        str(evidence.get("url") or ""),
        str(evidence.get("articleUrl") or ""),
        str(evidence.get("attachmentUrl") or ""),
    ]
    if any("dichvucong.gov.vn" in value for value in urls):
        return "local_execution"
    return "local_legal_effect"


def normalize_evidence(evidence: dict[str, Any], default_role: str = "") -> dict[str, Any]:
    item = deepcopy(evidence)
    role = default_role or _infer_role(item)
    if role not in SOURCE_ROLES:
        raise ValueError(f"sourceRole không hợp lệ: {role}")
    item["sourceRole"] = role
    if not item.get("url"):
        item["url"] = item.get("articleUrl") or item.get("attachmentUrl") or ""
    item["evidenceId"] = evidence_id(item)
    return item


def _execution_evidence(url: str, classification: str, checked_at: str = "") -> dict[str, Any] | None:
    url = str(url or "").strip()
    if not url or not _official_url(url):
        return None
    item: dict[str, Any] = {
        "sourceRole": "local_execution",
        "url": url,
        "classification": classification,
        "repealContext": False,
    }
    if checked_at:
        item["verifiedAt"] = checked_at
    item["evidenceId"] = evidence_id(item)
    return item


def _merge_ref(field_sources: dict[str, list[str]], field: str, ids: list[str]) -> None:
    current = list(field_sources.get(field) or [])
    for item in ids:
        if item and item not in current:
            current.append(item)
    if current:
        field_sources[field] = current


VINHBAO_DVC_SCOPE = {
    "province": "019bad30-cd83-76ea-9f9a-bc6cebad4138",
    "ward": "019bad30-cd84-7750-aaa5-8100fc7ceef8",
    "agency": "019bad30-cd84-7750-aaa5-8100fc7ceef8",
    "departmentId": "019bad30-cd84-7750-aaa5-8100fc7ceef8",
    "searchType": "PROVINCE",
    "commune": "WARD",
    "provinceCode": "31",
    "wardCode": "11824",
    "showAdvanced": "false",
    "isProvince": "0",
    "isMinistry": "0",
}

def build_vinhbao_submission_url(code: str, formality_id: str = "") -> str:
    params = dict(VINHBAO_DVC_SCOPE)
    if formality_id:
        params["formalityId"] = formality_id
    else:
        params["keyword"] = code
    return "https://dichvucong.gov.vn/tim-kiem-thu-tuc-hanh-chinh?" + urlencode(params)

def upgrade_record_to_v4(row: dict[str, Any], as_of: str) -> dict[str, Any]:
    record = deepcopy(row)
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source in record.get("sourceEvidence") or []:
        if not isinstance(source, dict):
            continue
        item = normalize_evidence(source)
        if item["evidenceId"] not in seen:
            evidence.append(item)
            seen.add(item["evidenceId"])

    dvc_source = _execution_evidence(
        str(record.get("dvcMappingSource") or ""),
        "dvcqg_formality_mapping",
        str(record.get("dvcMappingScrapedAt") or ""),
    )
    if dvc_source and dvc_source["evidenceId"] not in seen:
        evidence.append(dvc_source)
        seen.add(dvc_source["evidenceId"])

    submission_source = _execution_evidence(
        str(record.get("nopHoSoUrl") or ""),
        "dvcqg_submission_link",
        str(record.get("submissionLinkCheckedAt") or ""),
    )
    if submission_source and submission_source["evidenceId"] not in seen:
        evidence.append(submission_source)
        seen.add(submission_source["evidenceId"])

    guide = record.get("huongDan")
    guide_evidence_ids: list[str] = []
    guide_source_refs: dict[str, str] = {}
    guide_source_roles: dict[str, str] = {}
    if isinstance(guide, dict):
        for source in guide.get("sources") or []:
            if not isinstance(source, dict):
                continue
            source_item = {
                "url": str(source.get("url") or "").strip(),
                "sourceRole": str(source.get("sourceRole") or "central_content_reference").strip(),
                "classification": source.get("classification") or "official_guidance",
                "publishedDate": source.get("publishedDate"),
                "effectiveDate": source.get("effectiveDate"),
                "repealContext": False,
            }
            if not source_item["url"]:
                continue
            item = normalize_evidence(source_item)
            if item["evidenceId"] not in seen:
                evidence.append(item)
                seen.add(item["evidenceId"])
            guide_evidence_ids.append(item["evidenceId"])
            source_id = str(source.get("id") or "").strip()
            if source_id:
                guide_source_refs[source_id] = item["evidenceId"]
                guide_source_roles[source_id] = item["sourceRole"]

    legal_ids = [
        item["evidenceId"]
        for item in evidence
        if item.get("sourceRole") == "local_legal_effect"
    ]
    execution_ids = [
        item["evidenceId"]
        for item in evidence
        if item.get("sourceRole") == "local_execution"
    ]

    active_dates = sorted(
        str(item.get("effectiveDate") or item.get("publishedDate") or "")
        for item in evidence
        if item.get("sourceRole") == "local_legal_effect"
        and not item.get("repealContext")
        and (item.get("effectiveDate") or item.get("publishedDate"))
    )
    effective_from = active_dates[-1] if active_dates else None

    record["lifecycle"] = {
        "status": "active",
        "asOf": str(record.get("sourceSnapshotDate") or as_of),
        "effectiveFrom": effective_from,
        "effectiveTo": None,
    }
    record["sourceEvidence"] = evidence

    field_sources: dict[str, list[str]] = deepcopy(record.get("fieldSources") or {})
    for field in ("ma", "ten", "linhVuc", "cap", "quyetDinh", "lifecycle.status", "lifecycle.effectiveFrom"):
        if field == "quyetDinh" and not record.get("quyetDinh"):
            continue
        if field == "lifecycle.effectiveFrom" and not effective_from:
            continue
        _merge_ref(field_sources, field, legal_ids)

    if record.get("formalityId"):
        _merge_ref(field_sources, "formalityId", execution_ids)
    if record.get("nopHoSoUrl"):
        _merge_ref(field_sources, "nopHoSoUrl", execution_ids)
        _merge_ref(field_sources, "nopHoSoScope", execution_ids)
        _merge_ref(field_sources, "submissionLinkStatus", execution_ids)

    if isinstance(guide, dict) and guide_evidence_ids:
        provenance = guide.get("fieldProvenance")
        provenance = provenance if isinstance(provenance, dict) else {}
        for field in ("quyTrinh", "thanhPhanHoSo", "bieuMau", "lePhi", "thoiHan", "coQuanThucHien", "ketQua"):
            if guide.get(field) in (None, "", [], {}):
                continue
            refs = provenance.get(field)
            ids = [
                guide_source_refs[ref]
                for ref in refs
                if isinstance(ref, str) and ref in guide_source_refs
            ] if isinstance(refs, list) else []
            _merge_ref(field_sources, f"huongDan.{field}", ids or guide_evidence_ids)
        if guide.get("dvctt"):
            refs = provenance.get("dvctt")
            ids = [
                guide_source_refs[ref]
                for ref in refs
                if (
                    isinstance(ref, str)
                    and ref in guide_source_refs
                    and guide_source_roles.get(ref) == "local_execution"
                )
            ] if isinstance(refs, list) else []
            _merge_ref(field_sources, "huongDan.dvctt", ids or execution_ids)
        if guide.get("submissionUrl"):
            refs = provenance.get("submissionUrl")
            ids = [
                guide_source_refs[ref]
                for ref in refs
                if (
                    isinstance(ref, str)
                    and ref in guide_source_refs
                    and guide_source_roles.get(ref) == "local_execution"
                )
            ] if isinstance(refs, list) else []
            _merge_ref(field_sources, "huongDan.submissionUrl", ids or execution_ids)

    record["fieldSources"] = field_sources
    return record


def upgrade_payload_to_v4(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    result = deepcopy(payload)
    existing_version = str(result.get("dataset_version") or "")
    dataset_date = derive_dataset_date(root, existing_version)
    as_of = str(result.get("sourceSnapshotDate") or dataset_date)
    result["version"] = 4
    result["dataset_version"] = dataset_date.replace("-", ".")
    result["source_commit"] = compute_source_commit(root)
    result["source_commit_kind"] = SOURCE_COMMIT_KIND
    result["updatedAt"] = dataset_date
    result["thuTuc"] = [
        upgrade_record_to_v4(row, as_of)
        for row in result.get("thuTuc") or []
        if isinstance(row, dict)
    ]
    return result
