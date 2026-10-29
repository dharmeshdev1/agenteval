import unittest
from cart import Cart, merge_carts


class VisibleTests(unittest.TestCase):
    def test_add_and_total(self):
        c = Cart()
        c.add("apple", 2)
        c.add("pear")
        self.assertEqual(c.total_quantity(), 3)


if __name__ == "__main__":
    unittest.main()
