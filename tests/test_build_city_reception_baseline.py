import unittest

from scripts.build_city_reception_baseline import (
    cluster_code_columns,
    fragments,
    group_text_lines,
    norm_code,
)


class FakeRect:
    width = 595.32
    height = 842.04


class FakePage:
    rect = FakeRect()

    def get_text(self, kind, sort=False):
        self.asserted_kind = kind
        return [
            (53.5, 100.0, 60.0, 110.0, "1.000016", 0, 0, 0),
        ]


class CityReceptionBaselineParserTests(unittest.TestCase):
    def test_fragments_uses_absolute_page_coordinates(self):
        words = fragments(FakePage())
        self.assertEqual(len(words), 1)
        self.assertAlmostEqual(words[0][0], 737.04, places=2)
        self.assertAlmostEqual(words[0][1], 53.5)
        self.assertEqual(words[0][2], "1.000016")

    def test_separates_repeated_side_by_side_code_columns(self):
        codes = [
            (700, 53, "1.000016"),
            (680, 70, "2.000005"),
            (700, 350, "1.000481"),
            (680, 370, "2.000142"),
        ]
        groups = cluster_code_columns(codes)
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(len(group) for group in groups), [2, 2])

    def test_agency_heading_lines_do_not_join_across_columns(self):
        items = [
            (700.0, 10.0, "IV."),
            (700.0, 25.0, "SỞ"),
            (700.0, 42.0, "TÀI"),
            (700.0, 62.0, "CHÍNH"),
            (699.5, 320.0, "V."),
            (699.5, 338.0, "SỞ"),
            (699.5, 357.0, "CÔNG"),
            (699.5, 385.0, "THƯƠNG"),
        ]
        lines = group_text_lines(items)
        self.assertIn("IV. SỞ TÀI CHÍNH", [line[2] for line in lines])
        self.assertIn("V. SỞ CÔNG THƯƠNG", [line[2] for line in lines])

    def test_normalizes_short_codes_without_losing_zeroes(self):
        self.assertEqual(norm_code("2.00018"), "2.000180")


if __name__ == "__main__":
    unittest.main()
