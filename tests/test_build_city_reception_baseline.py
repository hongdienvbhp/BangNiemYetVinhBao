import unittest

from scripts.build_city_reception_baseline import cluster_code_columns, matrix_multiply, norm_code


class CityReceptionBaselineParserTests(unittest.TestCase):
    def test_composes_text_and_current_transformation_matrices(self):
        tm = (1, 0, 0, 1, 160, 700)
        cm = (1, 0, 0, 1, 600, 0)
        composed = matrix_multiply(tm, cm)
        self.assertEqual(composed[4], 760)
        self.assertEqual(composed[5], 700)

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

    def test_normalizes_short_codes_without_losing_zeroes(self):
        self.assertEqual(norm_code("2.00018"), "2.000180")


if __name__ == "__main__":
    unittest.main()
