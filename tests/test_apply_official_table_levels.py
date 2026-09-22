from __future__ import annotations

import unittest

from scripts.build_master_data import apply_official_table_levels


class ApplyOfficialTableLevelsTests(unittest.TestCase):
    def test_updates_public_and_excluded_without_touching_unknown(self):
        public_rows = [
            {"ma": "2.001576", "cap": "Xã / điểm tiếp nhận cấp xã"},
            {"ma": "1.014111", "cap": "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)"},
            {"ma": "9.999999", "cap": "Xã / điểm tiếp nhận cấp xã"},
        ]
        excluded = [{"ma": "1.014116", "cap": "Xã / điểm tiếp nhận cấp xã"}]
        stats = apply_official_table_levels(
            public_rows,
            excluded,
            [],
            {
                "2.001576": "PROVINCE",
                "1.014111": "SHARED",
                "1.014116": "SHARED",
            },
        )
        self.assertEqual(public_rows[0]["cap"], "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã")
        self.assertEqual(public_rows[1]["cap"], "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)")
        self.assertEqual(excluded[0]["cap"], "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)")
        self.assertEqual(public_rows[2]["cap"], "Xã / điểm tiếp nhận cấp xã")
        self.assertEqual(stats["classified"], 3)
        self.assertEqual(stats["changedPublic"], 1)
        self.assertEqual(stats["changedExcluded"], 1)


if __name__ == "__main__":
    unittest.main()
