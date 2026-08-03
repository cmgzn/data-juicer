import unittest

import pyarrow as pa

from data_juicer.ops.base_op import (
    OP,
    Filter,
    Mapper,
    Deduplicator,
    Selector,
    convert_dict_list_to_list_dict,
    convert_list_dict_to_dict_list,
    convert_arrow_to_python,
    catch_map_batches_exception,
    catch_map_single_exception,
    sample_to_dict,
    DEFAULT_BATCH_SIZE,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class ConvertListDictToDictListTest(DataJuicerTestCaseBase):

    def test_basic(self):
        samples = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        result = convert_list_dict_to_dict_list(samples)
        self.assertEqual(result, {"a": [1, 3], "b": [2, 4]})

    def test_single_sample(self):
        samples = [{"x": 10}]
        result = convert_list_dict_to_dict_list(samples)
        self.assertEqual(result, {"x": [10]})

    def test_preserves_types(self):
        samples = [{"text": "hello", "score": 0.5}]
        result = convert_list_dict_to_dict_list(samples)
        self.assertEqual(result["text"], ["hello"])
        self.assertEqual(result["score"], [0.5])


@TEST_TAG("standalone")
class ConvertDictListToListDictTest(DataJuicerTestCaseBase):

    def test_basic(self):
        samples = {"a": [1, 3], "b": [2, 4]}
        result = convert_dict_list_to_list_dict(samples)
        self.assertEqual(result, [{"a": 1, "b": 2}, {"a": 3, "b": 4}])

    def test_single_sample(self):
        samples = {"x": [10]}
        result = convert_dict_list_to_list_dict(samples)
        self.assertEqual(result, [{"x": 10}])

    def test_roundtrip(self):
        original = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        roundtrip = convert_dict_list_to_list_dict(
            convert_list_dict_to_dict_list(original))
        self.assertEqual(roundtrip, original)


@TEST_TAG("standalone")
class ConvertArrowToPythonTest(DataJuicerTestCaseBase):

    def test_dict_passthrough(self):
        @convert_arrow_to_python
        def fn(sample):
            return sample

        result = fn({"a": [1]})
        self.assertEqual(result, {"a": [1]})

    def test_arrow_table_converted(self):
        @convert_arrow_to_python
        def fn(sample):
            return sample

        table = pa.table({"text": ["hello", "world"]})
        result = fn(table)
        self.assertEqual(result, {"text": ["hello", "world"]})


@TEST_TAG("standalone")
class SampleToDictTest(DataJuicerTestCaseBase):

    def test_dict_passthrough(self):
        d = {"a": 1}
        self.assertIs(sample_to_dict(d), d)

    def test_arrow_table(self):
        table = pa.table({"x": [1, 2]})
        result = sample_to_dict(table)
        self.assertEqual(result, {"x": [1, 2]})

    def test_invalid_type_raises(self):
        with self.assertRaises(ValueError):
            sample_to_dict([1, 2, 3])


@TEST_TAG("standalone")
class CatchMapBatchesExceptionTest(DataJuicerTestCaseBase):

    def test_normal_execution(self):
        def process(samples):
            return samples

        wrapped = catch_map_batches_exception(process)
        result = wrapped({"text": ["a", "b"]})
        self.assertEqual(result, {"text": ["a", "b"]})

    def test_skip_error(self):
        def process(samples):
            raise RuntimeError("boom")

        wrapped = catch_map_batches_exception(process, skip_op_error=True)
        result = wrapped({"text": ["a"], "__dj_stats__": [{}], "source_file": ["f"]})
        self.assertEqual(result["text"], [])

    def test_propagate_error_when_not_skipped(self):
        def process(samples):
            raise RuntimeError("boom")

        wrapped = catch_map_batches_exception(process, skip_op_error=False)
        with self.assertRaises(RuntimeError):
            wrapped({"text": ["a"]})

    def test_arrow_input_converted(self):
        def process(samples):
            return samples

        wrapped = catch_map_batches_exception(process)
        table = pa.table({"text": ["hi"]})
        result = wrapped(table)
        self.assertEqual(result, {"text": ["hi"]})


@TEST_TAG("standalone")
class CatchMapSingleExceptionTest(DataJuicerTestCaseBase):

    def test_non_batched_passthrough(self):
        def process(sample):
            sample["text"] = sample["text"].upper()
            return sample

        wrapped = catch_map_single_exception(process)
        result = wrapped({"text": "hello"})
        self.assertEqual(result, {"text": "HELLO"})

    def test_batched_single_item(self):
        def process(sample):
            sample["text"] = sample["text"].upper()
            return sample

        wrapped = catch_map_single_exception(process)
        result = wrapped({"text": ["hello"]})
        self.assertEqual(result, {"text": ["HELLO"]})

    def test_batched_error_skipped(self):
        def process(sample):
            raise ValueError("bad")

        wrapped = catch_map_single_exception(process, skip_op_error=True)
        result = wrapped({"text": ["x"], "__dj_stats__": [{}], "source_file": ["f"]})
        self.assertEqual(result["text"], [])

    def test_batched_error_propagated(self):
        def process(sample):
            raise ValueError("bad")

        wrapped = catch_map_single_exception(process, skip_op_error=False)
        with self.assertRaises(ValueError):
            wrapped({"text": ["x"]})


@TEST_TAG("standalone")
class OPInitTest(DataJuicerTestCaseBase):

    def test_default_attributes(self):
        op = OP()
        self.assertEqual(op.text_key, "text")
        self.assertEqual(op.image_key, "images")
        self.assertEqual(op.audio_key, "audios")
        self.assertEqual(op.video_key, "videos")
        self.assertEqual(op.accelerator, "cpu")
        self.assertEqual(op.batch_size, DEFAULT_BATCH_SIZE)
        self.assertFalse(op.skip_op_error)

    def test_custom_keys(self):
        op = OP(text_key="content", image_key="imgs")
        self.assertEqual(op.text_key, "content")
        self.assertEqual(op.image_key, "imgs")

    def test_cuda_accelerator_batch_size(self):
        op = OP(accelerator="cuda")
        self.assertEqual(op.accelerator, "cuda")
        self.assertEqual(op.batch_size, 10)

    def test_custom_batch_size(self):
        op = OP(batch_size=50)
        self.assertEqual(op.batch_size, 50)

    def test_memory_string_conversion(self):
        op = OP(memory="2GB")
        self.assertIsNotNone(op.memory)
        self.assertIsInstance(op.memory, float)

    def test_metaclass_stores_init_args(self):
        op = OP(text_key="t", batch_size=5)
        self.assertEqual(op._init_kwargs.get("text_key"), "t")
        self.assertEqual(op._init_kwargs.get("batch_size"), 5)

    def test_is_batched_op_default(self):
        op = OP()
        self.assertFalse(op.is_batched_op())

    def test_is_batched_op_explicit(self):
        op = OP(batch_mode=True)
        self.assertTrue(op.is_batched_op())

    def test_use_ray_actor_default(self):
        op = OP()
        self.assertFalse(op.use_ray_actor())

    def test_use_ray_actor_explicit(self):
        op = OP(ray_execution_mode="actor")
        self.assertTrue(op.use_ray_actor())

    def test_use_ray_task(self):
        op = OP(ray_execution_mode="task")
        self.assertFalse(op.use_ray_actor())

    def test_remove_extra_parameters(self):
        op = OP()
        params = {"self": op, "x": 1, "_private": 2, "y": 3}
        result = op.remove_extra_parameters(params)
        self.assertNotIn("self", result)
        self.assertNotIn("_private", result)
        self.assertIn("x", result)
        self.assertIn("y", result)

    def test_remove_extra_parameters_with_keys(self):
        op = OP()
        params = {"a": 1, "b": 2, "c": 3}
        result = op.remove_extra_parameters(params, keys=["b"])
        self.assertIn("a", result)
        self.assertNotIn("b", result)
        self.assertIn("c", result)

    def test_add_parameters(self):
        op = OP()
        init_dict = {"a": 1, "b": 2}
        result = op.add_parameters(init_dict, c=3)
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3})
        self.assertEqual(init_dict, {"a": 1, "b": 2})


