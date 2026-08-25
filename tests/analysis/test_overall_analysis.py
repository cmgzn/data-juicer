import os
import unittest
import pandas as pd

from data_juicer.core.data import NestedDataset
from data_juicer.analysis.overall_analysis import OverallAnalysis, _single_column_analysis
from data_juicer.utils.constant import DEFAULT_PREFIX, Fields

from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase

class OverallAnalysisTest(DataJuicerTestCaseBase):

    def setUp(self) -> None:
        super().setUp()

        data_list = [
            {
                Fields.meta: {
                    f'{DEFAULT_PREFIX}meta_str1': 'human',
                    f'{DEFAULT_PREFIX}meta_str2': 'sft',
                    'meta_str3': 'code',
                },
                Fields.stats: {
                    'stats_num_list': [4, 5, 6],
                    'stats_num': 3.1,
                    'stats_str': 'zh',
                }
            },
            {
                Fields.meta: {
                    f'{DEFAULT_PREFIX}meta_str1': 'assistant',
                    f'{DEFAULT_PREFIX}meta_str2': 'rlhf',
                    'meta_str3': 'math',
                },
                Fields.stats: {
                    'stats_num_list': [7, 8, 9],
                    'stats_num': 4.1,
                    'stats_str': 'en',
                }
            },
            {
                Fields.meta: {
                    f'{DEFAULT_PREFIX}meta_str1': 'system',
                    f'{DEFAULT_PREFIX}meta_str2': 'dpo',
                    'meta_str3': 'reasoning',
                },
                Fields.stats: {
                    'stats_num_list': [10, 11, 12],
                    'stats_num': 5.1,
                    'stats_str': 'fr',
                }
            },
        ]
        self.dataset = NestedDataset.from_list(data_list)
        invalid_data_list = [
            {
                Fields.stats: {
                    'invalid_dict': {'lang': 'fr'},
                }
            },
            {
                Fields.stats: {
                    'invalid_dict': {'lang': 'zh'},
                }
            },
        ]
        self.invalid_dataset = NestedDataset.from_list(invalid_data_list)
        self.temp_output_path = 'tmp/test_overall_analysis/'

    def tearDown(self):
        if os.path.exists(self.temp_output_path):
            os.system(f'rm -rf {self.temp_output_path}')

        super().tearDown()

    def test_single_column_analysis(self):
        df = self.dataset.flatten().to_pandas()
        res = _single_column_analysis(df[f'{Fields.stats}.stats_num'])
        self.assertIsInstance(res, pd.Series)
        self.assertIn('min', res.index)
        self.assertIn('max', res.index)
        self.assertIn('mean', res.index)
        self.assertIn('std', res.index)

    def test_analyze(self):
        overall_analysis = OverallAnalysis(self.dataset, self.temp_output_path)
        res = overall_analysis.analyze()
        self.assertIsInstance(res, pd.DataFrame)
        self.assertIn('stats_num', res.columns)
        self.assertIn(f'{DEFAULT_PREFIX}meta_str1', res.columns)
        self.assertNotIn('meta_str3', res.columns)
        self.assertEqual(len(res.columns), 5)
        self.assertTrue(os.path.exists(os.path.join(self.temp_output_path, 'overall.csv')))
        self.assertTrue(os.path.exists(os.path.join(self.temp_output_path, 'overall.md')))

    def test_invalid_dataset(self):
        overall_analysis = OverallAnalysis(self.invalid_dataset, self.temp_output_path)
        res = overall_analysis.analyze()
        self.assertIsInstance(res, pd.DataFrame)
        self.assertEqual(len(res.columns), 0)
        self.assertTrue(os.path.exists(os.path.join(self.temp_output_path, 'overall.csv')))
        self.assertTrue(os.path.exists(os.path.join(self.temp_output_path, 'overall.md')))


class OverallAnalysisStringDtypeTest(DataJuicerTestCaseBase):
    """Regression test: pandas 2.x StringDtype should not crash analyze()."""

    def setUp(self):
        super().setUp()
        self.temp_output_path = 'tmp/test_overall_stringdtype/'

    def tearDown(self):
        if os.path.exists(self.temp_output_path):
            os.system(f'rm -rf {self.temp_output_path}')
        super().tearDown()

    def test_stringdtype_column_no_crash(self):
        df = pd.DataFrame({
            Fields.stats: [
                {'score': 0.8, 'lang': 'zh'},
                {'score': 0.9, 'lang': 'en'},
                {'score': 0.7, 'lang': 'fr'},
            ]
        })
        # Force string column to use pandas 2.x StringDtype
        dataset = NestedDataset.from_pandas(df)
        flat = dataset.flatten().to_pandas()
        flat[f'{Fields.stats}.lang'] = flat[
            f'{Fields.stats}.lang'
        ].astype('string')

        # Reconstruct dataset with StringDtype column
        dataset_with_stringdtype = NestedDataset.from_pandas(
            flat.rename(columns={
                f'{Fields.stats}.lang': f'{Fields.stats}.lang',
                f'{Fields.stats}.score': f'{Fields.stats}.score',
            })
        )
        overall_analysis = OverallAnalysis(
            dataset_with_stringdtype, self.temp_output_path
        )
        # Before the fix this raised:
        # TypeError: Cannot interpret '<StringDtype>' as a data type
        res = overall_analysis.analyze()
        self.assertIsInstance(res, pd.DataFrame)


if __name__ == '__main__':
    unittest.main()
