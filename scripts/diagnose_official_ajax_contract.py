#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only diagnostics for official TTHC AJAX pagination request contracts.

This probe does not write repository data or submit administrative forms. It
fetches only configured official listing pages and their declared LoadArticle
read endpoint, then compares form-encoded and JSON request bodies.
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from scripts import update_official_sources as scanner

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data/source-audit/official-source-config.json"
TARGET_IDS = {
    "haiphong-city-official-tthc",
    "vinhbao-official-tthc",
    "haiphong-dept-agri-env",
}
TIMEOUT_SECONDS = 12


def request(opener, url: str, *, data: bytes | None = None, headers: dict | None = None):
    request_headers = {
        "User-Agent": scanner.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    }
    request_headers.update(headers or {})
    req = Request(url, data=data, headers=request_headers, method="POST" if data is not None else "GET")
    try:
        with opener.open(req, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.headers.get("Content-Type", ""), response.read()
    except HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", ""), exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        return 0, "", str(exc).encode("utf-8", errors="replace")


def find_ajax_script(page_html: str) -> str:
    blocks = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", page_html, re.I | re.S)
    matches = [block for block in blocks if "ArticleInMenuPagination.aspx/LoadArticle" in block]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one AJAX script; found {len(matches)}")
    return matches[0]


def response_summary(status: int, content_type: str, body: bytes) -> dict:
    text = body.decode("utf-8", errors="replace")
    embedded_strings = [text]
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            embedded_strings += [v for v in payload.values() if isinstance(v, str)]
        elif isinstance(payload, str):
            embedded_strings.append(payload)
    except json.JSONDecodeError:
        pass
    html_text = max(embedded_strings, key=len) if embedded_strings else text
    return {
        "status": status,
        "contentType": content_type,
        "bodyBytes": len(body),
        "bodySha256": hashlib.sha256(body).hexdigest(),
        "isJson": "json" in (content_type or "").lower() or text.lstrip().startswith(("{", "[")),
        "hasArticleList": "ArticleList" in html_text,
        "hrefCount": len(re.findall(r"\bhref\s*=", html_text, re.I)),
        "tthcDecisionSignalCount": len(re.findall(r"quyet[-_ ]dinh|thu[-_ ]tuc[-_ ]hanh[-_ ]chinh", html_text, re.I)),
        "errorPreview": text[:180] if status == 0 or status >= 400 else "",
    }


def run_source(source: dict) -> list[dict]:
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    source_url = str(source["url"])
    result_rows: list[dict] = []
    get_status, get_type, get_body = request(opener, source_url)
    record = {
        "sourceId": source["id"],
        "sourceUrl": source_url,
        "kind": "initial_get",
        **response_summary(get_status, get_type, get_body),
    }
    result_rows.append(record)
    if get_status < 200 or get_status >= 400 or not get_body:
        result_rows.append({"sourceId": source["id"], "kind": "skipped", "reason": "initial GET failed or empty"})
        return result_rows

    page_html = scanner.decode_html(get_body, get_type)
    try:
        ajax = scanner.extract_ajax_pagination_config(page_html, source_url)
        ajax_script = find_ajax_script(page_html)
    except Exception as exc:
        result_rows.append({"sourceId": source["id"], "kind": "config_error", "error": str(exc)})
        return result_rows
    if not ajax:
        result_rows.append({"sourceId": source["id"], "kind": "skipped", "reason": "no declared AJAX pagination"})
        return result_rows

    type_match = re.search(r"\btype\s*:\s*(['\"])(.*?)\1", ajax_script, re.I | re.S)
    method_match = re.search(r"\bmethod\s*:\s*(['\"])(.*?)\1", ajax_script, re.I | re.S)
    content_match = re.search(r"\bcontentType\s*:\s*(['\"])(.*?)\1", ajax_script, re.I | re.S)
    stringify_match = re.search(r"\bdata\s*:\s*(?:JSON\.stringify|jQuery\.toJSON|\$\.toJSON)\s*\(", ajax_script, re.I)
    result_rows.append({
        "sourceId": source["id"],
        "kind": "js_contract",
        "endpoint": ajax["endpoint"],
        "declaredMaxPage": ajax["maxPage"],
        "declaredPageSize": ajax["pageSize"],
        "type": type_match.group(2) if type_match else (method_match.group(2) if method_match else "unspecified"),
        "contentType": content_match.group(2) if content_match else "jQuery-default-or-unspecified",
        "dataUsesJsonSerializer": bool(stringify_match),
    })

    pages = list(dict.fromkeys([1, min(2, ajax["maxPage"]), ajax["maxPage"]]))
    for page_number in pages:
        data = dict(ajax["formData"])
        data["page"] = str(page_number)
        variants = [
            ("form_urlencoded", urlencode(data).encode("utf-8"),
             "application/x-www-form-urlencoded; charset=UTF-8"),
            ("json", json.dumps(data, ensure_ascii=False).encode("utf-8"),
             "application/json; charset=UTF-8"),
        ]
        for variant, body, content_type in variants:
            headers = {
                "Referer": source_url,
                "Origin": f"{urlparse(source_url).scheme}://{urlparse(source_url).netloc}",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": content_type,
            }
            status, response_type, response_body = request(opener, ajax["endpoint"], data=body, headers=headers)
            result_rows.append({
                "sourceId": source["id"],
                "kind": "endpoint_probe",
                "page": page_number,
                "variant": variant,
                "requestBytes": len(body),
                **response_summary(status, response_type, response_body),
            })
    return result_rows


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    targets = [s for s in config.get("listingSources", []) if s.get("id") in TARGET_IDS]
    output: dict = {
        "purpose": "read-only AJAX transport diagnostics; no repository/data writes",
        "selectedSourceCount": len(targets),
        "results": [],
    }
    for source in targets:
        try:
            output["results"].extend(run_source(source))
        except Exception as exc:
            output["results"].append({"sourceId": source.get("id", ""), "kind": "probe_error", "error": str(exc)})
    output["resultCount"] = len(output["results"])
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if len(targets) == len(TARGET_IDS) else 2


if __name__ == "__main__":
    sys.exit(main())
