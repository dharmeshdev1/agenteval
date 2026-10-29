import unittest
from paginate import paginate, page_count


class VisibleTests(unittest.TestCase):
    def test_first_page(self):
        self.assertEqual(paginate([1, 2, 3, 4, 5], 1, 2), [1, 2])

    def test_exact_page_count(self):
        self.assertEqual(page_count(10, 5), 2)


if __name__ == "__main__":
    unittest.main()
