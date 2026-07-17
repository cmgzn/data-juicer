import copy
import unittest

import numpy as np

from data_juicer.ops.base_op import Filter, Mapper, OP
from data_juicer.ops.filter import AverageLineLengthFilter
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class RemoveExtraParametersTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.op = AverageLineLengthFilter()

    def test_removes_underscored_keys(self):
        params = {'_internal': 1, 'public': 2, '__dunder': 3}
        result = self.op.remove_extra_parameters(params)
        self.assertNotIn('_internal', result)
        self.assertNotIn('__dunder', result)
        self.assertIn('public', result)

    def test_removes_self(self):
        params = {'self': 'x', 'a': 1, 'b': 2}
        result = self.op.remove_extra_parameters(params)
        self.assertNotIn('self', result)
        self.assertIn('a', result)

    def test_custom_keys(self):
        params = {'a': 1, 'b': 2, 'c': 3}
        result = self.op.remove_extra_parameters(params, keys=['b', 'c'])
        self.assertIn('a', result)
        self.assertNotIn('b', result)
        self.assertNotIn('c', result)


class AddParametersTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.op = AverageLineLengthFilter()

    def test_merge(self):
        init = {'a': 1, 'b': 2}
        result = self.op.add_parameters(init, c=3, d=4)
        self.assertEqual(result, {'a': 1, 'b': 2, 'c': 3, 'd': 4})

    def test_deep_copy(self):
        init = {'nested': [1, 2, 3]}
        result = self.op.add_parameters(init, extra=True)
        result['nested'].append(4)
        self.assertEqual(len(init['nested']), 3)


class IsBatchedOpTest(DataJuicerTestCaseBase):

    def test_batched_op_returns_true(self):
        op = AverageLineLengthFilter()
        self.assertTrue(op.is_batched_op())

    def test_batch_mode_false_on_batched_op_raises(self):
        op = AverageLineLengthFilter()
        op.batch_mode = False
        with self.assertRaises(ValueError):
            op.is_batched_op()


class EmptyHistoryTest(DataJuicerTestCaseBase):

    def test_returns_numpy_array(self):
        op = AverageLineLengthFilter()
        result = op.empty_history()
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.shape, (0, 0))


class MapperInitSubclassTest(DataJuicerTestCaseBase):

    def test_cannot_override_process(self):
        with self.assertRaises(TypeError):
            class BadMapper(Mapper):
                def process(self, sample):
                    return sample


class FilterInitSubclassTest(DataJuicerTestCaseBase):

    def test_cannot_override_compute_stats(self):
        with self.assertRaises(TypeError):
            class BadFilter(Filter):
                def compute_stats(self, sample):
                    return sample

    def test_cannot_override_process(self):
        with self.assertRaises(TypeError):
            class BadFilter2(Filter):
                def process(self, sample):
                    return sample


class BaseOPTest(DataJuicerTestCaseBase):

    def test_filter_get_keep_boolean(self):
        # test cases with tuple (min_closed_interval, max_closed_interval, reversed_range, val, min_val, max_val, tgt)
        test_cases = [
            # normal ranges
            (True, True, False, 5, 1, 10, True),
            (True, True, False, 5, None, 10, True),
            (True, True, False, 5, 1, None, True),
            (True, True, False, 5, None, None, True),
            # marginal cases
            (True, True, False, 5, 1, 5, True),
            (True, True, False, 5, 5, 10, True),
            (True, True, False, 5, 5, 5, True),
            (True, True, False, 5, 1, 4, False),
            (True, True, False, 5, 6, 10, False),
            # open intervals
            (True, False, False, 5, 1, 10, True),
            (True, False, False, 5, 5, 10, True),
            (True, False, False, 5, 1, 5, False),
            (False, True, False, 5, 1, 10, True),
            (False, True, False, 5, 5, 10, False),
            (False, True, False, 5, 1, 5, True),
            # reversed ranges
            (True, True, True, 5, 1, 10, False),
            (True, True, True, 5, None, 10, False),
            (True, True, True, 5, 1, None, False),
            (True, True, True, 5, None, None, False),
            (True, True, True, 5, 1, 5, True),
            (True, True, True, 5, 5, 10, True),
            (True, True, True, 5, 5, 5, True),
            (False, True, True, 5, 1, 5, True),
            (False, True, True, 5, 5, 10, False),
            (False, True, True, 5, 5, 5, True),
            (True, False, True, 5, 1, 5, False),
            (True, False, True, 5, 5, 10, True),
            (True, False, True, 5, 5, 5, True),
            (False, False, True, 5, 1, 5, False),
            (False, False, True, 5, 5, 10, False),
            (False, False, True, 5, 5, 5, False),
        ]
        for tc in test_cases:
            min_closed_interval, max_closed_interval, reversed_range, val, min_val, max_val, tgt = tc
            op = AverageLineLengthFilter(min_closed_interval=min_closed_interval,
                                     max_closed_interval=max_closed_interval,
                                     reversed_range=reversed_range)
            self.assertEqual(
                op.get_keep_boolean(val, min_val, max_val), tgt)


if __name__ == '__main__':
    unittest.main()
