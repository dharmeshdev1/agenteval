import unittest
from config_merge import merge


class VisibleTests(unittest.TestCase):
    def test_scalar_override(self):
        self.assertEqual(merge({"a": 1}, {"a": 2}), {"a": 2})


if __name__ == "__main__":
    unittest.main()
