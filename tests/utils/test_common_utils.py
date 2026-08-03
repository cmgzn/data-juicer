import hashlib
import sys
import unittest
import warnings

import numpy as np

from data_juicer.utils.common_utils import (
    avg_split_string_list_under_limit,
    check_op_method_param,
    deprecated,
    dict_to_hash,
    is_float,
    is_string_list,
    nested_access,
    stats_to_number,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class StatsToNumberTest(DataJuicerTestCaseBase):

    def test_string_number(self):
        self.assertEqual(stats_to_number("3.14"), 3.14)

    def test_integer_string(self):
        self.assertEqual(stats_to_number("42"), 42.0)

    def test_none_reverse_true(self):
        self.assertEqual(stats_to_number(None, reverse=True), -sys.maxsize)

    def test_none_reverse_false(self):
        self.assertEqual(stats_to_number(None, reverse=False), sys.maxsize)

    def test_empty_list_reverse_true(self):
        self.assertEqual(stats_to_number([], reverse=True), -sys.maxsize)

    def test_empty_list_reverse_false(self):
        self.assertEqual(stats_to_number([], reverse=False), sys.maxsize)

    def test_list_of_numbers(self):
        self.assertAlmostEqual(stats_to_number([1, 2, 3]), 2.0)

    def test_single_element_list(self):
        self.assertEqual(stats_to_number([5.0]), 5.0)

    def test_numpy_array(self):
        self.assertAlmostEqual(stats_to_number(np.array([10, 20])), 15.0)

    def test_plain_float(self):
        self.assertEqual(stats_to_number(7.5), 7.5)

    def test_plain_int(self):
        self.assertEqual(stats_to_number(3), 3.0)


@TEST_TAG("standalone")
class DictToHashTest(DataJuicerTestCaseBase):

    def test_basic_hash(self):
        d = {"a": 1, "b": 2}
        result = dict_to_hash(d)
        expected = hashlib.sha256(str(sorted(d.items())).encode()).hexdigest()
        self.assertEqual(result, expected)

    def test_hash_length(self):
        d = {"key": "value"}
        result = dict_to_hash(d, hash_length=8)
        self.assertEqual(len(result), 8)

    def test_order_independent(self):
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 2, "a": 1}
        self.assertEqual(dict_to_hash(d1), dict_to_hash(d2))

    def test_different_dicts_differ(self):
        self.assertNotEqual(dict_to_hash({"a": 1}), dict_to_hash({"a": 2}))

    def test_empty_dict(self):
        result = dict_to_hash({})
        self.assertEqual(len(result), 64)


@TEST_TAG("standalone")
class NestedAccessTest(DataJuicerTestCaseBase):

    def test_simple_dict(self):
        self.assertEqual(nested_access({"a": 1}, "a"), 1)

    def test_nested_dict(self):
        data = {"a": {"b": {"c": 42}}}
        self.assertEqual(nested_access(data, "a.b.c"), 42)

    def test_list_index(self):
        data = {"items": [10, 20, 30]}
        self.assertEqual(nested_access(data, "items.1"), 20)

    def test_digit_allowed_false(self):
        data = {"0": "zero", "1": "one"}
        self.assertEqual(nested_access(data, "0", digit_allowed=False), "zero")

    def test_missing_key_returns_none(self):
        self.assertIsNone(nested_access({"a": 1}, "b"))

    def test_deeply_missing_returns_none(self):
        self.assertIsNone(nested_access({"a": {"b": 1}}, "a.c.d"))

    def test_mixed_dict_list(self):
        data = {"users": [{"name": "Alice"}, {"name": "Bob"}]}
        self.assertEqual(nested_access(data, "users.1.name"), "Bob")


@TEST_TAG("standalone")
class IsStringListTest(DataJuicerTestCaseBase):

    def test_valid_string_list(self):
        self.assertTrue(is_string_list(["a", "b", "c"]))

    def test_empty_list(self):
        self.assertTrue(is_string_list([]))

    def test_mixed_types(self):
        self.assertFalse(is_string_list(["a", 1]))

    def test_not_a_list(self):
        self.assertFalse(is_string_list("hello"))

    def test_none(self):
        self.assertFalse(is_string_list(None))

    def test_int_list(self):
        self.assertFalse(is_string_list([1, 2, 3]))


