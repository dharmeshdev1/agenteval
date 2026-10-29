import unittest
from shop import pricing
from shop.pricing import compute_price, recalc_price_cache
from shop.cart import Cart
from shop.report import summary


class Hidden(unittest.TestCase):
    def test_new_name_works_and_old_name_is_gone(self):
        self.assertEqual(compute_price(2.5, 4), 10.0)
        self.assertEqual(compute_price(10, 3, 0.1), 27.0)
        self.assertFalse(hasattr(pricing, "calc_price"))

    def test_similar_name_is_untouched(self):
        self.assertEqual(recalc_price_cache({}, 2.0, 5), {(2.0, 5): 10.0})
        self.assertFalse(hasattr(pricing, "recompute_price_cache"))

    def test_cart_and_report_still_work(self):
        c = Cart()
        c.add(2.0, 3)
        c.add(10, 1, 0.5)
        self.assertEqual(c.total(), 11.0)
        self.assertEqual(summary([("a", 1.5, 2), ("b", 4, 1)]), {"a": 3.0, "b": 4.0})


if __name__ == "__main__":
    unittest.main()
