import unittest

from scripts.build_city_reception_baseline import (
    code_from_block,
    extract_rows,
    norm_code,
    words_text,
)


class FakePage:
    def __init__(self, blocks, words):
        self.blocks = blocks
        self.words = words

    def get_text(self, kind, sort=False):
        if kind == "blocks":
            return self.blocks
        if kind == "words":
            return self.words
        raise AssertionError(kind)


class CityReceptionBaselineParserTests(unittest.TestCase):
    def test_code_must_be_a_standalone_early_row_line(self):
        self.assertEqual(code_from_block("78.\n1.000016\nThông báo tăng vốn"), "1.000016")
        self.assertEqual(code_from_block("1.000481\nCấp điều chỉnh giấy chứng nhận"), "1.000481")
        self.assertEqual(code_from_block("79. 2.000005\nThủ tục đăng ký thay đổi"), "2.000005")
        self.assertIsNone(code_from_block("Tên thủ tục\nSố tham chiếu 5.000000"))

    def test_words_text_splits_name_and_field_cells(self):
        words = [
            (125.9, 68.87, 174.5, 83.22, "1.000481", 1, 0, 0),
            (196.85, 61.41, 217.73, 75.76, "Cấp", 1, 1, 0),
            (220.61, 61.41, 242.92, 75.76, "điều", 1, 1, 1),
            (443.26, 68.87, 469.19, 83.22, "Kinh", 1, 3, 0),
            (472.43, 68.87, 504.21, 83.22, "doanh", 1, 3, 1),
            (507.46, 68.87, 524.03, 83.22, "khí", 1, 3, 2),
        ]
        self.assertEqual(words_text(words, 160, 443), "Cấp điều")
        self.assertEqual(words_text(words, 443, 700), "Kinh doanh khí")

    def test_extracts_a_row_with_field_in_same_text_block(self):
        blocks = [
            (83.42, 59.37, 99.62, 73.72, "101.", 0, 0),
            (125.9, 61.41, 527.38, 90.78,
             "1.000481\nCấp điều chỉnh Giấy chứng nhận đủ điều kiện\nthương nhân kinh doanh mua bán CNG\nKinh doanh khí", 1, 0),
        ]
        words = [
            (125.9, 68.87, 174.5, 83.22, "1.000481", 1, 0, 0),
            (196.85, 61.41, 217.73, 75.76, "Cấp", 1, 1, 0),
            (220.61, 61.41, 242.92, 75.76, "điều", 1, 1, 1),
            (443.26, 68.87, 469.19, 83.22, "Kinh", 1, 3, 0),
            (472.43, 68.87, 504.21, 83.22, "doanh", 1, 3, 1),
            (507.46, 68.87, 524.03, 83.22, "khí", 1, 3, 2),
        ]
        rows = extract_rows([FakePage(blocks, words)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "1.000481")
        self.assertEqual(rows[0]["name"], "Cấp điều")
        self.assertEqual(rows[0]["field"], "Kinh doanh khí")

    def test_extracts_a_field_stored_in_a_separate_text_block(self):
        blocks = [
            (83.42, 713.83, 435.52, 743.06,
             "78.\n1.000016\nThông báo tăng, giảm vốn góp của quỹ đầu tư\nkhởi nghiệp sáng tạo (cấp tỉnh)", 1, 0),
            (443.26, 721.27, 545.98, 735.62, "Hỗ trợ doanh nghiệp nhỏ và vừa", 2, 0),
            (83.42, 748.71, 435.52, 777.94,
             "79.\n2.000005\nThủ tục đăng ký thay đổi vốn điều lệ", 3, 0),
        ]
        words = [
            (83.42, 721.27, 99.62, 735.62, "78.", 1, 0, 0),
            (125.9, 721.27, 174.5, 735.62, "1.000016", 1, 1, 0),
            (196.85, 713.83, 230.69, 728.18, "Thông", 1, 2, 0),
            (233.45, 713.83, 252.27, 728.18, "báo", 1, 2, 1),
            (196.85, 728.71, 220.27, 743.06, "khởi", 1, 3, 0),
            (223.51, 728.71, 258.88, 743.06, "nghiệp", 1, 3, 1),
            (443.26, 721.27, 467.0, 735.62, "Hỗ trợ", 2, 0, 0),
            (469.0, 721.27, 545.98, 735.62, "doanh nghiệp nhỏ và vừa", 2, 0, 1),
            (83.42, 756.15, 99.62, 770.5, "79.", 3, 0, 0),
            (125.9, 756.15, 174.5, 770.5, "2.000005", 3, 1, 0),
            (196.85, 748.71, 230.0, 763.06, "Thủ tục", 3, 2, 0),
        ]
        rows = extract_rows([FakePage(blocks, words)])
        self.assertEqual(len(rows), 2)
        first = rows[0]
        self.assertEqual(first["code"], "1.000016")
        self.assertEqual(first["name"], "Thông báo khởi nghiệp")
        self.assertEqual(first["field"], "Hỗ trợ doanh nghiệp nhỏ và vừa")

    def test_normalizes_short_codes_without_losing_zeroes(self):
        self.assertEqual(norm_code("2.00018"), "2.000180")


    def test_extracts_multiple_codes_in_one_pdf_block(self):
        blocks = [
            (83.42, 100.0, 545.98, 145.0,
             "1.000001\nFirst procedure\nField A\n2.000002\nSecond procedure\nField B", 1, 0),
        ]
        words = [
            (125.9, 100.0, 174.5, 114.0, "1.000001", 1, 0, 0),
            (196.85, 100.0, 217.73, 114.0, "First", 1, 0, 1),
            (220.61, 100.0, 260.0, 114.0, "procedure", 1, 0, 2),
            (443.26, 100.0, 469.19, 114.0, "Field", 1, 0, 3),
            (472.43, 100.0, 486.0, 114.0, "A", 1, 0, 4),
            (125.9, 125.0, 174.5, 139.0, "2.000002", 1, 1, 0),
            (196.85, 125.0, 238.0, 139.0, "Second", 1, 1, 1),
            (240.0, 125.0, 280.0, 139.0, "procedure", 1, 1, 2),
            (443.26, 125.0, 469.19, 139.0, "Field", 1, 1, 3),
            (472.43, 125.0, 486.0, 139.0, "B", 1, 1, 4),
        ]

        rows = extract_rows([FakePage(blocks, words)])

        self.assertEqual([row["code"] for row in rows], ["1.000001", "2.000002"])
        self.assertEqual(rows[0]["name"], "First procedure")
        self.assertEqual(rows[0]["field"], "Field A")
        self.assertEqual(rows[1]["name"], "Second procedure")
        self.assertEqual(rows[1]["field"], "Field B")


if __name__ == "__main__":
    unittest.main()
