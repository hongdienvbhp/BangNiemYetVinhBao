import unittest

from scripts.build_city_reception_baseline import (
    cluster_code_columns,
    fragments,
    group_text_lines,
    norm_code,
)


class FakePage:
    height = 842.0
    width = 1414.0

    def extract_words(self, **kwargs):
        return [
            {"text": "1.000016", "x0": 125.9, "top": 100.0, "bottom": 110.0},
        ]


class CityReceptionBaselineParserTests(unittest.TestCase):
    def test_fragments_uses_absolute_page_coordinates(self):
        words = fragments(FakePage())
        self.assertEqual(len(words), 1)
        self.assertAlmostEqual(words[0][0], 737.0)
        self.assertAlmostEqual(words[0][1], 125.9)
        self.assertEqual(words[0][2], "1.000016")

    def test_separates_repeated_side_by_side_code_columns(self):
        codes = [
            (700, 110, "1.000016"),
            (680, 170, "2.000005"),
            (700, 710, "1.000481"),
            (680, 770, "2.000142"),
        ]
        groups = cluster_code_columns(codes)
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(len(group) for group in groups), [2, 2])

    def test_agency_heading_lines_do_not_join_across_columns(self):
        items = [
            (700.0, 20.0, "IV."),
            (700.0, 45.0, "SỞ"),
            (700.0, 70.0, "TÀI"),
            (700.0, 100.0, "CHÍNH"),
            (699.5, 620.0, "V."),
            (699.5, 645.0, "SỞ"),
            (699.5, 670.0, "CÔNG"),
            (699.5, 715.0, "THƯƠNG"),
        ]
        lines = group_text_lines(items)
        self.assertIn("IV. SỞ TÀI CHÍNH", [line[2] for line in lines])
        self.assertIn("V. SỞ CÔNG THƯƠNG", [line[2] for line in lines])

    def test_normalizes_short_codes_without_losing_zeroes(self):
        self.assertEqual(norm_code("2.00018"), "2.000180")


if __name__ == "__main__":
    unittest.main()
