from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "classify_official_tables", ROOT / "scripts" / "classify_official_tables.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class OfficialTableClassificationTests(unittest.TestCase):
    def test_commune_heading(self):
        result = MODULE.classify_snippet(
            "2.002821",
            "B THỦ TỤC HÀNH CHÍNH CẤP XÃ (01 TTHC) 1 2.002821 Hỗ trợ đào tạo nghề",
        )
        self.assertEqual(result, ("COMMUNE", "THỦ TỤC HÀNH CHÍNH CẤP XÃ"))

    def test_shared_heading(self):
        result = MODULE.classify_snippet(
            "1.014111",
            "THỦ TỤC HÀNH CHÍNH DÙNG CHUNG (CẤP BỘ, CẤP TỈNH, CẤP XÃ) 1. 1.014111 Thi tuyển công chức",
        )
        self.assertEqual(result, ("SHARED", "THỦ TỤC HÀNH CHÍNH DÙNG CHUNG"))

    def test_reception_text_alone_is_not_authority(self):
        self.assertIsNone(
            MODULE.classify_snippet(
                "1.000479",
                "1.000479 Cấp giấy phép - Trung tâm PVHCC thành phố - Trung tâm PVHCC cấp xã",
            )
        )

    def test_repository_snapshot_is_conflict_free(self):
        payload = json.loads((ROOT / "data" / "source-audit" / "vinhbao-tthc-attachment-evidence-20260906.json").read_text(encoding="utf-8-sig"))
        result = MODULE.build(payload)
        self.assertEqual(result["summary"]["conflicts"], 0)
        self.assertGreaterEqual(result["summary"]["resolved"], 36)

if __name__ == "__main__":
    unittest.main()
