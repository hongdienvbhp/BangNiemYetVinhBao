import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_google_sheets as sync


def sheet_row(code, **updates):
    row = {name: "" for name in sync.HEADERS}
    row.update({
        "Mã TTHC": code,
        "Thủ tục hành chính": f"Thủ tục {code}",
        "Lĩnh vực": "Lĩnh vực thử nghiệm",
        "Tình trạng hiệu lực": "Còn hiệu lực",
        "Ghi chú cập nhật": "Điều chỉnh",
        "Nguồn chính thức": "https://example.gov.vn/tthc",
    })
    row.update(updates)
    return row


class SyncGoogleSheetsSafetyTests(unittest.TestCase):
    def test_empty_projection_fails_before_sheet_read_or_write(self):
        with patch.object(sync, "existing_rows") as read_rows, \
             patch.object(sync, "batch_update_values") as write_rows, \
             patch.object(sync, "append_values") as append_log, \
             patch.object(sync, "batch_clear") as clear_rows:
            with self.assertRaisesRegex(RuntimeError, "empty commune projection"):
                sync.sync_target(object(), "sheet-id", "commune", [])
        read_rows.assert_not_called()
        write_rows.assert_not_called()
        append_log.assert_not_called()
        clear_rows.assert_not_called()

    def test_already_held_row_does_not_create_duplicate_held_log(self):
        current = sheet_row(
            "1.000002",
            **{
                "Tình trạng hiệu lực": "Cần xác minh",
                "Ghi chú cập nhật": "Điều chỉnh",
                "Ghi chú chi tiết": (
                    "[AUTO] Mã không còn trong projection mới; giữ nguyên để rà soát, không tự xóa."
                ),
            },
        )
        projected = sheet_row("1.000001")
        snapshot = {"1.000001": projected, "1.000002": current}

        with patch.object(sync, "existing_rows", side_effect=[(snapshot, 2), (snapshot, 2)]), \
             patch.object(sync, "batch_update_values"), \
             patch.object(sync, "batch_clear"), \
             patch.object(sync, "append_values") as append_log:
            result = sync.sync_target(object(), "sheet-id", "commune", [projected])

        append_log.assert_called_once()
        logged_rows = append_log.call_args.args[3]
        self.assertEqual(logged_rows, [])
        self.assertTrue(result["readBackVerified"])
        self.assertEqual(result["rows"], 2)


if __name__ == "__main__":
    unittest.main()
