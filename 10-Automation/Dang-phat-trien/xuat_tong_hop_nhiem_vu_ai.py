#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
VAULT_ROOT = BASE_DIR.parent.parent

DEFAULT_DB_PATH = VAULT_ROOT / "10-Automation" / "du-lieu" / "second_brain.db"
OUTPUT_PATH = (
    VAULT_ROOT
    / "03-Resources"
    / "07-So-lieu-Ho-so"
    / "BAO-CAO-TONG-HOP-NHIEM-VU-AI.md"
)


def normalize_key(value):
    return str(value or "").strip().lower().replace("-", "_")


def quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def choose_value(row_dict, candidates):
    lowered = {normalize_key(key): value for key, value in row_dict.items()}
    for candidate in candidates:
        value = lowered.get(normalize_key(candidate))
        if value is not None and str(value).strip() not in ("", "None", "NULL"):
            return str(value).strip()
    return ""


def find_db_candidates():
    candidates = []
    if DEFAULT_DB_PATH.exists():
        candidates.append(DEFAULT_DB_PATH)

    for path in sorted(VAULT_ROOT.rglob("*.db"), key=lambda p: str(p).lower()):
        if path.is_file() and path not in candidates:
            candidates.append(path)

    if not candidates:
        return []

    # Ưu tiên file có tên liên quan đến second brain / vault / nhiem vu / ai
    priority_order = [
        "second_brain",
        "vault",
        "brain",
        "nhiem_vu",
        "ai",
        "db",
    ]
    ordered = []
    for keyword in priority_order:
        for path in candidates:
            lower = str(path).lower()
            if keyword in lower and path not in ordered:
                ordered.append(path)
    for path in candidates:
        if path not in ordered:
            ordered.append(path)
    return ordered


def table_exists(conn, table_name: str) -> bool:
    try:
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        return result is not None
    except sqlite3.Error:
        return False


def list_tables(conn):
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return [row[0] for row in rows]
    except sqlite3.Error:
        return []


def fetch_table_rows(conn, table_name: str):
    if not table_exists(conn, table_name):
        return []
    try:
        columns = conn.execute(f"PRAGMA table_info({quote_ident(table_name)});").fetchall()
        column_names = [col[1] for col in columns]
        rows = conn.execute(f"SELECT * FROM {quote_ident(table_name)};").fetchall()
        return [dict(zip(column_names, row)) for row in rows]
    except sqlite3.Error:
        return []


def find_table_aliases(conn, preferred_names):
    tables = list_tables(conn)
    aliases = []
    for preferred in preferred_names:
        preferred_key = normalize_key(preferred)
        for table_name in tables:
            if normalize_key(table_name) == preferred_key:
                return table_name
        for table_name in tables:
            if preferred_key in normalize_key(table_name):
                aliases.append(table_name)
    return aliases[0] if aliases else None


def build_legal_basis_map(conn):
    result = defaultdict(list)
    table_name = find_table_aliases(conn, ["nhiem_vu_can_cu", "nhiem_vu_cu", "nhiem_vu_cu_theo_ho_so"])
    if not table_name:
        return result

    rows = fetch_table_rows(conn, table_name)
    if not rows:
        return result

    task_key_col = None
    for key in rows[0].keys():
        nk = normalize_key(key)
        if any(token in nk for token in ["nhiem_vu", "task", "nv", "ma_nv", "id_nhiem_vu"]):
            task_key_col = key
            break

    if task_key_col is None:
        for key in rows[0].keys():
            if normalize_key(key) in {"id", "ma", "ma_so"}:
                task_key_col = key
                break

    legal_cols = []
    for key in rows[0].keys():
        nk = normalize_key(key)
        if any(token in nk for token in ["so_hieu", "van_ban", "dieu_khoan", "can_cu", "nguon", "co_so", "legal"]):
            legal_cols.append(key)

    for row in rows:
        task_id_value = ""
        if task_key_col and task_key_col in row:
            task_id_value = normalize_text(row.get(task_key_col))
        if not task_id_value:
            continue

        legal_items = []
        for key in legal_cols:
            val = normalize_text(row.get(key))
            if not val:
                continue
            if "dieu_khoan" in normalize_key(key) and val:
                legal_items.append(f"Điều {val}")
            elif val:
                legal_items.append(val)

        if not legal_items:
            for key in ["can_cu_nguon", "nguon_can_cu", "nguon", "co_so_phan_lap", "ghi_chu"]:
                val = normalize_text(row.get(key))
                if val:
                    legal_items.append(val)

        if legal_items:
            result[str(task_id_value)] = legal_items[:6]

    return result


def escape_markdown(value):
    text = normalize_text(value)
    if not text:
        return "—"
    text = text.replace("|", "\\|").replace("\n", " ")
    return text.strip()


