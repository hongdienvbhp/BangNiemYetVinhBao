import unittest

from scripts import extract_city_updates as extractor


class ExtractCityUpdatesTests(unittest.TestCase):
    def test_code_regex_only_accepts_canonical_tthc_shape(self):
        text = "1.001117 1.000 1.500 10.000 15.000 50.000 2.001909"
        self.assertEqual(extractor.CODE_RE.findall(text), ["1.001117", "2.001909"])

    def test_reception_location_does_not_change_legal_level(self):
        line = "Trung tâm Phục vụ hành chính công thành phố và cấp xã"
        self.assertEqual(extractor.level_hint(line, "province"), "province")

    def test_split_tthc_code_is_repaired(self):
        lines = ["1. 1.00488", "9", "Công nhận bằng tốt nghiệp"]
        self.assertEqual(
            extractor.repair_split_tthc_codes(lines),
            ["1. 1.004889", "", "Công nhận bằng tốt nghiệp"],
        )

    def test_commune_reception_without_word_cap_is_detected(self):
        lines = [
            "1.004889 Công nhận bằng tốt nghiệp",
            "Trung tâm Phục vụ hành chính công thành phố;",
            "Trung tâm Phục vụ hành chính công xã, phường, đặc khu.",
        ]
        self.assertTrue(extractor.context_is_commune(lines, 0, "province"))

    def test_explicit_procedure_heading_changes_legal_level(self):
        self.assertEqual(
            extractor.level_hint("THỦ TỤC HÀNH CHÍNH CẤP XÃ", "province"),
            "commune",
        )
        self.assertEqual(extractor.level_hint("B. CẤP TỈNH", "commune"), "province")


if __name__ == "__main__":
    unittest.main()
