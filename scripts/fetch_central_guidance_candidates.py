#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from scripts.central_source_registry import load_json, validate_registry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data/source-audit/central-source-registry.json"
PLAN = ROOT / "data/source-audit/central-guidance-plan.json"
OUTPUT = ROOT / "data/source-audit/central-guidance-candidates.json"
USER_AGENT = "BangNiemYetVinhBao-Central-Guidance/1.0"

HEADINGS = [
    "Trình tự thực hiện",
    "Cách thức thực hiện",
    "Thành phần hồ sơ",
    "Đối tượng thực hiện",
    "Cơ quan thực hiện",
    "Cơ quan có thẩm quyền",
    "Địa chỉ tiếp nhận hồ sơ",
    "Cơ quan được ủy quyền",
    "Cơ quan phối hợp",
    "Kết quả thực hiện",
    "Căn cứ pháp lý",
    "Yêu cầu hoặc điều kiện thực hiện",
]
DOC_HEADERS = {"Tên giấy tờ", "Số bản chính", "Số bản sao"}


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._href = ""
        self._anchor: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "li", "p", "tr", "td", "th", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")
        if tag.lower() == "a":
            attrs_map = {key.lower(): (value or "") for key, value in attrs}
            self._href = attrs_map.get("href", "")
            self._anchor = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)
        if self._href:
            self._anchor.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            text = re.sub(r"\s+", " ", " ".join(self._anchor)).strip()
            self.links.append({"href": self._href, "text": text})
            self._href = ""
            self._anchor = []
        if tag.lower() in {"li", "p", "tr", "td", "th", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def lines(self) -> list[str]:
        lines = [re.sub(r"\s+", " ", item).strip() for item in "".join(self.parts).splitlines()]
        return [item for item in lines if item]


def fetch(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    with urlopen(request, timeout=40) as response:
        return response.read(), response.headers.get("Content-Type", "")


def decode(body: bytes, content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    charset = match.group(1) if match else "utf-8"
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def section(lines: list[str], heading: str) -> list[str]:
    try:
        start = lines.index(heading) + 1
    except ValueError:
        return []
    stop = len(lines)
    for candidate in HEADINGS:
        if candidate == heading:
            continue
        try:
            index = lines.index(candidate, start)
        except ValueError:
            continue
        stop = min(stop, index)
    return lines[start:stop]


def parse_documents(lines: list[str]) -> list[dict]:
    raw = [item for item in section(lines, "Thành phần hồ sơ") if item not in DOC_HEADERS]
    documents: list[dict] = []
    index = 0
    while index < len(raw):
        name = raw[index].strip()
        if index + 2 < len(raw) and re.fullmatch(r"\d+", raw[index + 1]) and re.fullmatch(r"\d+", raw[index + 2]):
            documents.append({
                "ten": name,
                "soLuong": f"Bản chính: {raw[index + 1]}; Bản sao: {raw[index + 2]}",
            })
            index += 3
            continue
        if name and not re.fullmatch(r"\d+", name):
            documents.append({"ten": name})
        index += 1
    return documents


def parse_forms(parser: VisibleTextParser, page_url: str) -> list[dict]:
    forms: list[dict] = []
    seen: set[str] = set()
    for link in parser.links:
        href = html.unescape(link.get("href") or "").strip()
        text = link.get("text") or ""
        if not href:
            continue
        absolute = urljoin(page_url, href)
        path = urlparse(absolute).path.lower()
        if not re.search(r"\.(?:docx?|pdf|xlsx?)$", path) and "mẫu" not in text.lower() and "mau" not in text.lower():
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        forms.append({"ten": text or Path(path).name, "url": absolute, "nguonUrl": page_url})
    return forms


def page_code(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if line in {"Mã thủ tục", "Mã TTHC", "Mã số"} and index + 1 < len(lines):
            candidate = lines[index + 1].strip()
            if re.fullmatch(r"\d{1,2}\.\d{3,6}", candidate):
                return candidate
    joined = " ".join(lines[:250])
    match = re.search(r"\b\d{1,2}\.\d{3,6}\b", joined)
    return match.group(0) if match else ""


def parse_direct_page(code: str, source: dict, url: str) -> dict:
    body, content_type = fetch(url)
    text = decode(body, content_type)
    parser = VisibleTextParser()
    parser.feed(text)
    lines = parser.lines()
    detected_code = page_code(lines)
    process = section(lines, "Trình tự thực hiện")
    method = section(lines, "Cách thức thực hiện")
    authority = section(lines, "Cơ quan thực hiện")
    result = section(lines, "Kết quả thực hiện")
    docs = parse_documents(lines)
    forms = parse_forms(parser, url)
    status = "candidate"
    issues: list[str] = []
    if detected_code != code:
        issues.append(f"code_mismatch:{detected_code or 'missing'}")
    if not process:
        issues.append("missing_process")
    if not docs:
        issues.append("missing_documents")
    if not authority:
        issues.append("missing_authority")
    if issues:
        status = "needs_review"
    return {
        "ma": code,
        "sourceId": source["id"],
        "sourceRole": "central_content_reference",
        "sourceUrl": url,
        "authority": source["authority"],
        "adapter": source["adapter"],
        "httpEvidence": {
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "contentType": content_type,
            "detectedCode": detected_code,
        },
        "candidateStatus": status,
        "issues": issues,
        "extracted": {
            "quyTrinh": [{"buoc": 1, "tieuDe": "Trình tự thực hiện", "noiDung": "\n".join(process)}] if process else [],
            "cachThucText": "\n".join(method),
            "thanhPhanHoSo": docs,
            "bieuMau": forms,
            "coQuanThucHien": "\n".join(authority),
            "ketQuaText": "\n".join(result),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", default="moj-tthc")
    args = parser.parse_args()

    registry = load_json(REGISTRY)
    errors = validate_registry(registry)
    if errors:
        raise SystemExit("\n".join(errors))
    plan = load_json(PLAN)
    source = next((item for item in registry["sources"] if item["id"] == args.source_id), None)
    if not source:
        raise SystemExit(f"Unknown source id: {args.source_id}")
    if source["status"] not in {"ready", "ready_search"}:
        raise SystemExit(f"Source {args.source_id} is not ready")
    if source["adapter"] != "direct_code_detail":
        raise SystemExit(f"Automated fetch currently supports direct_code_detail only; {args.source_id} remains planned/search-reviewed")

    results = []
    for procedure in plan.get("procedures") or []:
        match = next((item for item in procedure.get("sources") or [] if item["sourceId"] == args.source_id), None)
        if not match:
            continue
        results.append(parse_direct_page(procedure["ma"], source, match["candidateUrl"]))

    payload = {
        "format": "central-guidance-candidates",
        "version": 1,
        "sourceId": args.source_id,
        "candidateOnly": True,
        "autoPublish": False,
        "summary": {
            "procedures": len(results),
            "candidate": sum(1 for item in results if item["candidateStatus"] == "candidate"),
            "needsReview": sum(1 for item in results if item["candidateStatus"] == "needs_review"),
            "withProcess": sum(1 for item in results if item["extracted"]["quyTrinh"]),
            "withDocuments": sum(1 for item in results if item["extracted"]["thanhPhanHoSo"]),
            "withForms": sum(1 for item in results if item["extracted"]["bieuMau"]),
            "withAuthority": sum(1 for item in results if item["extracted"]["coQuanThucHien"]),
        },
        "procedures": results,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
