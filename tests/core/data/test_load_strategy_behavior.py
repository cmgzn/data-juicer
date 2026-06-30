import json
import os
import tempfile
import unittest

from jsonargparse import Namespace

from data_juicer.core.data.load_strategy import (
    DataLoadStrategy,
    DataLoadStrategyRegistry,
    DefaultArxivDataLoadStrategy,
    DefaultCommonCrawlDataLoadStrategy,
    DefaultLocalDataLoadStrategy,
    DefaultModelScopeDataLoadStrategy,
    DefaultS3DataLoadStrategy,
    DefaultWikiDataLoadStrategy,
    RayLocalJsonDataLoadStrategy,
    RayS3DataLoadStrategy,
    StrategyKey,
)
from data_juicer.utils.constant import Fields
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class ConcreteDataLoadStrategy(DataLoadStrategy):
    def load_data(self, **kwargs):
        return kwargs


class LoadStrategyBehaviorTest(DataJuicerTestCaseBase):
    def setUp(self):
        super().setUp()
        self._original_strategies = DataLoadStrategyRegistry._strategies.copy()

    def tearDown(self):
        DataLoadStrategyRegistry._strategies = self._original_strategies
        super().tearDown()

    def test_registry_uses_defaults_and_specific_patterns(self):
        DataLoadStrategyRegistry._strategies = {}

        @DataLoadStrategyRegistry.register("*", "local", "*.jsonl")
        class JsonLinesStrategy(ConcreteDataLoadStrategy):
            pass

        @DataLoadStrategyRegistry.register("ray", "local", "records.json?")
        class QuestionPatternStrategy(ConcreteDataLoadStrategy):
            pass

        @DataLoadStrategyRegistry.register("ray", "local", "records.jsonl")
        class ExactJsonLinesStrategy(ConcreteDataLoadStrategy):
            pass

        @DataLoadStrategyRegistry.register("default", "local", "*")
        class LocalFileStrategy(ConcreteDataLoadStrategy):
            pass

        self.assertTrue(
            StrategyKey("*", "local", "*.jsonl").matches(
                StrategyKey("ray", "local", "records.jsonl")
            )
        )
        self.assertIs(
            DataLoadStrategyRegistry.get_strategy_class("ray", "local", "records.jsonl"),
            ExactJsonLinesStrategy,
        )
        self.assertIs(
            DataLoadStrategyRegistry.get_strategy_class(None, "local", "records.jsonl"),
            JsonLinesStrategy,
        )
        self.assertIs(
            DataLoadStrategyRegistry.get_strategy_class("default", "local", "records.csv"),
            LocalFileStrategy,
        )
        self.assertIsNone(DataLoadStrategyRegistry.get_strategy_class("ray", "remote", "records.csv"))

    def test_default_local_strategy_loads_jsonl_with_suffix_filter_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = os.path.join(tmpdir, "records.jsonl")
            with open(data_path, "w", encoding="utf-8") as f:
                f.write(json.dumps({"text": "alpha"}) + "\n")
                f.write(json.dumps({"text": "beta"}) + "\n")

            cfg = Namespace(text_keys=["text"], suffixes=None, process=[{"suffix_filter": {}}])
            strategy = DefaultLocalDataLoadStrategy({"path": data_path}, cfg)
            dataset = strategy.load_data(num_proc=1)

        rows = dataset.to_list()
        self.assertEqual([row["text"] for row in rows], ["alpha", "beta"])
        self.assertIn(Fields.suffix, dataset.features)
        self.assertEqual({row[Fields.suffix] for row in rows}, {".jsonl"})

    def test_unimplemented_remote_strategies_raise(self):
        cfg = Namespace(text_keys=["text"])
        cases = [
            (DefaultModelScopeDataLoadStrategy, {"path": "modelscope_name"}),
            (DefaultArxivDataLoadStrategy, {"path": "2026.00001"}),
            (DefaultWikiDataLoadStrategy, {"path": "enwiki"}),
            (
                DefaultCommonCrawlDataLoadStrategy,
                {"start_snapshot": "2023-06", "end_snapshot": "2023-14"},
            ),
        ]

        for strategy_cls, ds_config in cases:
            with self.subTest(strategy=strategy_cls.__name__):
                strategy = strategy_cls(ds_config, cfg)
                with self.assertRaises(NotImplementedError):
                    strategy.load_data()

    def test_local_and_s3_strategies_reject_missing_or_invalid_paths_before_loading(self):
        cfg = Namespace(work_dir="/tmp", text_keys=["text"])
        missing = RayLocalJsonDataLoadStrategy({"path": "missing/records.jsonl"}, cfg)
        with self.assertRaises(FileNotFoundError):
            missing.load_data()

        default_s3 = DefaultS3DataLoadStrategy({"path": "https://bucket/records.jsonl"}, cfg)
        with self.assertRaises(ValueError):
            default_s3.load_data()

        ray_s3 = RayS3DataLoadStrategy({"path": "https://bucket/records.jsonl"}, cfg)
        with self.assertRaises(ValueError):
            ray_s3.load_data()


if __name__ == "__main__":
    unittest.main()
