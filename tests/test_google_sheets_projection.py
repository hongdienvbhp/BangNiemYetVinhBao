import unittest

from scripts.google_sheets_projection import (
    HEADERS,
    EVIDENCE_PRIORITY,
    dedupe_rows,
    delta_notes,
    merge_manual_fields,
    scope_for_master,
    status_for_excluded,
)


class GoogleSheetsProjectionTests(unittest.TestCase):
    def test_scope_does_not_confuse_city_reception_with_commune_authority(self):
        self.assertEqual(
            scope_for_master({"cap": "Cấp tỉnh - tiếp nhận tại Trung tâm PVHCC cấp xã"}),
            "city",
        )
        self.assertEqual(scope_for_master({"cap": "Xã / điểm tiếp nhận cấp xã"}), "commune")
        self.assertEqual(scope_for_master({"cap": "Cấp xã"}), "commune")

    def test_removed_delta_does_not_imply_legal_repeal(self):
        notes = delta_notes({"removed": [{"ma": "1.000001"}]})
        self.assertIn("cần xác minh", notes["1.000001"].lower())
        self.assertNotEqual(notes["1.000001"], "Bãi bỏ")

    def test_excluded_status_is_evidence_driven(self):
        self.assertEqual(
            status_for_excluded({"verificationStatus": "repealed_by_official_city_decision"}),
            "Bãi bỏ",
        )
        self.assertEqual(
            status_for_excluded({"verificationStatus": "future_effective_official_decision"}),
            "Chưa hiệu lực",
        )
        self.assertEqual(status_for_excluded({"verificationStatus": "unknown"}), "Cần xác minh")

    def test_manual_fields_survive_auto_projection(self):
        projected = {h: "" for h in HEADERS}
        projected.update({
            "Mã TTHC": "1.000001",
            "Thủ tục hành chính": "Tên mới từ nguồn chuẩn",
            "Tình trạng hiệu lực": "Còn hiệu lực",
            "Nguồn chính thức": "https://example.gov.vn/a",
        })
        existing = {h: "" for h in HEADERS}
        existing.update({
            "Mã TTHC": "1.000001",
            "Thủ tục hành chính": "Tên cũ",
            "Quy trình nội bộ": "QĐ 123",
            "Quy trình ISO": "ISO-01",
            "Đã công khai tại Trung tâm?": "Có",
            "Ghi chú chi tiết": "Ghi chú nghiệp vụ",
        })
        merged = merge_manual_fields(projected, existing)
        self.assertEqual(merged["Thủ tục hành chính"], "Tên mới từ nguồn chuẩn")
        self.assertEqual(merged["Quy trình nội bộ"], "QĐ 123")
        self.assertEqual(merged["Quy trình ISO"], "ISO-01")
        self.assertEqual(merged["Đã công khai tại Trung tâm?"], "Có")
        self.assertEqual(merged["Ghi chú chi tiết"], "Ghi chú nghiệp vụ")

    def test_dedupe_prefers_newer_evidence_without_false_review(self):
        review = []
        a = {h: "" for h in HEADERS}
        a.update({
            "Mã TTHC": "1.000001",
            "Thủ tục hành chính": "A",
            "Lĩnh vực": "Lĩnh vực",
            "Tình trạng hiệu lực": "Còn hiệu lực",
            "Ngày kiểm tra/cập nhật": "2026-09-10",
        })
        b = dict(a)
        b["Tình trạng hiệu lực"] = "Bãi bỏ"
        b["Ngày kiểm tra/cập nhật"] = "2026-09-15"
        rows = dedupe_rows([a, b], review, "commune")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Tình trạng hiệu lực"], "Bãi bỏ")
        self.assertEqual(review, [])

    def test_same_date_higher_priority_official_evidence_wins_without_review(self):
        review = []
        master = {h: "" for h in HEADERS}
        master.update({
            "Mã TTHC": "1.000001",
            "Thủ tục hành chính": "Tên cũ",
            "Lĩnh vực": "Lĩnh vực",
            "Tình trạng hiệu lực": "Còn hiệu lực",
            "Ngày kiểm tra/cập nhật": "2026-09-18",
            EVIDENCE_PRIORITY: "10",
        })
        official = dict(master)
        official.update({
            "Thủ tục hành chính": "Tên theo quyết định chính thức",
            "Quyết định ban hành/công bố": "123/QĐ-UBND",
            EVIDENCE_PRIORITY: "30",
        })
        rows = dedupe_rows([master, official], review, "city")
        self.assertEqual(rows[0]["Thủ tục hành chính"], "Tên theo quyết định chính thức")
        self.assertEqual(review, [])
        self.assertNotIn(EVIDENCE_PRIORITY, rows[0])

    def test_same_date_equal_priority_material_conflict_still_requires_review(self):
        review = []
        a = {h: "" for h in HEADERS}
        a.update({
            "Mã TTHC": "1.000001",
            "Thủ tục hành chính": "Tên A",
            "Tình trạng hiệu lực": "Còn hiệu lực",
            "Ngày kiểm tra/cập nhật": "2026-09-18",
            EVIDENCE_PRIORITY: "30",
        })
        b = dict(a)
        b["Thủ tục hành chính"] = "Tên B"
        rows = dedupe_rows([a, b], review, "city")
        self.assertEqual(len(rows), 1)
        self.assertEqual(review[0]["reason"], "same_date_material_conflict")



if __name__ == "__main__":
    unittest.main()
