import unittest

from scripts.build_priority50_guidance import (
    label_value,
    parse_dossier_table,
    parse_process_tables,
)


class Priority50GuidanceParserTests(unittest.TestCase):
    def test_extracts_agency_and_result_labels(self):
        body = """Thông tin thủ tục
Cơ quan thực hiện:
Ủy ban nhân dân cấp xã
Kết quả thực hiện:
Quyết định giải quyết thủ tục
"""
        self.assertEqual(label_value(body, ("Cơ quan thực hiện",)), "Ủy ban nhân dân cấp xã")
        self.assertEqual(label_value(body, ("Kết quả thực hiện",)), "Quyết định giải quyết thủ tục")

    def test_parses_process_table(self):
        tables = [{
            "rows": [
                ["Hình thức nộp", "Thời hạn giải quyết", "Phí, lệ phí", "Mô tả"],
                ["Trực tiếp", "03 Ngày làm việc", "Không", "Kể từ khi đủ hồ sơ"],
                ["Trực tuyến", "03 Ngày làm việc", "Không", "Kể từ khi đủ hồ sơ"],
            ]
        }]
        times, fees = parse_process_tables(tables)
        self.assertEqual(len(times), 2)
        self.assertEqual(times[0]["hinhThuc"], "Trực tiếp")
        self.assertEqual(times[0]["giaTri"], "03 Ngày làm việc")
        self.assertEqual(fees[1]["mucThu"], "Không")

    def test_parses_dossier_table(self):
        tables = [{
            "rows": [
                ["Tên giấy tờ", "Mẫu đơn, tờ khai", "Bản chính", "Bản sao"],
                ["Tờ khai đề nghị", "Mẫu số 01", "1", "0"],
            ]
        }]
        items = parse_dossier_table(tables)
        self.assertEqual(items, [{
            "ten": "Tờ khai đề nghị",
            "bieuMau": "Mẫu số 01",
            "banChinh": "1",
            "banSao": "0",
        }])


if __name__ == "__main__":
    unittest.main()
