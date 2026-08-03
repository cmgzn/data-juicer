import unittest

from datasets import is_caching_enabled

from data_juicer.utils.cache_utils import DatasetCacheControl, dataset_cache_control
from data_juicer.utils.config_utils import ConfigAccessor
from data_juicer.utils.availability_utils import _is_package_available
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class ConfigAccessorTest(DataJuicerTestCaseBase):

    def test_get_from_dict(self):
        self.assertEqual(ConfigAccessor.get({"a": 1}, "a"), 1)

    def test_get_from_dict_default(self):
        self.assertEqual(ConfigAccessor.get({"a": 1}, "b", "default"), "default")

    def test_get_from_object(self):
        class Cfg:
            x = 42
        self.assertEqual(ConfigAccessor.get(Cfg(), "x"), 42)

    def test_get_from_object_default(self):
        class Cfg:
            pass
        self.assertEqual(ConfigAccessor.get(Cfg(), "y", 99), 99)

    def test_get_from_none(self):
        self.assertEqual(ConfigAccessor.get(None, "x", "fallback"), "fallback")

    def test_get_nested_dict(self):
        cfg = {"db": {"host": "localhost", "port": 5432}}
        self.assertEqual(ConfigAccessor.get_nested(cfg, "db", "host"), "localhost")

    def test_get_nested_default(self):
        cfg = {"db": {"host": "localhost"}}
        self.assertEqual(ConfigAccessor.get_nested(cfg, "db", "port", default=3306), 3306)

    def test_get_nested_none_intermediate(self):
        cfg = {"db": None}
        self.assertEqual(ConfigAccessor.get_nested(cfg, "db", "host", default="x"), "x")

    def test_get_nested_missing_key(self):
        cfg = {"a": 1}
        self.assertEqual(ConfigAccessor.get_nested(cfg, "b", "c", default="d"), "d")


@TEST_TAG("standalone")
class DatasetCacheControlTest(DataJuicerTestCaseBase):

    def test_disable_and_restore(self):
        original = is_caching_enabled()
        with DatasetCacheControl(on=False):
            self.assertFalse(is_caching_enabled())
        self.assertEqual(is_caching_enabled(), original)

    def test_enable_and_restore(self):
        original = is_caching_enabled()
        with DatasetCacheControl(on=True):
            self.assertTrue(is_caching_enabled())
        self.assertEqual(is_caching_enabled(), original)


@TEST_TAG("standalone")
class DatasetCacheDecoratorTest(DataJuicerTestCaseBase):

    def test_decorator_disables_cache(self):
        @dataset_cache_control(on=False)
        def work():
            return is_caching_enabled()

        result = work()
        self.assertFalse(result)

    def test_decorator_enables_cache(self):
        @dataset_cache_control(on=True)
        def work():
            return is_caching_enabled()

        result = work()
        self.assertTrue(result)


@TEST_TAG("standalone")
class AvailabilityUtilsTest(DataJuicerTestCaseBase):

    def test_available_package(self):
        self.assertTrue(_is_package_available("datasets"))

    def test_unavailable_package(self):
        self.assertFalse(_is_package_available("nonexistent_pkg_xyz"))

    def test_return_version(self):
        available, version = _is_package_available("datasets", return_version=True)
        self.assertTrue(available)
        self.assertNotEqual(version, "N/A")

    def test_return_version_unavailable(self):
        available, version = _is_package_available("nonexistent_xyz", return_version=True)
        self.assertFalse(available)


if __name__ == "__main__":
    unittest.main()
