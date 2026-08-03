"""
Tests for data_juicer/ops/fused_batch_executor.py and
data_juicer/ops/fused_sequential_batch_op.py
"""

import unittest
from copy import deepcopy

from data_juicer.ops.base_op import OPERATORS, Filter, Mapper
from data_juicer.ops.fused_batch_executor import (
    SequentialBatchExecutionPolicy,
    _ensure_dict_column,
    _validate_batch,
    execute_sequential_batch,
    get_batch_size,
)
from data_juicer.ops.fused_sequential_batch_op import FusedSequentialBatchOp
from data_juicer.utils.constant import Fields
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


# ---------------------------------------------------------------------------
# Concrete test operators (no mocks)
# ---------------------------------------------------------------------------


class _TestUpperMapper(Mapper):
    """Simple mapper that uppercases text."""

    _name = 'test_upper_mapper'
    _batched_op = True

    def process_batched(self, samples, **kwargs):
        samples['text'] = [t.upper() for t in samples['text']]
        return samples


class _TestAppendMapper(Mapper):
    """Mapper that appends a suffix to text."""

    _name = 'test_append_mapper'
    _batched_op = True

    def __init__(self, suffix='_done', **kwargs):
        super().__init__(**kwargs)
        self.suffix = suffix

    def process_batched(self, samples, **kwargs):
        samples['text'] = [t + self.suffix for t in samples['text']]
        return samples


class _TestLengthFilter(Filter):
    """Filter that keeps samples with text length >= min_len."""

    _name = 'test_length_filter'
    _batched_op = True

    def __init__(self, min_len=5, **kwargs):
        super().__init__(**kwargs)
        self.min_len = min_len

    def compute_stats_batched(self, samples, **kwargs):
        if Fields.stats not in samples:
            samples[Fields.stats] = [{} for _ in samples['text']]
        for i, t in enumerate(samples['text']):
            samples[Fields.stats][i]['text_len'] = len(t)
        return samples

    def process_batched(self, samples):
        return [
            s.get('text_len', 0) >= self.min_len
            for s in samples[Fields.stats]
        ]


class _TestNoneReturningMapper(Mapper):
    """Mapper that returns None (broken op for validation testing)."""

    _name = 'test_none_mapper'
    _batched_op = True

    def process_batched(self, samples, **kwargs):
        return None


class _TestListReturningMapper(Mapper):
    """Mapper that returns a list instead of dict (broken op)."""

    _name = 'test_list_mapper'
    _batched_op = True

    def process_batched(self, samples, **kwargs):
        return [samples]


class _TestUnsupportedOp:
    """An object that is neither Mapper nor Filter."""

    _name = 'test_unsupported_op'


# ---------------------------------------------------------------------------
# Test: get_batch_size
# ---------------------------------------------------------------------------


class GetBatchSizeTest(DataJuicerTestCaseBase):
    def test_none_returns_zero(self):
        self.assertEqual(get_batch_size(None), 0)

    def test_empty_dict_returns_zero(self):
        self.assertEqual(get_batch_size({}), 0)

    def test_normal_dict_returns_correct_count(self):
        samples = {'text': ['hello', 'world', 'foo'], 'id': [1, 2, 3]}
        self.assertEqual(get_batch_size(samples), 3)

    def test_single_element(self):
        samples = {'text': ['single']}
        self.assertEqual(get_batch_size(samples), 1)

    def test_empty_list_column(self):
        samples = {'text': []}
        self.assertEqual(get_batch_size(samples), 0)


# ---------------------------------------------------------------------------
# Test: _validate_batch
# ---------------------------------------------------------------------------


