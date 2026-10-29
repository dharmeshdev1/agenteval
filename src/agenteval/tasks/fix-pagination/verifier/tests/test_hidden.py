import unittest
from paginate import paginate, page_count


class Hidden(unittest.TestCase):
    def test_middle_and_last_partial_page(self):
        items = list(range(1, 11))
        self.assertEqual(paginate(items, 2, 3), [4, 5, 6])
        self.assertEqual(paginate(items, 4, 3), [10])

    def test_past_the_end_is_empty(self):
        self.assertEqual(paginate([1, 2, 3], 2, 5), [])
        self.assertEqual(paginate([], 1, 5), [])

    def test_invalid_arguments(self):
        for page, per in ((0, 5), (-1, 5), (1, 0), (1, -3)):
            with self.assertRaises(ValueError):
                paginate([1, 2, 3], page, per)

    def test_page_count_rounds_up(self):
        self.assertEqual(page_count(11, 5), 3)
        self.assertEqual(page_count(1, 5), 1)
        self.assertEqual(page_count(0, 5), 0)

    def test_page_count_invalid(self):
        with self.assertRaises(ValueError):
            page_count(10, 0)

    def test_does_not_mutate_input(self):
        items = [1, 2, 3, 4]
        paginate(items, 1, 2)
        self.assertEqual(items, [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
