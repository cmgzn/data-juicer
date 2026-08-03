import unittest

from data_juicer.core.data.data_validator import (
    BaseConversationValidator,
    DataValidationError,
    DataValidator,
    DataValidatorRegistry,
    DataJuicerFormatValidator,
    RequiredFieldsValidator,
    SwiftMessagesValidator,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


class FakeDJDataset:
    """Minimal fake implementing DJDataset interface for validator tests."""

    def __init__(self, data):
        self.data = data

    def get(self, n):
        return self.data[:n]

    def schema(self):
        class S:
            columns = list(self.data[0].keys()) if self.data else []
        return S()

    def get_column(self, field, n):
        return [row.get(field) for row in self.data[:n]]


@TEST_TAG("standalone")
class DataValidatorRegistryTest(DataJuicerTestCaseBase):

    def test_register_and_get(self):
        cls = DataValidatorRegistry.get_validator("swift_messages")
        self.assertIs(cls, SwiftMessagesValidator)

    def test_get_dj_conversation(self):
        cls = DataValidatorRegistry.get_validator("dj_conversation")
        self.assertIs(cls, DataJuicerFormatValidator)

    def test_get_required_fields(self):
        cls = DataValidatorRegistry.get_validator("required_fields")
        self.assertIs(cls, RequiredFieldsValidator)

    def test_get_nonexistent(self):
        self.assertIsNone(DataValidatorRegistry.get_validator("nonexistent"))


@TEST_TAG("standalone")
class SwiftMessagesValidatorTest(DataJuicerTestCaseBase):

    def _make_validator(self, **kwargs):
        config = {"min_turns": 1, "max_turns": 100, "sample_size": 10}
        config.update(kwargs)
        return SwiftMessagesValidator(config)

    def test_valid_conversation(self):
        v = self._make_validator()
        data = {
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ]
        }
        v.validate_conversation(data)

    def test_missing_messages_field(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError) as ctx:
            v.validate_conversation({})
        self.assertIn("messages", str(ctx.exception))

    def test_messages_not_list(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"messages": "not a list"})

    def test_too_few_messages(self):
        v = self._make_validator(min_turns=2)
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"messages": [{"role": "user", "content": "x"}]})

    def test_too_many_messages(self):
        v = self._make_validator(max_turns=2)
        msgs = [{"role": "user", "content": "x"}] * 3
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"messages": msgs})

    def test_missing_role(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"messages": [{"content": "x"}]})

    def test_null_role(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"messages": [{"role": None, "content": "x"}]})

    def test_invalid_role(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"messages": [{"role": "bot", "content": "x"}]})

    def test_missing_content(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"messages": [{"role": "user"}]})

    def test_null_content(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"messages": [{"role": "user", "content": None}]}
            )

    def test_system_role_valid(self):
        v = self._make_validator()
        data = {
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "hi"},
            ]
        }
        v.validate_conversation(data)


@TEST_TAG("standalone")
class DataJuicerFormatValidatorTest(DataJuicerTestCaseBase):

    def _make_validator(self, **kwargs):
        config = {"min_turns": 1, "max_turns": 100, "sample_size": 10}
        config.update(kwargs)
        return DataJuicerFormatValidator(config)

    def test_valid_minimal(self):
        v = self._make_validator()
        data = {"instruction": "do it", "query": "what", "response": "done"}
        v.validate_conversation(data)

    def test_valid_with_system_and_history(self):
        v = self._make_validator()
        data = {
            "system": "You are helpful",
            "instruction": "do it",
            "query": "q2",
            "response": "r2",
            "history": [["q1", "r1"]],
        }
        v.validate_conversation(data)

    def test_missing_instruction(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"query": "q", "response": "r"})

    def test_missing_query(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"instruction": "i", "response": "r"})

    def test_missing_response(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation({"instruction": "i", "query": "q"})

    def test_non_string_field(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"instruction": 123, "query": "q", "response": "r"}
            )

    def test_system_not_string(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"system": 42, "instruction": "i", "query": "q", "response": "r"}
            )

    def test_history_not_list(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"instruction": "i", "query": "q", "response": "r", "history": "bad"}
            )

    def test_history_turn_not_pair(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"instruction": "i", "query": "q", "response": "r",
                 "history": [["only_one"]]}
            )

    def test_history_turn_query_not_string(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"instruction": "i", "query": "q", "response": "r",
                 "history": [[123, "r"]]}
            )

    def test_history_turn_response_not_string(self):
        v = self._make_validator()
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"instruction": "i", "query": "q", "response": "r",
                 "history": [["q", 456]]}
            )

    def test_too_many_turns_with_history(self):
        v = self._make_validator(max_turns=2)
        with self.assertRaises(DataValidationError):
            v.validate_conversation(
                {"instruction": "i", "query": "q", "response": "r",
                 "history": [["q1", "r1"], ["q2", "r2"]]}
            )


@TEST_TAG("standalone")
class RequiredFieldsValidatorTest(DataJuicerTestCaseBase):

    def test_normalize_type_from_string(self):
        config = {"required_fields": ["f"], "field_types": {"f": "str"}}
        v = RequiredFieldsValidator(config)
        self.assertEqual(v.field_types["f"], str)

    def test_normalize_type_from_type_object(self):
        config = {"required_fields": ["f"], "field_types": {"f": int}}
        v = RequiredFieldsValidator(config)
        self.assertEqual(v.field_types["f"], int)

    def test_normalize_unknown_type_raises(self):
        config = {"required_fields": ["f"], "field_types": {"f": "unknown_type"}}
        with self.assertRaises(DataValidationError) as ctx:
            RequiredFieldsValidator(config)
        self.assertIn("Unknown type name", str(ctx.exception))

    def test_normalize_invalid_type_spec_raises(self):
        config = {"required_fields": ["f"], "field_types": {"f": 123}}
        with self.assertRaises(DataValidationError) as ctx:
            RequiredFieldsValidator(config)
        self.assertIn("Invalid type specification", str(ctx.exception))

    def test_all_supported_type_strings(self):
        for type_name in ["str", "string", "int", "integer", "float",
                          "bool", "boolean", "list", "dict", "tuple",
                          "set", "bytes"]:
            config = {"required_fields": ["f"], "field_types": {"f": type_name}}
            v = RequiredFieldsValidator(config)
            self.assertIsInstance(v.field_types["f"], type)


if __name__ == "__main__":
    unittest.main()
