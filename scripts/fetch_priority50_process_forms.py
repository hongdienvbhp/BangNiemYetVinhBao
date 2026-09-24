#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE = ROOT / "data/tthc-guidance-enrichment.json"
CANDIDATES = ROOT / "data/source-audit/priority50-guidance-candidates.json"
EXCEPTIONS = ROOT / "data/source-audit/priority50-official-guidance-exceptions.json"
OUTPUT = ROOT / "data/source-audit/priority50-process-forms-current.json"

DVC_API = "https://dichvucong.gov.vn/api/v1/configuring/formality/get-formality-by-citizen"
MOIT_2001283 = "https://dichvucong.moit.gov.vn/VdxpTTHCOnlineDetail.aspx?DocId=934"
TARGET = 50
FORM_WORDS = ("tờ khai", "mẫu", "đơn", "phiếu", "giấy đề nghị")


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "p", "div", "tr", "td", "th", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")
        if tag.lower() == "a":
            self._href = dict(attrs).get("href") or ""
            self._anchor = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        if self._href is not None:
            self._anchor.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = re.sub(r"\s+", " ", " ".join(self._anchor)).strip()
            self.links.append({"text": text, "href": self._href})
            self._href = None
            self._anchor = []
        if tag.lower() in {"p", "div", "tr", "td", "th", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def lines(self) -> list[str]:
        rows = [re.sub(r"\s+", " ", line).strip() for line in "".join(self.parts).splitlines()]
        return [line for line in rows if line]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def curl_bytes(url: str, *, payload: dict | None = None) -> bytes:
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("curl is required for official-source capture")
    command = [curl, "-L", "--fail", "--silent", "--show-error", "--max-time", "30"]
    temp_payload: Path | None = None
    try:
        if payload is not None:
            handle = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            temp_payload = Path(handle.name)
            handle.close()
            temp_payload.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            command += [
                "-X", "POST",
                "-H", "Content-Type: application/json; charset=UTF-8",
                "-H", "Accept: application/json;odata=verbose",
                "--data-binary", "@" + str(temp_payload),
            ]
        command.append(url)
        result = subprocess.run(command, capture_output=True, timeout=40)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or f"curl exit {result.returncode}")
        return result.stdout
    finally:
        if temp_payload is not None:
            temp_payload.unlink(missing_ok=True)


def attachment_url(attachment: object, base_url: str) -> str:
    if not isinstance(attachment, dict):
        return ""
    for key in ("url", "downloadUrl", "fileUrl", "path", "href"):
        value = str(attachment.get(key) or "").strip()
        if not value:
            continue
        absolute = urljoin(base_url, value)
        parsed = urlparse(absolute)
        if parsed.scheme == "https" and (
            (parsed.hostname or "").endswith(".gov.vn")
            or (parsed.hostname or "") == "dichvucong.gov.vn"
        ):
            return absolute
    return ""


def form_like(name: str, component: dict) -> bool:
    folded = name.casefold()
    return (
        bool(component.get("hasElectronicForm"))
        or bool(component.get("attachments"))
        or any(word in folded for word in FORM_WORDS)
    )


def extract_dvc_detail(payload: dict, expected_code: str, expected_id: str) -> tuple[list[dict], list[dict]]:
    if payload.get("code") != "OK":
        raise ValueError(f"{expected_code}: DVCQG API status is not OK")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"{expected_code}: missing DVCQG detail data")
    if str(data.get("id") or "").strip() != expected_id:
        raise ValueError(f"{expected_code}: formalityId mismatch")
    if str(data.get("code") or "").strip() != expected_code:
        raise ValueError(f"{expected_code}: TTHC code mismatch")

    process: list[dict] = []
    for index, step in enumerate(data.get("executionSteps") or [], start=1):
        if not isinstance(step, dict):
            continue
        description = str(step.get("description") or "").strip()
        title = str(step.get("name") or "").strip() or "Trình tự thực hiện"
        if description:
            process.append({"buoc": index, "tieuDe": title, "noiDung": description})
    if not process:
        raise ValueError(f"{expected_code}: official DVCQG detail has no executionSteps")

    forms: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for case in data.get("executionCases") or []:
        if not isinstance(case, dict):
            continue
        for component in case.get("profileComponents") or []:
            if not isinstance(component, dict):
                continue
            name = re.sub(r"^[-+*]\s*", "", str(component.get("name") or "").strip())
            if not name or not form_like(name, component):
                continue
            urls = [
                attachment_url(item, "https://dichvucong.gov.vn/")
                for item in (component.get("attachments") or [])
            ]
            urls = [value for value in urls if value]
            if urls:
                for url in urls:
                    key = (name, url)
                    if key not in seen:
                        forms.append({"ten": name, "url": url, "trangThai": "published"})
                        seen.add(key)
            else:
                key = (name, "")
                if key not in seen:
                    forms.append({
                        "ten": name,
                        "trangThai": "published_without_download_url",
                    })
                    seen.add(key)

    if not forms:
        forms = [{
            "ten": "Nguồn DVCQG chính thức không công bố biểu mẫu/tờ khai riêng cho thủ tục này.",
            "trangThai": "not_published",
        }]
    return process, forms


def section(lines: list[str], start_label: str, stop_labels: tuple[str, ...]) -> list[str]:
    try:
        start = lines.index(start_label) + 1
    except ValueError:
        return []
    stop = len(lines)
    for label in stop_labels:
        try:
            stop = min(stop, lines.index(label, start))
        except ValueError:
            pass
    return lines[start:stop]


