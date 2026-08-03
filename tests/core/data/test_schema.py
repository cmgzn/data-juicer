import unittest
from typing import Any, Dict, List

import pyarrow as pa
from datasets import ClassLabel, Features, Sequence, Value

from data_juicer.core.data.schema import Schema
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class SchemaFromHfFeaturesTest(DataJuicerTestCaseBase):

    def test_string_value(self):
        features = Features({"text": Value("string")})
        schema = Schema.from_hf_features(features)
        self.assertEqual(schema.columns, ["text"])
        self.assertEqual(schema.column_types["text"], str)

    def test_int_value(self):
        features = Features({"count": Value("int64")})
        schema = Schema.from_hf_features(features)
        self.assertEqual(schema.column_types["count"], int)

    def test_float_value(self):
        features = Features({"score": Value("float32")})
        schema = Schema.from_hf_features(features)
        self.assertEqual(schema.column_types["score"], float)

    def test_bool_value(self):
        features = Features({"flag": Value("bool")})
        schema = Schema.from_hf_features(features)
        self.assertEqual(schema.column_types["flag"], bool)

    def test_sequence(self):
        features = Features({"tags": Sequence(Value("string"))})
        schema = Schema.from_hf_features(features)
        self.assertEqual(schema.column_types["tags"], List[str])

    def test_class_label(self):
        features = Features({"label": ClassLabel(names=["pos", "neg"])})
        schema = Schema.from_hf_features(features)
        self.assertEqual(schema.column_types["label"], int)

    def test_multiple_columns(self):
        features = Features({
            "text": Value("string"),
            "score": Value("float64"),
            "id": Value("int32"),
        })
        schema = Schema.from_hf_features(features)
        self.assertEqual(len(schema.columns), 3)
        self.assertEqual(schema.column_types["text"], str)
        self.assertEqual(schema.column_types["score"], float)
        self.assertEqual(schema.column_types["id"], int)


@TEST_TAG("standalone")
class SchemaFromRaySchemaTest(DataJuicerTestCaseBase):

    def test_string_type(self):
        arrow_schema = pa.schema([("text", pa.string())])
        schema = Schema.from_ray_schema(arrow_schema)
        self.assertEqual(schema.column_types["text"], str)

    def test_int_type(self):
        arrow_schema = pa.schema([("count", pa.int64())])
        schema = Schema.from_ray_schema(arrow_schema)
        self.assertEqual(schema.column_types["count"], int)

    def test_float_type(self):
        arrow_schema = pa.schema([("score", pa.float64())])
        schema = Schema.from_ray_schema(arrow_schema)
        self.assertEqual(schema.column_types["score"], float)

    def test_bool_type(self):
        arrow_schema = pa.schema([("flag", pa.bool_())])
        schema = Schema.from_ray_schema(arrow_schema)
        self.assertEqual(schema.column_types["flag"], bool)

    def test_binary_type(self):
        arrow_schema = pa.schema([("data", pa.binary())])
        schema = Schema.from_ray_schema(arrow_schema)
        self.assertEqual(schema.column_types["data"], bytes)

    def test_list_type(self):
        arrow_schema = pa.schema([("items", pa.list_(pa.string()))])
        schema = Schema.from_ray_schema(arrow_schema)
        self.assertEqual(schema.column_types["items"], List[str])

    def test_struct_type(self):
        arrow_schema = pa.schema([
            ("meta", pa.struct([("key", pa.string()), ("val", pa.int64())]))
        ])
        schema = Schema.from_ray_schema(arrow_schema)
        meta_schema = schema.column_types["meta"]
        self.assertIsInstance(meta_schema, Schema)
        self.assertEqual(meta_schema.column_types["key"], str)
        self.assertEqual(meta_schema.column_types["val"], int)

    def test_map_type(self):
        arrow_schema = pa.schema([("kv", pa.map_(pa.string(), pa.int64()))])
        schema = Schema.from_ray_schema(arrow_schema)
        self.assertEqual(schema.column_types["kv"], dict)


@TEST_TAG("standalone")
class SchemaValidationTest(DataJuicerTestCaseBase):

    def test_valid_schema(self):
        schema = Schema(column_types={"a": str, "b": int}, columns=["a", "b"])
        self.assertEqual(schema.columns, ["a", "b"])

    def test_missing_column_type_raises(self):
        with self.assertRaises(ValueError):
            Schema(column_types={"a": str}, columns=["a", "b"])

    def test_str_representation(self):
        schema = Schema(column_types={"text": str}, columns=["text"])
        s = str(schema)
        self.assertIn("Dataset Schema", s)
        self.assertIn("text", s)


if __name__ == "__main__":
    unittest.main()
