from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from scripts.canonical_v4 import SOURCE_COMMIT_KIND, upgrade_record_to_v4

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_canonical_contract", ROOT / "scripts" / "validate_canonical_contract.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CanonicalContractTest(unittest.TestCase):
    def payload(self, name: str = "Thủ tục hợp lệ") -> dict:
        row = upgrade_record_to_v4({
            "ma": "1.000001",
            "ten": name,
            "linhVuc": "TƯ PHÁP",
            "cap": "Xã",
            "sourceSnapshotDate": "2026-09-20",
            "sourceEvidence": [{
                "articleUrl": "https://haiphong.gov.vn/thu-tuc-hanh-chinh",
                "articleTitle": "Quyết định công bố",
                "publishedDate": "2026-09-20",
                "effectiveDate": "2026-09-20",
                "classification": "public_tthc_city_update",
                "attachmentUrl": "https://haiphong.gov.vn/a.pdf",
                "attachmentSha256": "a" * 64,
                "decisionNumbers": ["123/QĐ-UBND"],
                "repealContext": False,
            }],
        }, "2026-09-20")
        return {
            "format": "bangniemyet-vinhbao-master-data",
            "version": 4,
            "dataset_version": "2026.09.20",
            "source_commit": "a" * 40,
            "source_commit_kind": SOURCE_COMMIT_KIND,
            "thuTuc": [row],
        }

    def test_accepts_clean_unicode_name(self):
        self.assertEqual(MODULE.validate(self.payload()), [])

    def test_rejects_control_character(self):
        self.assertTrue(any(
            "ký tự điều khiển" in e
            for e in MODULE.validate(self.payload("\x07Tên lỗi\x07"))
        ))

    def test_rejects_cp437_marker(self):
        self.assertTrue(any(
            "CP437" in e for e in MODULE.validate(self.payload("Th├╗ tß╗Ñc"))
        ))

    def test_rejects_known_ocr_split_marker(self):
        self.assertTrue(any(
            "tách chữ OCR" in e
            for e in MODULE.validate(self.payload("Cấp Ch ứng chỉ hành nghề đấu giá"))
        ))

    def test_rejects_broken_field_source_reference(self):
        data = self.payload()
        data["thuTuc"][0]["fieldSources"]["ma"] = ["ev_deadbeefdeadbeefdeadbeef"]
        self.assertTrue(any(
            "tham chiếu evidenceId không tồn tại" in e
            for e in MODULE.validate(data)
        ))

    def test_repository_dataset_passes(self):
        payload = json.loads((ROOT / "data" / "thu-tuc.json").read_text(encoding="utf-8"))
        self.assertEqual(MODULE.validate(payload, ROOT), [])


if __name__ == "__main__":
    unittest.main()
