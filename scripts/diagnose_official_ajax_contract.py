#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only diagnostics for official TTHC AJAX pagination request contracts.

This probe does not write repository data or submit administrative forms. It
fetches only configured official listing pages and their declared LoadArticle
read endpoint, then compares form-encoded and JSON request bodies.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.cookiejar
import importlib.util
import json
import re
import socket
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
SCANNER_PATH = ROOT / "scripts/update_official_sources.py"
_spec = importlib.util.spec_from_file_location("update_official_sources", SCANNER_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"unable to load source scanner: {SCANNER_PATH}")
scanner = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = scanner
_spec.loader.exec_module(scanner)

CONFIG_PATH = ROOT / "data/source-audit/official-source-config.json"
TARGET_ORDER = [
    "vinhbao-official-tthc",
    "haiphong-city-official-tthc",
    "haiphong-dept-culture-tourism",
    "haiphong-dept-agri-env",
    "haiphong-dept-construction-commune",
    "haiphong-local-nhi-chieu",
    "haiphong-local-an-duong",
    "haiphong-local-ngo-quyen",
    "haiphong-local-gia-vien",
    "haiphong-local-bach-long-vy",
    "haiphong-local-cat-hai",
]
TARGET_IDS = set(TARGET_ORDER)
TIMEOUT_SECONDS = 4
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_OUTPUT = Path("/tmp/official-source-ajax-contract.json")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def request(opener, url: str, *, data: bytes | None = None, headers: dict | None = None) -> dict:
    started_utc = utc_now()
    started = time.monotonic()
    request_headers = {
        "User-Agent": scanner.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    }
    request_headers.update(headers or {})
    req = Request(
        url,
        data=data,
        headers=request_headers,
        method="POST" if data is not None else "GET",
    )
    status = 0
    content_type = ""
    body = b""
    effective_url = None
    error_code = None
    error = None
    try:
        with opener.open(req, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            effective_url = response.geturl()
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                body = body[:MAX_RESPONSE_BYTES]
                error_code = "RESPONSE_TRUNCATED"
                error = f"response exceeded {MAX_RESPONSE_BYTES} byte safety cap"
    except HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        effective_url = exc.geturl()
        try:
            body = exc.read(MAX_RESPONSE_BYTES + 1)
        except Exception:
            body = b""
        error_code = f"HTTP_{exc.code}"
        error = f"HTTP {exc.code}: {exc.reason}"
    except URLError as exc:
        reason = exc.reason
        reason_text = str(reason)
        if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in reason_text.lower():
            error_code = "TIMEOUT"
        elif isinstance(reason, socket.gaierror) or "name resolution" in reason_text.lower() or "name or service not known" in reason_text.lower():
            error_code = "DNS_ERROR"
        else:
            error_code = "TRANSPORT_ERROR"
        error = f"{type(exc).__name__}: {exc}"
    except (TimeoutError, socket.timeout) as exc:
        error_code = "TIMEOUT"
        error = f"{type(exc).__name__}: {exc}"
    except OSError as exc:
        error_code = "OS_ERROR"
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        error_code = "REQUEST_ERROR"
        error = f"{type(exc).__name__}: {exc}"

    ended_utc = utc_now()
    return {
        "status": status,
        "contentType": content_type,
        "body": body,
        "urlEffective": effective_url,
        "errorCode": error_code,
        "error": error,
        "attemptStartedUtc": started_utc,
        "attemptEndedUtc": ended_utc,
        "elapsedMs": round((time.monotonic() - started) * 1000, 2),
        "timeoutSeconds": TIMEOUT_SECONDS,
    }
def find_ajax_script(page_html: str) -> str:
    blocks = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", page_html, re.I | re.S)
    matches = [block for block in blocks if "ArticleInMenuPagination.aspx/LoadArticle" in block]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one AJAX script; found {len(matches)}")
    return matches[0]


def response_summary(response: dict) -> dict:
    status = int(response.get("status") or 0)
    content_type = str(response.get("contentType") or "")
    body = response.get("body") or b""
    text = body.decode("utf-8", errors="replace")
    embedded_strings = [text]
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            embedded_strings += [value for value in payload.values() if isinstance(value, str)]
        elif isinstance(payload, str):
            embedded_strings.append(payload)
    except json.JSONDecodeError:
        pass
    html_text = max(embedded_strings, key=len) if embedded_strings else text
    return {
        "httpStatus": status,
        "contentType": content_type or None,
        "bodyBytes": len(body),
        "bodySha256": hashlib.sha256(body).hexdigest() if status else None,
        "urlEffective": response.get("urlEffective"),
        "errorCode": response.get("errorCode"),
        "error": response.get("error"),
        "attemptStartedUtc": response.get("attemptStartedUtc"),
        "attemptEndedUtc": response.get("attemptEndedUtc"),
        "elapsedMs": response.get("elapsedMs"),
        "timeoutSeconds": response.get("timeoutSeconds", TIMEOUT_SECONDS),
        "isJson": "json" in content_type.lower() or text.lstrip().startswith(("{", "[")),
        "hasArticleList": "ArticleList" in html_text,
        "hrefCount": len(re.findall(r"\bhref\s*=", html_text, re.I)),
        "tthcDecisionSignalCount": len(re.findall(r"quyet[-_ ]dinh|thu[-_ ]tuc[-_ ]hanh[-_ ]chinh", html_text, re.I)),
        "errorPreview": text[:180] if status >= 400 else "",
    }
def run_source(source: dict) -> list[dict]:
    opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    source_url = str(source["url"])
    source_id = str(source["id"])
    result_rows: list[dict] = []
    initial = request(opener, source_url)
    result_rows.append({
        "sourceId": source_id,
        "sourceUrl": source_url,
        "kind": "initial_get",
        "method": "GET",
        "urlRequested": source_url,
        "requestBodySha256": None,
        **response_summary(initial),
    })
    if initial["status"] < 200 or initial["status"] >= 400 or not initial["body"]:
        result_rows.append({
            "sourceId": source_id,
            "sourceUrl": source_url,
            "kind": "skipped",
            "urlRequested": source_url,
            "reason": "initial GET failed or returned an empty body; pagination contract not inspected",
            "errorCode": initial.get("errorCode") or (f"HTTP_{initial['status']}" if initial["status"] >= 400 else "EMPTY_INITIAL_BODY"),
        })
        return result_rows

    page_html = scanner.decode_html(initial["body"], initial["contentType"])
    try:
        ajax = scanner.extract_ajax_pagination_config(page_html, source_url)
        ajax_script = find_ajax_script(page_html)
    except Exception as exc:
        result_rows.append({
            "sourceId": source_id,
            "sourceUrl": source_url,
            "kind": "config_error",
            "urlRequested": source_url,
            "errorCode": "AJAX_CONFIG_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        })
        return result_rows
    if not ajax:
        result_rows.append({
            "sourceId": source_id,
            "sourceUrl": source_url,
            "kind": "skipped",
            "urlRequested": source_url,
            "reason": "no declared AJAX pagination contract found in source HTML",
            "errorCode": "NO_AJAX_CONTRACT",
        })
        return result_rows

    type_match = re.search(r"\btype\s*:\s*(['\"])(.*?)\1", ajax_script, re.I | re.S)
    method_match = re.search(r"\bmethod\s*:\s*(['\"])(.*?)\1", ajax_script, re.I | re.S)
    content_match = re.search(r"\bcontentType\s*:\s*(['\"])(.*?)\1", ajax_script, re.I | re.S)
    stringify_match = re.search(r"\bdata\s*:\s*(?:JSON\.stringify|jQuery\.toJSON|\$\.toJSON)\s*\(", ajax_script, re.I)
    result_rows.append({
        "sourceId": source_id,
        "sourceUrl": source_url,
        "kind": "js_contract",
        "urlRequested": source_url,
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
            endpoint_response = request(opener, ajax["endpoint"], data=body, headers=headers)
            result_rows.append({
                "sourceId": source_id,
                "sourceUrl": source_url,
                "kind": "endpoint_probe",
                "method": "POST_READ_ONLY_LIST",
                "urlRequested": ajax["endpoint"],
                "page": page_number,
                "variant": variant,
                "requestBytes": len(body),
                "requestBodySha256": hashlib.sha256(body).hexdigest(),
                **response_summary(endpoint_response),
            })
    return result_rows
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="write structured JSON results (default: /tmp/official-source-ajax-contract.json)",
    )
    args = parser.parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    by_id = {str(source.get("id", "")): source for source in config.get("listingSources", [])}
    targets = [by_id[source_id] for source_id in TARGET_ORDER if source_id in by_id]
    output: dict = {
        "schemaVersion": 1,
        "purpose": "read-only, time-bounded diagnostics of configured official listing pages and declared AJAX list endpoints",
        "createdAtUtc": utc_now(),
        "timeoutSecondsPerRequest": TIMEOUT_SECONDS,
        "maxResponseBytesPerRequest": MAX_RESPONSE_BYTES,
        "selectedSourceCount": len(targets),
        "expectedSourceCount": len(TARGET_ORDER),
        "sourceOrder": [source["id"] for source in targets],
        "paginationCompletenessProven": False,
        "completenessNote": "Diagnostic samples initial page and selected AJAX pages only; it does not establish complete listing traversal or authorize publication.",
        "results": [],
    }
    for source in targets:
        try:
            output["results"].extend(run_source(source))
        except Exception as exc:
            now = utc_now()
            output["results"].append({
                "sourceId": source.get("id", ""),
                "sourceUrl": source.get("url", ""),
                "urlRequested": source.get("url", ""),
                "kind": "probe_error",
                "errorCode": "DIAGNOSTIC_EXCEPTION",
                "error": f"{type(exc).__name__}: {exc}",
                "attemptStartedUtc": now,
                "attemptEndedUtc": now,
                "timeoutSeconds": TIMEOUT_SECONDS,
            })
    results = output["results"]
    request_rows = [row for row in results if row.get("kind") in {"initial_get", "endpoint_probe"}]
    output["resultCount"] = len(results)
    output["summary"] = {
        "sourceCount": len(targets),
        "sourceCountMissingFromConfig": sorted(set(TARGET_ORDER) - set(by_id)),
        "requestCount": len(request_rows),
        "nonemptyHttp2xxResponses": sum(1 for row in request_rows if 200 <= int(row.get("httpStatus") or 0) < 300 and int(row.get("bodyBytes") or 0) > 0 and not row.get("errorCode")),
        "emptyHttp2xxResponses": sum(1 for row in request_rows if 200 <= int(row.get("httpStatus") or 0) < 300 and int(row.get("bodyBytes") or 0) == 0),
        "httpNon2xxResponses": sum(1 for row in request_rows if int(row.get("httpStatus") or 0) >= 300),
        "transportOrRequestErrors": sum(1 for row in request_rows if not int(row.get("httpStatus") or 0) or row.get("errorCode")),
        "sourcesWithNonemptyInitialPage": sum(1 for row in results if row.get("kind") == "initial_get" and 200 <= int(row.get("httpStatus") or 0) < 300 and int(row.get("bodyBytes") or 0) > 0 and not row.get("errorCode")),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "jsonOutput": str(args.output),
        "sourceCount": output["selectedSourceCount"],
        "expectedSourceCount": output["expectedSourceCount"],
        "requestCount": output["summary"]["requestCount"],
        "emptyHttp2xxResponses": output["summary"]["emptyHttp2xxResponses"],
        "httpNon2xxResponses": output["summary"]["httpNon2xxResponses"],
        "transportOrRequestErrors": output["summary"]["transportOrRequestErrors"],
        "paginationCompletenessProven": False,
    }, ensure_ascii=False))
    return 0 if len(targets) == len(TARGET_ORDER) else 2


if __name__ == "__main__":
    sys.exit(main())
if __name__ == "__main__":
    sys.exit(main())
