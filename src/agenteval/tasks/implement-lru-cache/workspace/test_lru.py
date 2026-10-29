import unittest
from lru import LRUCache


class VisibleTests(unittest.TestCase):
    def test_basic(self):
        c = LRUCache(2)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("missing"))


if __name__ == "__main__":
    unittest.main()
