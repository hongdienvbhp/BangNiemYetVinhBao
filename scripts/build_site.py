"""Đóng gói website tĩnh vào thư mục phát hành (dùng chung GitHub Pages và Firebase Hosting).

Chỉ sao chép đúng các tài nguyên runtime; không đưa dữ liệu audit/nguồn vào bản công khai.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_FILES = (
    "index.html",
    "manifest.json",
    "sw.js",
    "css/styles.css",
    "js/config.js",
    "js/data.js",
    "js/master-data-fallback.js",
    "js/extra-data.js",
    "js/app.js",
    "assets/logo-hcc.png",
    "assets/logo-hcc.svg",
    "data/thu-tuc.json",
)


def build(out_dir: Path, root: Path = ROOT) -> int:
    missing_src = [p for p in RUNTIME_FILES if not (root / p).is_file()]
    if missing_src:
        raise SystemExit(f"Thiếu tài nguyên nguồn: {missing_src}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    for rel in RUNTIME_FILES:
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, dst)
    (out_dir / ".nojekyll").touch()

    payload = json.loads((out_dir / "data/thu-tuc.json").read_text(encoding="utf-8-sig"))
    published = payload.get("summary", {}).get("publishedProcedures", 0)
    if published <= 0:
        raise SystemExit("Master Data rỗng")
    if len(payload.get("thuTuc") or []) != published:
        raise SystemExit("Số thủ tục trong thuTuc không khớp summary.publishedProcedures")
    return published


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="_site", help="Thư mục đích (mặc định: _site)")
    args = parser.parse_args(argv)
    published = build(ROOT / args.out)
    print(f"Site artifact: {len(RUNTIME_FILES)} tài nguyên, {published} thủ tục công khai")
    return 0


if __name__ == "__main__":
    sys.exit(main())