@TEST_TAG("standalone")
class FilterGetKeepBooleanTest(DataJuicerTestCaseBase):

    def test_within_range(self):
        f = Filter()
        self.assertTrue(f.get_keep_boolean(5, min_val=1, max_val=10))

    def test_below_min(self):
        f = Filter()
        self.assertFalse(f.get_keep_boolean(0, min_val=1, max_val=10))

    def test_above_max(self):
        f = Filter()
        self.assertFalse(f.get_keep_boolean(11, min_val=1, max_val=10))

    def test_at_min_closed(self):
        f = Filter(min_closed_interval=True)
        self.assertTrue(f.get_keep_boolean(1, min_val=1))

    def test_at_min_open(self):
        f = Filter(min_closed_interval=False)
        self.assertFalse(f.get_keep_boolean(1, min_val=1))

    def test_at_max_closed(self):
        f = Filter(max_closed_interval=True)
        self.assertTrue(f.get_keep_boolean(10, max_val=10))

    def test_at_max_open(self):
        f = Filter(max_closed_interval=False)
        self.assertFalse(f.get_keep_boolean(10, max_val=10))

    def test_reversed_range(self):
        f = Filter(reversed_range=True)
        self.assertFalse(f.get_keep_boolean(5, min_val=1, max_val=10))
        self.assertTrue(f.get_keep_boolean(0, min_val=1, max_val=10))

    def test_no_bounds(self):
        f = Filter()
        self.assertTrue(f.get_keep_boolean(999))


@TEST_TAG("standalone")
class MapperSubclassTest(DataJuicerTestCaseBase):

    def test_cannot_override_process(self):
        with self.assertRaises(TypeError):
            class BadMapper(Mapper):
                def process(self, sample):
                    pass

    def test_valid_subclass(self):
        class GoodMapper(Mapper):
            def process_single(self, sample):
                return sample

        m = GoodMapper()
        self.assertIsNotNone(m)


@TEST_TAG("standalone")
class FilterSubclassTest(DataJuicerTestCaseBase):

    def test_cannot_override_process(self):
        with self.assertRaises(TypeError):
            class BadFilter(Filter):
                def process(self, sample):
                    pass

    def test_cannot_override_compute_stats(self):
        with self.assertRaises(TypeError):
            class BadFilter(Filter):
                def compute_stats(self, sample):
                    pass


if __name__ == "__main__":
    unittest.main()