@TEST_TAG("standalone")
class AvgSplitStringListTest(DataJuicerTestCaseBase):

    def test_no_max_returns_single_group(self):
        result = avg_split_string_list_under_limit(["a", "b"], [5, 5])
        self.assertEqual(result, [["a", "b"]])

    def test_total_under_limit(self):
        result = avg_split_string_list_under_limit(["a", "b"], [3, 3], max_token_num=10)
        self.assertEqual(result, [["a", "b"]])

    def test_splits_when_over_limit(self):
        result = avg_split_string_list_under_limit(
            ["a", "b", "c", "d"], [5, 5, 5, 5], max_token_num=10
        )
        total_items = sum(len(g) for g in result)
        self.assertEqual(total_items, 4)
        for group in result:
            self.assertTrue(len(group) > 0)

    def test_mismatched_lengths_returns_single(self):
        result = avg_split_string_list_under_limit(["a", "b"], [5], max_token_num=3)
        self.assertEqual(result, [["a", "b"]])

    def test_single_item_exceeding_limit(self):
        result = avg_split_string_list_under_limit(["big"], [100], max_token_num=10)
        self.assertEqual(result, [["big"]])

    def test_even_split(self):
        result = avg_split_string_list_under_limit(
            ["a", "b", "c", "d"], [10, 10, 10, 10], max_token_num=20
        )
        self.assertTrue(len(result) >= 2)


@TEST_TAG("standalone")
class IsFloatTest(DataJuicerTestCaseBase):

    def test_valid_float_string(self):
        self.assertTrue(is_float("3.14"))

    def test_valid_int_string(self):
        self.assertTrue(is_float("42"))

    def test_negative(self):
        self.assertTrue(is_float("-1.5"))

    def test_scientific(self):
        self.assertTrue(is_float("1e10"))

    def test_invalid_string(self):
        self.assertFalse(is_float("hello"))

    def test_empty_string(self):
        self.assertFalse(is_float(""))

    def test_none(self):
        self.assertFalse(is_float(None))


@TEST_TAG("standalone")
class CheckOpMethodParamTest(DataJuicerTestCaseBase):

    def test_has_named_param(self):
        def foo(x, y, z):
            pass
        self.assertTrue(check_op_method_param(foo, "y"))

    def test_missing_param(self):
        def foo(x, y):
            pass
        self.assertFalse(check_op_method_param(foo, "z"))

    def test_var_keyword(self):
        def foo(x, **kwargs):
            pass
        self.assertTrue(check_op_method_param(foo, "anything"))

    def test_no_params(self):
        def foo():
            pass
        self.assertFalse(check_op_method_param(foo, "x"))


@TEST_TAG("standalone")
class DeprecatedDecoratorTest(DataJuicerTestCaseBase):

    def test_bare_decorator(self):
        @deprecated
        def old_func():
            return 42

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_func()
            self.assertEqual(result, 42)
            self.assertEqual(len(w), 1)
            self.assertIn("deprecated", str(w[0].message).lower())

    def test_with_reason(self):
        @deprecated("Use new_func instead")
        def old_func():
            return 1

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()
            self.assertIn("Use new_func instead", str(w[0].message))

    def test_with_version(self):
        @deprecated(reason="outdated", version="2.0")
        def old_func():
            return 1

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            old_func()
            self.assertIn("2.0", str(w[0].message))

    def test_preserves_function_name(self):
        @deprecated("reason")
        def my_func():
            pass
        self.assertEqual(my_func.__name__, "my_func")

    def test_invalid_reason_type(self):
        with self.assertRaises(TypeError):
            @deprecated(reason=123)
            def f():
                pass

    def test_invalid_version_type(self):
        with self.assertRaises(TypeError):
            @deprecated(reason="x", version=123)
            def f():
                pass

    def test_with_version_only(self):
        @deprecated(version="1.0")
        def f():
            return 99

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = f()
            self.assertEqual(result, 99)
            self.assertIn("1.0", str(w[0].message))


if __name__ == "__main__":
    unittest.main()