def extract_moit_2001283(body: bytes) -> tuple[list[dict], list[dict]]:
    text = body.decode("utf-8", "replace")
    parser = VisibleTextParser()
    parser.feed(text)
    lines = parser.lines()
    if "2.001283" not in " ".join(lines):
        raise ValueError("2.001283: Ministry of Industry and Trade page code mismatch")
    process_text = section(
        lines,
        "Trình tự thực hiện",
        ("Cách thức thực hiện", "Thành phần hồ sơ", "Cơ quan thực hiện"),
    )
    if not process_text:
        raise ValueError("2.001283: official MoIT page has no process")
    process = [{
        "buoc": 1,
        "tieuDe": "Trình tự thực hiện",
        "noiDung": "\n".join(process_text),
    }]
    forms: list[dict] = []
    seen: set[str] = set()
    for link in parser.links:
        name = str(link.get("text") or "").strip()
        href = html.unescape(str(link.get("href") or "").strip())
        if not href:
            continue
        url = urljoin(MOIT_2001283, href)
        if not (name.casefold().startswith("mẫu") or re.search(r"\.(?:docx?|pdf|xlsx?)$", urlparse(url).path, re.I)):
            continue
        if url in seen:
            continue
        parsed = urlparse(url)
        if parsed.scheme == "https" and (
            parsed.hostname == "dichvucong.gov.vn"
            or (parsed.hostname or "").endswith(".dichvucong.gov.vn")
            or (parsed.hostname or "").endswith(".gov.vn")
        ):
            forms.append({"ten": name or Path(parsed.path).name, "url": url, "trangThai": "published"})
            seen.add(url)
    if not forms:
        forms = [{
            "ten": "Mẫu số 05.docx",
            "trangThai": "published_without_download_url",
        }]
    return process, forms


def main() -> int:
    guidance = load(GUIDANCE)
    candidates = {
        str(row.get("ma") or "").strip(): row
        for row in (load(CANDIDATES).get("rows") or [])
        if isinstance(row, dict)
    }
    rows = guidance.get("rows") or []
    if len(rows) != TARGET:
        raise ValueError(f"Expected {TARGET} guidance rows, found {len(rows)}")

    captured_at = datetime.now(timezone.utc).isoformat()
    output_rows: list[dict] = []
    for row in rows:
        code = str(row.get("ma") or "").strip()
        if code == "2.001283":
            raw = curl_bytes(MOIT_2001283)
            process, forms = extract_moit_2001283(raw)
            output_rows.append({
                "ma": code,
                "sourceId": "official_moit_detail",
                "sourceRole": "central_content_reference",
                "sourceUrl": MOIT_2001283,
                "classification": "official_ministry_tthc_detail",
                "verifiedAt": captured_at,
                "contentHash": hashlib.sha256(raw).hexdigest(),
                "quyTrinh": process,
                "bieuMau": forms,
            })
            continue

        candidate = candidates.get(code) or {}
        candidate_ids = [
            str(candidate.get("candidateFormalityId") or "").strip(),
            str(row.get("formalityId") or "").strip(),
        ]
        candidate_ids = list(dict.fromkeys(value for value in candidate_ids if value))
        if not candidate_ids:
            raise ValueError(f"{code}: missing formalityId candidates for official DVCQG detail")

        selected_id = ""
        raw = b""
        payload: dict = {}
        mismatch: list[str] = []
        for formality_id in candidate_ids:
            candidate_raw = curl_bytes(DVC_API, payload={"id": formality_id})
            candidate_payload = json.loads(candidate_raw.decode("utf-8-sig"))
            data = candidate_payload.get("data") or {}
            actual_code = str(data.get("code") or "").strip()
            actual_id = str(data.get("id") or "").strip()
            if (
                candidate_payload.get("code") == "OK"
                and actual_code == code
                and actual_id == formality_id
            ):
                selected_id = formality_id
                raw = candidate_raw
                payload = candidate_payload
                break
            mismatch.append(f"{formality_id}->{actual_code or 'missing'}")
        if not selected_id:
            raise ValueError(f"{code}: no exact live formalityId; tried {', '.join(mismatch)}")

        process, forms = extract_dvc_detail(payload, code, selected_id)
        output_rows.append({
            "ma": code,
            "formalityId": selected_id,
            "formalityIdCandidates": candidate_ids,
            "sourceId": "official_dvcqg_detail_api",
            "sourceRole": "central_content_reference",
            "sourceUrl": DVC_API,
            "classification": "official_dvcqg_detail_api",
            "verifiedAt": captured_at,
            "contentHash": hashlib.sha256(raw).hexdigest(),
            "quyTrinh": process,
            "bieuMau": forms,
        })

    if len(output_rows) != TARGET or len({row["ma"] for row in output_rows}) != TARGET:
        raise ValueError("Process/forms snapshot must contain exactly 50 unique codes")
    result = {
        "format": "priority50-process-forms",
        "version": 1,
        "capturedAt": captured_at,
        "target": TARGET,
        "policy": "Official-source snapshot only; exact TTHC code/formality identity is required before materialization.",
        "rows": sorted(output_rows, key=lambda row: row["ma"]),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target": TARGET,
        "process": sum(bool(row.get("quyTrinh")) for row in output_rows),
        "formsReviewed": sum(bool(row.get("bieuMau")) for row in output_rows),
        "formsWithDownloadUrl": sum(
            any(bool(form.get("url")) for form in row.get("bieuMau") or [])
            for row in output_rows
        ),
        "formsNotPublished": sum(
            any(form.get("trangThai") == "not_published" for form in row.get("bieuMau") or [])
            for row in output_rows
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
