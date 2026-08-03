import unittest

from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase

from data_juicer.tools.DJ_mcp_recipe_flow import (
    get_global_config_schema,
    get_dataset_load_strategies,
    search_ops,
    run_data_recipe,
    analyze_dataset,
)


class GetGlobalConfigSchemaTest(DataJuicerTestCaseBase):

    def test_returns_dict(self):
        result = get_global_config_schema()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_schema_entries_have_required_keys(self):
        result = get_global_config_schema()
        required_keys = {'type', 'default', 'description'}
        for param_name, entry in result.items():
            self.assertIsInstance(entry, dict,
                                 f"Entry for '{param_name}' is not a dict")
            for key in required_keys:
                self.assertIn(key, entry,
                              f"Entry for '{param_name}' missing key '{key}'")

    def test_excludes_internal_params(self):
        result = get_global_config_schema()
        excluded = {'config', 'auto', 'help', 'print_config'}
        for param_name in result.keys():
            self.assertNotIn(param_name, excluded,
                             f"Internal param '{param_name}' should not "
                             f"appear in schema")


class GetDatasetLoadStrategiesTest(DataJuicerTestCaseBase):

    def test_returns_dict(self):
        result = get_dataset_load_strategies()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_entries_have_required_fields(self):
        result = get_dataset_load_strategies()
        required_fields = {
            'executor_type', 'data_type', 'data_source',
            'description', 'class_name'
        }
        for strategy_id, entry in result.items():
            self.assertIsInstance(entry, dict,
                                 f"Entry for '{strategy_id}' is not a dict")
            for field in required_fields:
                self.assertIn(field, entry,
                              f"Entry for '{strategy_id}' missing "
                              f"field '{field}'")

    def test_strategy_key_format(self):
        """Strategy keys should be executor_type/data_type/data_source."""
        result = get_dataset_load_strategies()
        for strategy_id in result.keys():
            parts = strategy_id.split('/')
            self.assertEqual(len(parts), 3,
                             f"Strategy key '{strategy_id}' does not have "
                             f"3 slash-separated parts")


class SearchOpsTest(DataJuicerTestCaseBase):

    def test_search_all_returns_nonempty(self):
        result = search_ops()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_search_by_type_filter(self):
        result = search_ops(op_type='filter')
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        for op_name in result.keys():
            self.assertIn('filter', op_name,
                          f"Op '{op_name}' does not contain 'filter' in name")

    def test_search_by_tags(self):
        result = search_ops(tags=['text'])
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_regex_mode_requires_query(self):
        result = search_ops(query=None, search_mode='regex')
        self.assertIn('error', result)
        self.assertIn('query is required', result['error'])

    def test_bm25_mode_requires_query(self):
        result = search_ops(query=None, search_mode='bm25')
        self.assertIn('error', result)
        self.assertIn('query is required', result['error'])

    def test_regex_mode_finds_matching_ops(self):
        result = search_ops(query='language.*filter', search_mode='regex')
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        # At least one result should match the regex pattern
        found_match = any('language' in name for name in result.keys())
        self.assertTrue(found_match,
                        "No operator matching 'language' found in regex "
                        "search results")

    def test_search_result_values_are_strings(self):
        result = search_ops(op_type='mapper')
        self.assertIsInstance(result, dict)
        for op_name, desc in result.items():
            self.assertIsInstance(op_name, str)
            self.assertIsInstance(desc, str)

    def test_bm25_mode_returns_results(self):
        result = search_ops(query='remove duplicate text', search_mode='bm25',
                            top_k=5)
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        self.assertLessEqual(len(result), 5)

    def test_search_by_type_and_tags_combined(self):
        result = search_ops(op_type='filter', tags=['text'])
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        for op_name in result.keys():
            self.assertIn('filter', op_name)


class RunDataRecipeTest(DataJuicerTestCaseBase):

    def test_invalid_config_returns_error_string(self):
        # No valid dataset_path, so execution should fail gracefully
        result = run_data_recipe(
            process=[{'text_length_filter': {'min_len': 10}}],
            dataset_path='/nonexistent/path/to/data.jsonl',
        )
        self.assertIsInstance(result, str)
        self.assertIn('error', result.lower())

    def test_error_string_format(self):
        result = run_data_recipe(
            process=[{'text_length_filter': {'min_len': 10}}],
            dataset_path='/nonexistent/path/to/data.jsonl',
        )
        self.assertIsInstance(result, str)
        self.assertTrue(
            result.startswith('Occur error when executing Data-Juicer:'),
            f"Error message does not start with expected prefix. "
            f"Got: {result[:80]}"
        )


class AnalyzeDatasetTest(DataJuicerTestCaseBase):

    def test_invalid_config_returns_error_string(self):
        result = analyze_dataset(
            process=[{'text_length_filter': {'min_len': 10}}],
            dataset_path='/nonexistent/path/to/data.jsonl',
        )
        self.assertIsInstance(result, str)
        self.assertTrue(
            result.startswith(
                'Occur error when executing Data-Juicer Analyzer:'),
            f"Error message does not start with expected prefix. "
            f"Got: {result[:80]}"
        )


if __name__ == '__main__':
    unittest.main()
