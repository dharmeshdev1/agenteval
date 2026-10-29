import copy
import unittest
from config_merge import merge


class Hidden(unittest.TestCase):
    def test_nested_merge(self):
        base = {"db": {"host": "a", "port": 1}, "debug": False}
        over = {"db": {"port": 2}, "extra": True}
        self.assertEqual(merge(base, over),
                         {"db": {"host": "a", "port": 2}, "debug": False, "extra": True})

    def test_lists_are_replaced(self):
        self.assertEqual(merge({"x": [1, 2, 3]}, {"x": [9]}), {"x": [9]})

    def test_none_removes_a_key(self):
        self.assertEqual(merge({"a": 1, "b": 2}, {"a": None}), {"b": 2})

    def test_none_for_a_missing_key_adds_nothing(self):
        self.assertEqual(merge({"a": 1}, {"zzz": None}), {"a": 1})

    def test_none_removes_a_nested_key(self):
        self.assertEqual(merge({"d": {"x": 1, "y": 2}}, {"d": {"x": None}}), {"d": {"y": 2}})

    def test_dict_replaced_by_scalar_and_back(self):
        self.assertEqual(merge({"a": {"b": 1}}, {"a": 5}), {"a": 5})
        self.assertEqual(merge({"a": 5}, {"a": {"b": 1}}), {"a": {"b": 1}})

    def test_falsy_scalars_still_override(self):
        self.assertEqual(merge({"a": 5, "b": "x", "c": True}, {"a": 0, "b": "", "c": False}),
                         {"a": 0, "b": "", "c": False})

    def test_inputs_are_not_modified(self):
        base = {"a": {"b": [1, 2]}, "c": 1}
        over = {"a": {"d": 2}, "c": 2}
        b0, o0 = copy.deepcopy(base), copy.deepcopy(over)
        merge(base, over)
        self.assertEqual(base, b0)
        self.assertEqual(over, o0)

    def test_result_shares_nothing_with_inputs(self):
        base = {"a": {"b": [1]}, "keep": {"k": [1]}}
        over = {"new": {"n": [2]}}
        result = merge(base, over)
        result["a"]["b"].append(99)
        result["keep"]["k"].append(99)
        result["new"]["n"].append(99)
        self.assertEqual(base, {"a": {"b": [1]}, "keep": {"k": [1]}})
        self.assertEqual(over, {"new": {"n": [2]}})

    def test_empty_inputs(self):
        self.assertEqual(merge({}, {}), {})
        self.assertEqual(merge({"a": 1}, {}), {"a": 1})
        self.assertEqual(merge({}, {"a": 1}), {"a": 1})

    def test_deeply_nested(self):
        base = {"a": {"b": {"c": {"d": 1, "e": 2}}}}
        over = {"a": {"b": {"c": {"d": 9}}}}
        self.assertEqual(merge(base, over), {"a": {"b": {"c": {"d": 9, "e": 2}}}})


if __name__ == "__main__":
    unittest.main()