class ValidateBatchTest(DataJuicerTestCaseBase):
    def _make_dummy_op(self):
        return _TestUpperMapper()

    def test_none_result_raises(self):
        op = self._make_dummy_op()
        with self.assertRaises(ValueError) as ctx:
            _validate_batch(None, op, 'test_owner', 'process', validate=True)
        self.assertIn('returned None', str(ctx.exception))

    def test_non_dict_raises_when_validate_true(self):
        op = self._make_dummy_op()
        with self.assertRaises(ValueError) as ctx:
            _validate_batch(['not', 'a', 'dict'], op, 'test_owner',
                            'process', validate=True)
        self.assertIn('unsupported batch type', str(ctx.exception))

    def test_non_dict_passes_when_validate_false(self):
        op = self._make_dummy_op()
        result = _validate_batch(['not', 'a', 'dict'], op, 'test_owner',
                                 'process', validate=False)
        self.assertEqual(result, ['not', 'a', 'dict'])

    def test_dict_passes(self):
        op = self._make_dummy_op()
        batch = {'text': ['hello']}
        result = _validate_batch(batch, op, 'test_owner', 'process',
                                 validate=True)
        self.assertEqual(result, batch)


# ---------------------------------------------------------------------------
# Test: _ensure_dict_column
# ---------------------------------------------------------------------------


class EnsureDictColumnTest(DataJuicerTestCaseBase):
    def _make_dummy_op(self):
        return _TestUpperMapper()

    def test_creates_column_when_missing(self):
        op = self._make_dummy_op()
        samples = {'text': ['a', 'b', 'c']}
        result = _ensure_dict_column(samples, Fields.stats, op, 'test')
        self.assertIn(Fields.stats, result)
        self.assertEqual(len(result[Fields.stats]), 3)
        self.assertEqual(result[Fields.stats], [{}, {}, {}])

    def test_creates_column_when_empty_list(self):
        op = self._make_dummy_op()
        samples = {'text': ['a', 'b'], Fields.stats: []}
        result = _ensure_dict_column(samples, Fields.stats, op, 'test')
        self.assertEqual(len(result[Fields.stats]), 2)

    def test_fills_none_entries(self):
        op = self._make_dummy_op()
        samples = {'text': ['a', 'b', 'c'],
                   Fields.stats: [{'x': 1}, None, {'y': 2}]}
        result = _ensure_dict_column(samples, Fields.stats, op, 'test')
        self.assertEqual(result[Fields.stats][0], {'x': 1})
        self.assertEqual(result[Fields.stats][1], {})
        self.assertEqual(result[Fields.stats][2], {'y': 2})

    def test_raises_on_length_mismatch(self):
        op = self._make_dummy_op()
        samples = {'text': ['a', 'b', 'c'],
                   Fields.stats: [{}, {}]}
        with self.assertRaises(ValueError) as ctx:
            _ensure_dict_column(samples, Fields.stats, op, 'test')
        self.assertIn('length', str(ctx.exception))


# ---------------------------------------------------------------------------
# Test: execute_sequential_batch
# ---------------------------------------------------------------------------


