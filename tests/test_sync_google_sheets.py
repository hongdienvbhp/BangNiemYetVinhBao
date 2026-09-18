import unittest

from scripts.google_sheets_projection import HEADERS
from scripts.sync_google_sheets import merge_duplicate_existing_rows


class GoogleSheetsSyncTests(unittest.TestCase):
    def row(self, **updates):
        value = {h: "" for h in HEADERS}
        value.update(updates)
        return value

    def test_duplicate_rows_merge_non_conflicting_manual_values(self):
        first = self.row(**{
            "Mã TTHC": "1.001.731",
            "Quy trình nội bộ": "QĐ 123",
            "Ghi chú chi tiết": "",
        })
        second = self.row(**{
            "Mã TTHC": "1.001.731",
            "Quy trình nội bộ": "QĐ 123",
            "Ghi chú chi tiết": "Ghi chú nghiệp vụ",
            "Thủ tục hành chính": "Tên tự động khác không quyết định merge",
        })
        merged = merge_duplicate_existing_rows("1.001.731", first, second)
        self.assertEqual(merged["Quy trình nội bộ"], "QĐ 123")
        self.assertEqual(merged["Ghi chú chi tiết"], "Ghi chú nghiệp vụ")

    def test_duplicate_rows_fail_closed_on_manual_conflict(self):
        first = self.row(**{
            "Mã TTHC": "1.001.731",
            "Quy trình nội bộ": "QĐ 123",
        })
        second = self.row(**{
            "Mã TTHC": "1.001.731",
            "Quy trình nội bộ": "QĐ 999",
        })
        with self.assertRaisesRegex(RuntimeError, "conflicting manual field"):
            merge_duplicate_existing_rows("1.001.731", first, second)


if __name__ == "__main__":
    unittest.main()
