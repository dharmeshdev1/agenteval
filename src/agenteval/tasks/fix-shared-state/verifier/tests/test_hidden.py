import unittest
from cart import Cart, merge_carts


class Hidden(unittest.TestCase):
    def test_carts_are_independent(self):
        a, b = Cart(), Cart()
        a.add("x", 5)
        self.assertEqual(b.total_quantity(), 0)
        self.assertEqual(a.items, [("x", 5)])
        self.assertEqual(b.items, [])

    def test_merge_returns_fresh_lists(self):
        a, b = Cart(), Cart()
        a.add("x", 1)
        b.add("y", 2)
        first = merge_carts(a, b)
        second = merge_carts(a, b)
        self.assertEqual(first, [("x", 1), ("y", 2)])
        self.assertEqual(second, [("x", 1), ("y", 2)])
        self.assertIsNot(first, second)

    def test_merge_does_not_modify_inputs(self):
        a, b = Cart(), Cart()
        a.add("x", 1)
        b.add("y", 2)
        merge_carts(a, b)
        self.assertEqual(a.items, [("x", 1)])
        self.assertEqual(b.items, [("y", 2)])

    def test_merging_empty_carts(self):
        self.assertEqual(merge_carts(Cart(), Cart()), [])

    def test_merge_order_is_a_then_b(self):
        a, b = Cart(), Cart()
        a.add("a1"); a.add("a2"); b.add("b1")
        self.assertEqual([n for n, _ in merge_carts(a, b)], ["a1", "a2", "b1"])
        self.assertEqual([n for n, _ in merge_carts(b, a)], ["b1", "a1", "a2"])

    def test_mutating_a_result_does_not_affect_later_merges(self):
        a, b = Cart(), Cart()
        a.add("x")
        r = merge_carts(a, b)
        r.append(("junk", 9))
        self.assertEqual(merge_carts(a, b), [("x", 1)])


if __name__ == "__main__":
    unittest.main()
