import unittest
from graph import shortest_path


class VisibleTests(unittest.TestCase):
    def test_small(self):
        g = {"a": [("b", 1), ("c", 4)], "b": [("c", 1)], "c": []}
        self.assertEqual(shortest_path(g, "a", "c"), (2, ["a", "b", "c"]))

    def test_unreachable(self):
        self.assertEqual(shortest_path({"a": []}, "a", "z"), (None, []))


if __name__ == "__main__":
    unittest.main()
