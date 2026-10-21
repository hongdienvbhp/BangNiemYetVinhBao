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

    def test_bare_cap_xa_table_cell_does_not_change_legal_level(self):
        # Ô "Địa điểm thực hiện" bị xuống dòng chỉ còn "cấp xã" không phải tiêu đề mục.
        self.assertEqual(extractor.level_hint("cấp xã", "province"), "province")
        self.assertEqual(extractor.level_hint("B. cấp xã", "province"), "commune")

    def test_missing_effective_clause_defaults_to_signing_date(self):
        # QĐ 1847/QĐ-UBND không ghi điều khoản hiệu lực → hiệu lực từ ngày ký.
        meta = {
            "decisionNo": "1847/QĐ-UBND",
            "decisionDate": "2026-05-19",
            "filePath": "data/source-audit/city-decisions/QD-1847.pdf",
            "field": "GIÁO DỤC VÀ ĐÀO TẠO",
            "ingestStatus": "applied",
            "classification": "public_tthc",
        }
        result = extractor.extract_decision(meta, "2026-09-29")
        self.assertEqual(result["effectiveDate"], "2026-05-19")
        self.assertEqual(result["effectiveDateSource"], "default_effective_from_signing_date")
        self.assertEqual(result["currentStateAtAsOf"], "current_or_immediate_unless_repealed")

    def test_row_scope_requires_reception_in_own_row(self):
        lines = [
            "1 1.005169 Đề nghị doanh nghiệp thay đổi tên 03 ngày làm việc - Trung tâm Phục vụ hành chính công thành phố",
            "2 1.010010 Đề nghị dừng thực hiện thủ tục - Trung tâm Phục vụ hành chính công cấp xã",
        ]
        self.assertFalse(extractor.row_is_commune(lines, 0, "province"))
        self.assertTrue(extractor.row_is_commune(lines, 1, "province"))
        self.assertTrue(extractor.row_is_commune(lines, 0, "commune"))

    def test_row_effective_date_override_keeps_future_repeal_pending(self):
        override = extractor.DECISION_ROW_OVERRIDES["3249/QĐ-UBND"]
        self.assertEqual(override["1.011607"]["rowEffectiveDate"], "2027-01-01")


if __name__ == "__main__":
    unittest.main()
