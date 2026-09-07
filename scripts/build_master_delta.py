#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a deterministic before/after Master Data delta report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

TRACKED_FIELDS = [
    "ten",
    "linhVuc",
    "cap",
    "phiDiaGioi",
    "lienThong",
    "phi",
    "phiOnline",
    "thoiHan",
    "dvctt",
    "coQuan",
    "quyetDinh",
    "formalityId",
    "verificationStatus",
    "sourceLatestDate",
    "sourceArticleUrl",
    "sourceAttachmentUrl",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def by_code(payload: dict) -> dict[str, dict]:
    return {
        str(row.get("ma") or "").strip(): row
        for row in payload.get("thuTuc", [])
        if str(row.get("ma") or "").strip()
    }


def make_delta(before: dict, after: dict) -> dict:
    old = by_code(before)
    new = by_code(after)
    added_codes = sorted(set(new) - set(old))
    removed_codes = sorted(set(old) - set(new))
    changed: list[dict] = []

    for code in sorted(set(old) & set(new)):
        fields: dict[str, dict] = {}
        for field in TRACKED_FIELDS:
            before_value = old[code].get(field)
            after_value = new[code].get(field)
            if before_value != after_value:
                fields[field] = {"before": before_value, "after": after_value}
        if fields:
            changed.append(
                {
                    "ma": code,
                    "ten": new[code].get("ten") or old[code].get("ten") or "",
                    "fields": fields,
                }
            )

    return {
        "format": "bangniemyet-master-data-delta",
        "version": 1,
        "beforeSnapshotDate": before.get("sourceSnapshotDate"),
        "afterSnapshotDate": after.get("sourceSnapshotDate"),
        "summary": {
            "beforePublic": len(old),
            "afterPublic": len(new),
            "added": len(added_codes),
            "removed": len(removed_codes),
            "changed": len(changed),
        },
        "added": [
            {
                "ma": code,
                "ten": new[code].get("ten") or "",
                "linhVuc": new[code].get("linhVuc") or "",
                "quyetDinh": new[code].get("quyetDinh") or "",
                "sourceArticleUrl": new[code].get("sourceArticleUrl") or "",
                "sourceAttachmentUrl": new[code].get("sourceAttachmentUrl") or "",
            }
            for code in added_codes
        ],
        "removed": [
            {
                "ma": code,
                "ten": old[code].get("ten") or "",
                "linhVuc": old[code].get("linhVuc") or "",
                "previousDecision": old[code].get("quyetDinh") or "",
            }
            for code in removed_codes
        ],
        "changed": changed,
    }


def render_markdown(delta: dict) -> str:
    summary = delta["summary"]
    lines = [
        "# BÁO CÁO CHÊNH LỆCH MASTER DATA TTHC",
        "",
        f"- Snapshot trước: **{delta.get('beforeSnapshotDate') or 'không xác định'}**",
        f"- Snapshot sau: **{delta.get('afterSnapshotDate') or 'không xác định'}**",
        f"- TTHC công khai trước: **{summary['beforePublic']}**",
        f"- TTHC công khai sau: **{summary['afterPublic']}**",
        f"- Thêm mới: **{summary['added']}**",
        f"- Loại khỏi danh mục công khai: **{summary['removed']}**",
        f"- Thay đổi thông tin: **{summary['changed']}**",
        "",
        "> Báo cáo này chỉ mô tả chênh lệch dữ liệu. Căn cứ pháp lý nằm trong sourceEvidence/sourceArticleUrl/sourceAttachmentUrl của từng bản ghi.",
        "",
    ]

    if delta["added"]:
        lines += [
            "## 1. Thủ tục thêm mới",
            "",
            "| Mã | Tên thủ tục | Lĩnh vực | Quyết định |",
            "|---|---|---|---|",
        ]
        for row in delta["added"]:
            lines.append(
                f"| {row['ma']} | {str(row['ten']).replace('|', '/')} | "
                f"{str(row['linhVuc']).replace('|', '/')} | {str(row['quyetDinh']).replace('|', '/')} |"
            )
        lines.append("")

    if delta["removed"]:
        lines += [
            "## 2. Thủ tục loại khỏi danh mục công khai",
            "",
            "| Mã | Tên thủ tục | Lĩnh vực |",
            "|---|---|---|",
        ]
        for row in delta["removed"]:
            lines.append(
                f"| {row['ma']} | {str(row['ten']).replace('|', '/')} | {str(row['linhVuc']).replace('|', '/')} |"
            )
        lines.append("")

    if delta["changed"]:
        lines += ["## 3. Thủ tục thay đổi thông tin", ""]
        for row in delta["changed"]:
            lines.append(f"### {row['ma']} — {row['ten']}")
            for field, values in row["fields"].items():
                lines.append(f"- **{field}**: {values['before']} → {values['after']}")
            lines.append("")

    if not (delta["added"] or delta["removed"] or delta["changed"]):
        lines += ["## Kết quả", "", "Không có thay đổi ngữ nghĩa trong Master Data.", ""]

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    args = parser.parse_args()

    delta = make_delta(load(args.before), load(args.after))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(delta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(render_markdown(delta), encoding="utf-8")

    print(json.dumps(delta["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