class ExecuteSequentialBatchTest(DataJuicerTestCaseBase):
    def _default_policy(self, **overrides):
        defaults = dict(
            copy_input=False,
            shared_context=False,
            use_op_wrappers=False,
            validate=True,
            ensure_fields=True,
        )
        defaults.update(overrides)
        return SequentialBatchExecutionPolicy(**defaults)

    def test_single_mapper_transforms_text(self):
        samples = {'text': ['hello', 'world']}
        ops = [_TestUpperMapper()]
        policy = self._default_policy()
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        self.assertEqual(result['text'], ['HELLO', 'WORLD'])

    def test_two_mappers_chained(self):
        samples = {'text': ['hi', 'there']}
        ops = [_TestUpperMapper(), _TestAppendMapper(suffix='!')]
        policy = self._default_policy()
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        self.assertEqual(result['text'], ['HI!', 'THERE!'])

    def test_filter_removes_rows(self):
        # min_len=5, so 'hi' (len=2) is removed, 'hello' (len=5) kept
        samples = {'text': ['hi', 'hello', 'world!'],
                   Fields.stats: [{}, {}, {}]}
        ops = [_TestLengthFilter(min_len=5)]
        policy = self._default_policy()
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        self.assertEqual(result['text'], ['hello', 'world!'])

    def test_mapper_then_filter_chain(self):
        # uppercase first, then filter by length >= 4
        samples = {'text': ['hi', 'hey', 'hello']}
        ops = [_TestUpperMapper(), _TestLengthFilter(min_len=4)]
        policy = self._default_policy()
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        # After upper: ['HI', 'HEY', 'HELLO']
        # Filter len>=4: only 'HELLO' (len=5) passes
        self.assertEqual(result['text'], ['HELLO'])

    def test_unsupported_op_type_raises(self):
        samples = {'text': ['hello']}
        ops = [_TestUnsupportedOp()]
        policy = self._default_policy()
        with self.assertRaises(NotImplementedError) as ctx:
            execute_sequential_batch(
                samples, ops, owner_name='test', policy=policy,
                cleanup_columns=None, on_op_complete=None)
        self.assertIn('does not support op', str(ctx.exception))

    def test_on_op_complete_callback_called(self):
        samples = {'text': ['hello', 'world']}
        ops = [_TestUpperMapper(), _TestAppendMapper(suffix='!')]
        policy = self._default_policy()
        callback_calls = []

        def on_complete(op, wall_ms):
            callback_calls.append((op._name, wall_ms))

        execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=on_complete)
        self.assertEqual(len(callback_calls), 2)
        self.assertEqual(callback_calls[0][0], 'test_upper_mapper')
        self.assertEqual(callback_calls[1][0], 'test_append_mapper')
        # wall_ms should be a positive float
        self.assertGreater(callback_calls[0][1], 0)
        self.assertGreater(callback_calls[1][1], 0)

    def test_copy_input_policy_does_not_mutate_original(self):
        samples = {'text': ['hello', 'world']}
        original_samples = deepcopy(samples)
        ops = [_TestUpperMapper()]
        policy = self._default_policy(copy_input=True)
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        # original should be unchanged
        self.assertEqual(samples, original_samples)
        # result should be transformed
        self.assertEqual(result['text'], ['HELLO', 'WORLD'])

    def test_no_copy_input_mutates_original(self):
        samples = {'text': ['hello', 'world']}
        ops = [_TestUpperMapper()]
        policy = self._default_policy(copy_input=False)
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        # original is mutated since copy_input=False
        self.assertEqual(samples['text'], ['HELLO', 'WORLD'])
        self.assertIs(result, samples)

    def test_empty_batch_after_filter_stops_early(self):
        # When a filter removes all rows, subsequent ops are skipped
        samples = {'text': ['hi', 'yo'],
                   Fields.stats: [{}, {}]}
        ops = [_TestLengthFilter(min_len=100), _TestUpperMapper()]
        policy = self._default_policy()
        callback_calls = []

        def on_complete(op, wall_ms):
            callback_calls.append(op._name)

        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=on_complete)
        # All rows removed, batch is empty
        self.assertEqual(get_batch_size(result), 0)
        # Only the filter ran, mapper was skipped
        self.assertEqual(callback_calls, ['test_length_filter'])

    def test_empty_columns_batch_returns_immediately(self):
        samples = {'text': []}
        ops = [_TestUpperMapper()]
        policy = self._default_policy()
        callback_calls = []

        def on_complete(op, wall_ms):
            callback_calls.append(op._name)

        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=on_complete)
        self.assertEqual(result['text'], [])

    def test_cleanup_columns_removes_specified_columns(self):
        samples = {'text': ['hello'], 'extra': ['remove_me']}
        ops = [_TestUpperMapper()]
        policy = self._default_policy()
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=['extra'], on_op_complete=None)
        self.assertEqual(result['text'], ['HELLO'])
        self.assertNotIn('extra', result)

    def test_cleanup_columns_nonexistent_column_no_error(self):
        samples = {'text': ['hello']}
        ops = [_TestUpperMapper()]
        policy = self._default_policy()
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=['nonexistent'], on_op_complete=None)
        self.assertEqual(result['text'], ['HELLO'])

    def test_shared_context_adds_and_removes_context_column(self):
        samples = {'text': ['hello', 'world']}
        ops = [_TestUpperMapper()]
        policy = self._default_policy(shared_context=True)
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        # context should be removed at the end
        self.assertNotIn(Fields.context, result)
        self.assertEqual(result['text'], ['HELLO', 'WORLD'])

    def test_filter_all_removed_stops_early(self):
        # All samples shorter than 100 chars, so filter removes everything
        samples = {'text': ['hi', 'yo', 'ok'],
                   Fields.stats: [{}, {}, {}]}
        ops = [_TestLengthFilter(min_len=100), _TestUpperMapper()]
        policy = self._default_policy()
        callback_calls = []

        def on_complete(op, wall_ms):
            callback_calls.append(op._name)

        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=on_complete)
        # All rows removed by filter, second op should not run
        self.assertEqual(get_batch_size(result), 0)
        # Only the filter callback was called (stops early after empty)
        self.assertEqual(len(callback_calls), 1)
        self.assertEqual(callback_calls[0], 'test_length_filter')

    def test_none_returning_mapper_raises(self):
        samples = {'text': ['hello']}
        ops = [_TestNoneReturningMapper()]
        policy = self._default_policy()
        with self.assertRaises(ValueError) as ctx:
            execute_sequential_batch(
                samples, ops, owner_name='test', policy=policy,
                cleanup_columns=None, on_op_complete=None)
        self.assertIn('returned None', str(ctx.exception))

    def test_list_returning_mapper_raises_when_validate_true(self):
        samples = {'text': ['hello']}
        ops = [_TestListReturningMapper()]
        policy = self._default_policy(validate=True)
        with self.assertRaises(ValueError) as ctx:
            execute_sequential_batch(
                samples, ops, owner_name='test', policy=policy,
                cleanup_columns=None, on_op_complete=None)
        self.assertIn('unsupported batch type', str(ctx.exception))

    def test_ensure_fields_false_skips_meta_stats_creation(self):
        # When ensure_fields=False, stats column is not auto-created
        # The filter itself adds stats in compute_stats_batched, so this
        # should still work
        samples = {'text': ['hello', 'hi']}
        ops = [_TestLengthFilter(min_len=4)]
        policy = self._default_policy(ensure_fields=False)
        result = execute_sequential_batch(
            samples, ops, owner_name='test', policy=policy,
            cleanup_columns=None, on_op_complete=None)
        self.assertEqual(result['text'], ['hello'])


