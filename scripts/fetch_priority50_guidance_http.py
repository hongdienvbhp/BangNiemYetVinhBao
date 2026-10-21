#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/thu-tuc.json"
OUTPUT = ROOT / "data/source-audit/priority50-guidance-raw-current.json"
TARGET = 50


def norm(value: object) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def fold(value: object) -> str:
    text = unicodedata.normalize("NFD", norm(value))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").lower()


class VisibleHTML(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg"}
    BLOCK = {
        "p", "div", "section", "article", "header", "footer", "main", "aside",
        "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.text_parts: list[str] = []
        self.tables: list[dict] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCK:
            self.text_parts.append("\n")
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"td", "th"} and self.cell_parts is not None and self.row is not None:
            self.row.append(norm(" ".join(self.cell_parts)))
            self.cell_parts = None
        elif tag == "tr" and self.row is not None and self.table is not None:
            if any(self.row):
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            if self.table:
                self.tables.append({"rows": self.table})
            self.table = None
        if tag in self.BLOCK:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = norm(data)
        if not value:
            return
        self.text_parts.append(value)
        self.text_parts.append(" ")
        if self.cell_parts is not None:
            self.cell_parts.append(value)

    def payload(self) -> tuple[str, list[dict]]:
        raw = "".join(self.text_parts)
        lines = [norm(line) for line in raw.splitlines()]
        body = "\n".join(line for line in lines if line)
        return body, self.tables


def fetch(url: str) -> tuple[str, str]:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BangNiemYetVinhBao/1.0; +https://github.com/hongdienvbhp/BangNiemYetVinhBao)",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.5",
        },
    )
    try:
        with urlopen(req, timeout=8) as response:
            data = response.read().decode("utf-8", errors="replace")
            return response.geturl(), data
    except HTTPError as exc:
        return url, f"__FETCH_ERROR__:HTTP_{exc.code}"
    except (URLError, TimeoutError) as exc:
        return url, f"__FETCH_ERROR__:{type(exc).__name__}"


def candidate_urls(code: str) -> list[str]:
    q = quote(code, safe="")
    return [
        f"https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-hanh-chinh.html?ma_thu_tuc={q}",
        f"https://dichvucong.gov.vn/p/home/dvc-chi-tiet-thu-tuc-dung-chung.html?ma_thu_tuc={q}",
    ]


def fetch_record(index: int, row: dict) -> dict:
    code = norm(row.get("ma"))
    expected = norm(row.get("ten"))
    chosen_url = ""
    body = ""
    tables: list[dict] = []
    status = "DETAIL_IDENTITY_UNRESOLVED"
    errors: list[str] = []

    for url in candidate_urls(code):
        rendered, html = fetch(url)
        if html.startswith("__FETCH_ERROR__:"):
            errors.append(html)
            continue
        parser = VisibleHTML()
        parser.feed(html)
        parsed_body, parsed_tables = parser.payload()
        folded = fold(parsed_body)
        if fold(code) in folded or (expected and fold(expected) in folded):
            chosen_url = rendered
            body = parsed_body
            tables = parsed_tables
            status = "DETAIL_CAPTURED"
            break
        if not body:
            chosen_url = rendered
            body = parsed_body
            tables = parsed_tables

    if status != "DETAIL_CAPTURED" and errors and not body:
        status = "HTTP_FETCH_FAILED"

    return {
        "ordinal": index,
        "code": code,
        "expectedName": expected,
        "field": row.get("linhVuc") or "",
        "formalityId": row.get("formalityId") or "",
        "localExecutionUrl": row.get("nopHoSoUrl") or "",
        "detailUrl": chosen_url,
        "renderedUrl": chosen_url,
        "pageTitle": "",
        "status": status,
        "bodyText": body,
        "tables": tables,
        "fetchErrors": errors,
    }


def main() -> int:
    master = json.loads(MASTER.read_text(encoding="utf-8-sig"))
    targets = [
        row for row in master.get("thuTuc") or []
        if isinstance(row, dict) and row.get("priority51") is True
    ]
    if len(targets) != TARGET:
        raise ValueError(f"Expected {TARGET} active priority procedures, found {len(targets)}")

    items: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_record, index, row): index
            for index, row in enumerate(targets, start=1)
        }
        for future in as_completed(futures):
            item = future.result()
            items.append(item)
            print(json.dumps({
                "ordinal": item["ordinal"],
                "code": item["code"],
                "status": item["status"],
                "body_chars": len(item["bodyText"]),
                "tables": len(item["tables"]),
            }, ensure_ascii=False), flush=True)
    items.sort(key=lambda item: item["ordinal"])

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "format": "DVCQG_PRIORITY50_GUIDANCE_RAW",
        "version": 1,
        "capturedAt": now,
        "source": "https://dichvucong.gov.vn/",
        "securityScope": "Public official HTML GET only; no login, credentials, cookies, citizen dossiers, submissions, or write-back.",
        "targetCount": TARGET,
        "transport": "https_direct_by_tthc_code",
        "totals": {
            "detailCaptured": sum(x["status"] == "DETAIL_CAPTURED" for x in items),
            "unresolved": sum(x["status"] == "DETAIL_IDENTITY_UNRESOLVED" for x in items),
            "fetchFailed": sum(x["status"] == "HTTP_FETCH_FAILED" for x in items),
        },
        "items": items,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["totals"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
