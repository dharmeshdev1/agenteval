import unittest
from shop.pricing import calc_price, recalc_price_cache
from shop.cart import Cart


class Tests(unittest.TestCase):
    def test_price(self):
        self.assertEqual(calc_price(2.5, 4), 10.0)

    def test_cart(self):
        c = Cart()
        c.add(2.0, 3)
        self.assertEqual(c.total(), 6.0)

    def test_cache(self):
        self.assertEqual(recalc_price_cache({}, 1.0, 2), {(1.0, 2): 2.0})


if __name__ == "__main__":
    unittest.main()
