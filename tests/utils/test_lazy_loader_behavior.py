import sys
import unittest
from types import ModuleType

from data_juicer.utils.lazy_loader import LazyLoader, get_toml_file_path, get_uv_lock_path
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class LazyLoaderBehaviorTest(DataJuicerTestCaseBase):
    def tearDown(self):
        LazyLoader.reset_dependencies_cache()
        super().tearDown()

    def test_live_dependency_files_are_discoverable(self):
        LazyLoader.reset_dependencies_cache()

        pyproject_path = get_toml_file_path()
        lock_path = get_uv_lock_path()
        deps = LazyLoader.get_all_dependencies()

        self.assertTrue(pyproject_path.name.endswith("pyproject.toml"))
        self.assertTrue(lock_path.name.endswith("uv.lock"))
        self.assertIn("ray", deps)
        self.assertIs(deps, LazyLoader.get_all_dependencies())

    def test_package_mapping_and_url_normalization(self):
        self.assertEqual(LazyLoader.get_package_name("cv2"), "opencv-contrib-python")
        self.assertEqual(LazyLoader.get_package_name("json"), "json")

        loader = LazyLoader(
            "json",
            package_url="local-package@git+https://example.invalid/repo.git",
            auto_install=False,
        )

        self.assertEqual(loader._package_name, "json")
        self.assertEqual(loader._package_url, "git+https://example.invalid/repo.git")

    def test_existing_module_loads_once_and_updates_parent_globals(self):
        globals().pop("decimal", None)
        loader = LazyLoader("decimal", auto_install=False)

        decimal_type = loader.Decimal
        loaded_module = loader._load()

        self.assertEqual(decimal_type("1.25") + decimal_type("2.75"), decimal_type("4.00"))
        self.assertIs(loaded_module, loader._module)
        self.assertIs(globals()["decimal"], loaded_module)
        self.assertIsInstance(loader, ModuleType)

    def test_submodule_access_and_missing_attribute_errors(self):
        loader = LazyLoader("email", auto_install=False)

        parser_module = loader.parser

        self.assertIs(parser_module, sys.modules["email.parser"])
        with self.assertRaises(AttributeError):
            _ = loader.attribute_that_is_not_present


if __name__ == "__main__":
    unittest.main()
