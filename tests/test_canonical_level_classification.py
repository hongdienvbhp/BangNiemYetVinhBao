from __future__ import annotations

import unittest

from scripts.build_master_data import canonical_cap_from_city_row


class CanonicalLevelClassificationTests(unittest.TestCase):
    def test_commune_hint(self):
        self.assertEqual(canonical_cap_from_city_row({"levelHint": "commune"}), "Xã")

    def test_shared_hint(self):
        self.assertEqual(
            canonical_cap_from_city_row({"levelHint": "shared_including_commune"}),
            "Dùng chung (cấp bộ, cấp tỉnh, cấp xã)",
        )

    def test_province_hint(self):
        self.assertEqual(
            canonical_cap_from_city_row({"levelHint": "province"}),
            "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã",
        )

    def test_unknown_hint_does_not_infer_province(self):
        self.assertEqual(
            canonical_cap_from_city_row({"communeReceptionEvidence": True}),
            "Xã / điểm tiếp nhận cấp xã",
        )


if __name__ == "__main__":
    unittest.main()
