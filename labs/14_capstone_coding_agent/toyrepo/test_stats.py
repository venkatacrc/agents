import unittest

from stats import mean, median, percentile


class TestStats(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(mean([1, 2, 3]), 2)

    def test_mean_empty_raises(self):
        with self.assertRaises(ValueError):
            mean([])

    def test_median_odd(self):
        self.assertEqual(median([3, 1, 2]), 2)

    def test_median_even(self):
        self.assertEqual(median([4, 1, 3, 2]), 2.5)

    def test_percentile(self):
        self.assertEqual(percentile(list(range(1, 101)), 99), 99)


if __name__ == "__main__":
    unittest.main()