def build_report_markdown(conn):
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    tasks_table = find_table_aliases(conn, ["nhiem_vu", "task", "cong_viec", "nhiem_vu_ai"])
    if not tasks_table:
        return "---\ntype: ai-digest\ngenerated_at: " + generated_at + "\ntotal_tasks: 0\npurpose: Cung cap ngu canh nhiem vu tong hop cho AI tra cuu va phan tich\n---\n\n# Báo cáo tổng hợp nhiệm vụ AI\n\nKhông tìm thấy bảng nhiệm vụ trong cơ sở dữ liệu.\n"

    tasks = fetch_table_rows(conn, tasks_table)
    legal_basis_map = build_legal_basis_map(conn)
    by_domain = defaultdict(list)

    for index, row in enumerate(tasks, start=1):
        task_key = choose_value(
            row,
            [
                "ma_nhiem_vu",
                "ma_nv",
                "id",
                "ma",
                "ma_so",
                "stt",
                "ma_nhiem_vu_ai",
                "nhiem_vu_id",
                "id_nhiem_vu",
            ],
        )
        if not task_key:
            task_key = f"NV-{index}"

        domain = choose_value(
            row,
            ["linh_vuc", "domain", "danh_muc", "nhom", "linh_vuc_cong_viec", "chuyen_muc", "phan_loai"],
        )
        if not domain:
            domain = "Chung"

        task = {
            "ma_nv": task_key,
            "noi_dung": choose_value(
                row,
                [
                    "noi_dung",
                    "noi_dung_cong_viec",
                    "mo_ta",
                    "mo_ta_cong_viec",
                    "ten_nhiem_vu",
                    "nhiem_vu",
                    "tieu_de",
                    "noi_dung_chi_tiet",
                    "ten_cong_viec",
                ],
            ),
            "chu_the": choose_value(
                row,
                [
                    "chu_the",
                    "chu_the_trach_nhiem",
                    "trach_nhiem",
                    "nguoi_chiu_trach_nhiem",
                    "co_quan",
                    "don_vi",
                    "chu_the_phu_trach",
                    "don_vi_phu_trach",
                ],
            ),
            "san_pham": choose_value(
                row,
                [
                    "san_pham",
                    "san_pham_dau_ra",
                    "san_pham_hoan_thanh",
                    "ket_qua",
                    "san_pham_dau_ra_cuoi",
                    "san_pham_ky_vong",
                    "dau_ra",
                ],
            ),
            "chu_ky": choose_value(
                row,
                [
                    "chu_ky",
                    "chu_ky_han",
                    "thoi_han",
                    "han",
                    "deadline",
                    "han_hoan_thanh",
                    "thoi_han_hoan_thanh",
                    "thoi_gian",
                    "thoi_han_hoan_thanh",
                ],
            ),
        }

        legal_values = legal_basis_map.get(str(task_key), [])
        if not legal_values:
            alt_keys = [
                normalize_text(row.get("id")),
                normalize_text(row.get("nhiem_vu_id")),
                normalize_text(row.get("id_nhiem_vu")),
            ]
            for alt in alt_keys:
                if alt and alt in legal_basis_map:
                    legal_values = legal_basis_map.get(alt, [])
                    break

        if not legal_values:
            for key in ["can_cu_nguon", "nguon_can_cu", "co_so_phan_lap"]:
                val = normalize_text(row.get(key))
                if val:
                    legal_values.append(val)

        task["cnd"] = "; ".join(legal_values) if legal_values else "—"
        by_domain[domain].append(task)

    domains = sorted(by_domain.keys(), key=lambda d: d.lower())

    lines = []
    lines.append("---")
    lines.append("type: ai-digest")
    lines.append(f"generated_at: {generated_at}")
    lines.append(f"total_tasks: {len(tasks)}")
    lines.append("purpose: Cung cap ngu canh nhiem vu tong hop cho AI tra cuu va phan tich")
    lines.append("---")
    lines.append("")
    lines.append("# Báo cáo tổng hợp nhiệm vụ AI")
    lines.append("")
    lines.append(f"Tổng số nhiệm vụ: {len(tasks)}")
    lines.append("")

    if not tasks:
        lines.append("Không có dữ liệu nhiệm vụ trong cơ sở dữ liệu.")
        return "\n".join(lines) + "\n"

    for domain in domains:
        tasks_in_domain = by_domain[domain]
        lines.append(f"## {escape_markdown(domain)}")
        lines.append("")
        lines.append(
            "| Mã NV | Nội dung công việc | Chủ thể / Trách nhiệm | Sản phẩm đầu ra | Chu kỳ / Hạn | Căn cứ pháp lý chính |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")

        for task in tasks_in_domain:
            lines.append(
                "| "
                f"{escape_markdown(task['ma_nv'])} | "
                f"{escape_markdown(task['noi_dung'])} | "
                f"{escape_markdown(task['chu_the'])} | "
                f"{escape_markdown(task['san_pham'])} | "
                f"{escape_markdown(task['chu_ky'])} | "
                f"{escape_markdown(task['cnd'])} |"
            )

        lines.append("")

    return "\n".join(lines) + "\n"


def safe_main():
    db_candidates = find_db_candidates()
    if not db_candidates:
        print("[THÔNG BÁO] Không tìm thấy file SQLite trong vault theo đường dẫn mong đợi: ")
        print(f"  - {DEFAULT_DB_PATH}")
        print("[THÔNG BÁO] Thiếu CSDL nên script dừng an toàn và không làm crash hệ thống.")
        return 0

    db_path = db_candidates[0]
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        report = build_report_markdown(conn)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(report, encoding="utf-8")

        print(f"[OK] Đã tạo báo cáo tổng hợp nhiệm vụ AI tại: {OUTPUT_PATH}")
        print(f"[OK] Đang dùng file SQLite: {db_path}")
        return 0
    except sqlite3.Error as exc:
        print(f"[LỖI] Không thể kết nối hoặc đọc CSDL SQLite: {exc}")
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass


if __name__ == "__main__":
    raise SystemExit(safe_main())
