from __future__ import annotations

import unittest

from scripts.build_master_data import canonical_cap_from_table_classification


class OfficialTableBuilderLevelTests(unittest.TestCase):
    def test_commune(self):
        self.assertEqual(canonical_cap_from_table_classification("COMMUNE", "old"), "Xã")

    def test_shared(self):
        self.assertEqual(
            canonical_cap_from_table_classification("SHARED", "old"),
            "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)",
        )

    def test_province(self):
        self.assertEqual(
            canonical_cap_from_table_classification("PROVINCE", "old"),
            "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã",
        )

    def test_unknown_preserves_fallback(self):
        self.assertEqual(canonical_cap_from_table_classification("", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