# ---------------------------------------------------------------------------
# Test: FusedSequentialBatchOp
# ---------------------------------------------------------------------------


class FusedSequentialBatchOpTest(DataJuicerTestCaseBase):
    def test_init_with_fused_ops(self):
        ops = [_TestUpperMapper(), _TestAppendMapper(suffix='!')]
        fused = FusedSequentialBatchOp(fused_ops=ops, group_name='test_group')
        self.assertEqual(fused.group_name, 'test_group')
        self.assertIsNotNone(fused._fused_ops_input)
        self.assertEqual(len(fused._fused_ops_input), 2)

    def test_init_with_op_specs(self):
        specs = [
            {'class_name': 'text_length_filter', 'kwargs': {'min_len': 3}},
        ]
        fused = FusedSequentialBatchOp(op_specs=specs, group_name='spec_test')
        self.assertEqual(len(fused.op_specs), 1)
        self.assertIsNone(fused._fused_ops_input)

    def test_both_fused_ops_and_op_specs_raises_valueerror(self):
        ops = [_TestUpperMapper()]
        specs = [{'class_name': 'text_length_filter', 'kwargs': {}}]
        with self.assertRaises(ValueError) as ctx:
            FusedSequentialBatchOp(fused_ops=ops, op_specs=specs)
        self.assertIn('not both', str(ctx.exception))

    def test_process_batched_with_fused_ops(self):
        ops = [_TestUpperMapper(), _TestAppendMapper(suffix='!')]
        fused = FusedSequentialBatchOp(fused_ops=ops, group_name='test')
        samples = {'text': ['hello', 'world']}
        result = fused.process_batched(samples)
        self.assertEqual(result['text'], ['HELLO!', 'WORLD!'])

    def test_process_batched_with_op_specs(self):
        # Use a real registered op from the registry
        specs = [
            {'class_name': 'text_length_filter',
             'kwargs': {'min_len': 4, 'max_len': 100}},
        ]
        fused = FusedSequentialBatchOp(op_specs=specs, group_name='spec_run')
        samples = {'text': ['hi', 'hello', 'hey', 'wonderful']}
        result = fused.process_batched(samples)
        # 'hi' (2) and 'hey' (3) are < 4, removed
        self.assertEqual(result['text'], ['hello', 'wonderful'])

    def test_process_batched_empty_samples(self):
        ops = [_TestUpperMapper()]
        fused = FusedSequentialBatchOp(fused_ops=ops, group_name='test')
        samples = {'text': []}
        result = fused.process_batched(samples)
        self.assertEqual(result['text'], [])

    def test_process_batched_no_ops(self):
        fused = FusedSequentialBatchOp(fused_ops=[], group_name='empty')
        samples = {'text': ['hello']}
        result = fused.process_batched(samples)
        self.assertEqual(result['text'], ['hello'])

    def test_cleanup_columns(self):
        ops = [_TestUpperMapper()]
        fused = FusedSequentialBatchOp(
            fused_ops=ops, group_name='test',
            cleanup_columns=['temp_col'])
        samples = {'text': ['hello'], 'temp_col': ['remove_me']}
        result = fused.process_batched(samples)
        self.assertEqual(result['text'], ['HELLO'])
        self.assertNotIn('temp_col', result)

    def test_invalid_op_spec_class_name_raises(self):
        specs = [{'class_name': 'nonexistent_op_xyz', 'kwargs': {}}]
        fused = FusedSequentialBatchOp(op_specs=specs, group_name='bad')
        with self.assertRaises(ValueError) as ctx:
            fused.process_batched({'text': ['hello']})
        self.assertIn('not found', str(ctx.exception))

    def test_op_spec_missing_class_name_raises(self):
        specs = [{'kwargs': {'min_len': 5}}]
        fused = FusedSequentialBatchOp(op_specs=specs, group_name='bad')
        with self.assertRaises(ValueError) as ctx:
            fused.process_batched({'text': ['hello']})
        self.assertIn("missing 'class_name'", str(ctx.exception))

    def test_mapper_filter_chain_in_fused_op(self):
        ops = [_TestUpperMapper(), _TestLengthFilter(min_len=4)]
        fused = FusedSequentialBatchOp(fused_ops=ops, group_name='chain')
        samples = {'text': ['hi', 'hey', 'hello', 'wonderful']}
        result = fused.process_batched(samples)
        # After upper: ['HI', 'HEY', 'HELLO', 'WONDERFUL']
        # Filter >= 4: 'HELLO' (5), 'WONDERFUL' (9) kept
        self.assertEqual(result['text'], ['HELLO', 'WONDERFUL'])

    def test_is_batched_op(self):
        fused = FusedSequentialBatchOp(fused_ops=[], group_name='test')
        self.assertTrue(fused._batched_op)


# ---------------------------------------------------------------------------
# Test: SequentialBatchExecutionPolicy defaults
# ---------------------------------------------------------------------------


class SequentialBatchExecutionPolicyTest(DataJuicerTestCaseBase):
    def test_default_values(self):
        policy = SequentialBatchExecutionPolicy()
        self.assertFalse(policy.copy_input)
        self.assertFalse(policy.shared_context)
        self.assertTrue(policy.use_op_wrappers)
        self.assertTrue(policy.validate)
        self.assertTrue(policy.ensure_fields)

    def test_frozen_raises_on_mutation(self):
        policy = SequentialBatchExecutionPolicy()
        with self.assertRaises(Exception):
            policy.copy_input = True


if __name__ == '__main__':
    unittest.main()
