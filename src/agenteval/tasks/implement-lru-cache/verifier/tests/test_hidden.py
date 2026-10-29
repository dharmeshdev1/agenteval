import unittest
from lru import LRUCache


class Hidden(unittest.TestCase):
    def test_evicts_least_recently_used(self):
        c = LRUCache(2)
        c.put("a", 1); c.put("b", 2); c.put("c", 3)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)
        self.assertEqual(len(c), 2)

    def test_get_refreshes_recency(self):
        c = LRUCache(2)
        c.put("a", 1); c.put("b", 2)
        c.get("a")
        c.put("c", 3)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("b"))

    def test_update_replaces_value_and_refreshes_recency(self):
        c = LRUCache(2)
        c.put("a", 1); c.put("b", 2)
        c.put("a", 10)
        c.put("c", 3)
        self.assertEqual(c.get("a"), 10)
        self.assertIsNone(c.get("b"))
        self.assertEqual(len(c), 2)

    def test_update_does_not_grow_the_cache(self):
        c = LRUCache(2)
        for _ in range(5):
            c.put("a", 1)
        self.assertEqual(len(c), 1)

    def test_keys_order(self):
        c = LRUCache(3)
        c.put("a", 1); c.put("b", 2); c.put("c", 3)
        c.get("a")
        self.assertEqual(c.keys(), ["b", "c", "a"])

    def test_capacity_one(self):
        c = LRUCache(1)
        c.put("a", 1); c.put("b", 2)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)

    def test_invalid_capacity(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                LRUCache(bad)

    def test_falsy_values_are_stored(self):
        c = LRUCache(2)
        c.put("zero", 0)
        c.put("none", None)
        self.assertEqual(c.get("zero"), 0)
        self.assertEqual(len(c), 2)

    def test_a_missing_get_does_not_change_order_or_size(self):
        c = LRUCache(2)
        c.put("a", 1); c.put("b", 2)
        c.get("zzz")
        self.assertEqual(c.keys(), ["a", "b"])
        self.assertEqual(len(c), 2)

    def test_many_operations_stay_consistent(self):
        c = LRUCache(50)
        for i in range(1000):
            c.put(i % 70, i)
        self.assertEqual(len(c), 50)
        self.assertEqual(len(set(c.keys())), 50)


if __name__ == "__main__":
    unittest.main()
