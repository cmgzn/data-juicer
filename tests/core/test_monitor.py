import unittest

from data_juicer.core.monitor import Monitor
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class MonitorAnalysisTest(DataJuicerTestCaseBase):

    def _make_resource_util_dict(self, records):
        return {
            "time": 5.0,
            "sampling interval": 0.5,
            "resource": records,
        }

    def test_analyze_single_basic(self):
        records = [
            {"CPU util.": 0.5, "Used mem.": 1000, "Free mem.": 3000},
            {"CPU util.": 0.7, "Used mem.": 1200, "Free mem.": 2800},
            {"CPU util.": 0.6, "Used mem.": 1100, "Free mem.": 2900},
        ]
        util_dict = self._make_resource_util_dict(records)
        result = Monitor.analyze_single_resource_util(util_dict)
        analysis = result["resource_analysis"]

        self.assertAlmostEqual(analysis["CPU util."]["max"], 0.7)
        self.assertAlmostEqual(analysis["CPU util."]["min"], 0.5)
        self.assertAlmostEqual(analysis["CPU util."]["avg"], 0.6)
        self.assertEqual(analysis["Used mem."]["max"], 1200)
        self.assertEqual(analysis["Used mem."]["min"], 1000)

    def test_analyze_single_with_none_values(self):
        records = [
            {"GPU util.": None, "CPU util.": 0.3},
            {"GPU util.": None, "CPU util.": 0.5},
        ]
        util_dict = self._make_resource_util_dict(records)
        result = Monitor.analyze_single_resource_util(util_dict)
        analysis = result["resource_analysis"]
        self.assertNotIn("GPU util.", analysis)
        self.assertIn("CPU util.", analysis)

    def test_analyze_single_with_list_values(self):
        records = [
            {"GPU util.": [0.4, 0.5], "CPU util.": 0.3},
            {"GPU util.": [0.6, 0.7], "CPU util.": 0.5},
        ]
        util_dict = self._make_resource_util_dict(records)
        result = Monitor.analyze_single_resource_util(util_dict)
        analysis = result["resource_analysis"]
        self.assertAlmostEqual(analysis["GPU util."]["max"], 0.7)
        self.assertAlmostEqual(analysis["GPU util."]["min"], 0.4)

    def test_analyze_single_empty_records(self):
        util_dict = self._make_resource_util_dict([])
        result = Monitor.analyze_single_resource_util(util_dict)
        self.assertEqual(result["resource_analysis"], {})

    def test_analyze_resource_util_list(self):
        dicts = [
            self._make_resource_util_dict([
                {"CPU util.": 0.5, "Used mem.": 1000},
            ]),
            self._make_resource_util_dict([
                {"CPU util.": 0.8, "Used mem.": 2000},
            ]),
        ]
        results = Monitor.analyze_resource_util_list(dicts)
        self.assertEqual(len(results), 2)
        self.assertIn("resource_analysis", results[0])
        self.assertIn("resource_analysis", results[1])
        self.assertAlmostEqual(
            results[0]["resource_analysis"]["CPU util."]["avg"], 0.5)
        self.assertAlmostEqual(
            results[1]["resource_analysis"]["CPU util."]["avg"], 0.8)

    def test_analyze_ignores_non_dynamic_fields(self):
        records = [
            {"CPU util.": 0.5, "CPU count": 8, "timestamp": 1000},
        ]
        util_dict = self._make_resource_util_dict(records)
        result = Monitor.analyze_single_resource_util(util_dict)
        analysis = result["resource_analysis"]
        self.assertNotIn("CPU count", analysis)
        self.assertNotIn("timestamp", analysis)
        self.assertIn("CPU util.", analysis)

    def test_dynamic_fields_set(self):
        expected_fields = {"CPU util.", "Used mem.", "Free mem.",
                          "Available mem.", "Mem. util.",
                          "GPU free mem.", "GPU used mem.", "GPU util."}
        self.assertEqual(Monitor.DYNAMIC_FIELDS, expected_fields)


if __name__ == "__main__":
    unittest.main()
