import os
import tempfile
import unittest

import numpy as np

from data_juicer.utils.file_utils import (
    Sizes,
    add_suffix_to_filename,
    byte_size_to_size_str,
    find_files_with_suffix,
    is_absolute_path,
    is_remote_path,
    load_numpy,
    load_numpy_list,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class SizesTest(DataJuicerTestCaseBase):

    def test_kib(self):
        self.assertEqual(Sizes.KiB, 1024)

    def test_mib(self):
        self.assertEqual(Sizes.MiB, 1024 * 1024)

    def test_gib(self):
        self.assertEqual(Sizes.GiB, 1024 ** 3)

    def test_tib(self):
        self.assertEqual(Sizes.TiB, 1024 ** 4)


@TEST_TAG("standalone")
class ByteSizeToSizeStrTest(DataJuicerTestCaseBase):

    def test_bytes(self):
        self.assertIn("Bytes", byte_size_to_size_str(500))

    def test_kib(self):
        result = byte_size_to_size_str(2048)
        self.assertIn("KiB", result)

    def test_mib(self):
        result = byte_size_to_size_str(5 * 1024 * 1024)
        self.assertIn("MiB", result)

    def test_gib(self):
        result = byte_size_to_size_str(3 * 1024 ** 3)
        self.assertIn("GiB", result)

    def test_tib(self):
        result = byte_size_to_size_str(2 * 1024 ** 4)
        self.assertIn("TiB", result)

    def test_exact_values(self):
        self.assertEqual(byte_size_to_size_str(1024), "1.00 KiB")
        self.assertEqual(byte_size_to_size_str(0), "0.00 Bytes")


@TEST_TAG("standalone")
class IsRemotePathTest(DataJuicerTestCaseBase):

    def test_http(self):
        self.assertTrue(is_remote_path("http://example.com/data"))

    def test_https(self):
        self.assertTrue(is_remote_path("https://bucket.s3.amazonaws.com"))

    def test_s3(self):
        self.assertTrue(is_remote_path("s3://my-bucket/key"))

    def test_gs(self):
        self.assertTrue(is_remote_path("gs://bucket/path"))

    def test_hdfs(self):
        self.assertTrue(is_remote_path("hdfs://cluster/path"))

    def test_local_absolute(self):
        self.assertFalse(is_remote_path("/home/user/data"))

    def test_local_relative(self):
        self.assertFalse(is_remote_path("data/file.txt"))


@TEST_TAG("standalone")
class IsAbsolutePathTest(DataJuicerTestCaseBase):

    def test_absolute_unix(self):
        self.assertTrue(is_absolute_path("/home/user/data"))

    def test_relative(self):
        self.assertFalse(is_absolute_path("relative/path"))

    def test_remote_is_absolute(self):
        self.assertTrue(is_absolute_path("https://example.com/data"))

    def test_s3_is_absolute(self):
        self.assertTrue(is_absolute_path("s3://bucket/key"))


@TEST_TAG("standalone")
class AddSuffixToFilenameTest(DataJuicerTestCaseBase):

    def test_basic(self):
        self.assertEqual(add_suffix_to_filename("abc.jpg", "_resized"),
                         "abc_resized.jpg")

    def test_multiple_dots(self):
        self.assertEqual(add_suffix_to_filename("edf.xyz.csv", "_processed"),
                         "edf.xyz_processed.csv")

    def test_with_path(self):
        self.assertEqual(add_suffix_to_filename("/path/to/file.json", "_suf"),
                         "/path/to/file_suf.json")

    def test_no_extension(self):
        self.assertEqual(add_suffix_to_filename("noext", "_v2"), "noext_v2")


@TEST_TAG("standalone")
class LoadNumpyTest(DataJuicerTestCaseBase):

    def test_array_passthrough(self):
        arr = np.array([1, 2, 3])
        result = load_numpy(arr)
        np.testing.assert_array_equal(result, arr)

    def test_from_npy_file(self):
        arr = np.array([4, 5, 6])
        with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as f:
            np.save(f, arr)
            path = f.name
        try:
            result = load_numpy(path)
            np.testing.assert_array_equal(result, arr)
        finally:
            os.unlink(path)

    def test_from_list(self):
        result = load_numpy([1.0, 2.0, 3.0])
        np.testing.assert_array_equal(result, np.array([1.0, 2.0, 3.0]))

    def test_load_numpy_list(self):
        arr1 = np.array([1, 2])
        arr2 = np.array([3, 4])
        with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as f:
            np.save(f, arr2)
            path = f.name
        try:
            results = load_numpy_list([arr1, path])
            np.testing.assert_array_equal(results[0], arr1)
            np.testing.assert_array_equal(results[1], arr2)
        finally:
            os.unlink(path)


@TEST_TAG("standalone")
class FindFilesWithSuffixTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp()
        open(os.path.join(self.tmp_dir, "a.txt"), "w").close()
        open(os.path.join(self.tmp_dir, "b.txt"), "w").close()
        open(os.path.join(self.tmp_dir, "c.json"), "w").close()
        sub = os.path.join(self.tmp_dir, "sub")
        os.makedirs(sub)
        open(os.path.join(sub, "d.txt"), "w").close()

    def test_find_txt(self):
        result = find_files_with_suffix(self.tmp_dir, ".txt")
        self.assertIn(".txt", result)
        self.assertEqual(len(result[".txt"]), 3)

    def test_find_json(self):
        result = find_files_with_suffix(self.tmp_dir, ".json")
        self.assertIn(".json", result)
        self.assertEqual(len(result[".json"]), 1)

    def test_find_all_no_suffix(self):
        result = find_files_with_suffix(self.tmp_dir)
        total = sum(len(v) for v in result.values())
        self.assertEqual(total, 4)

    def test_suffix_without_dot(self):
        result = find_files_with_suffix(self.tmp_dir, "txt")
        self.assertIn(".txt", result)

    def test_single_file(self):
        path = os.path.join(self.tmp_dir, "a.txt")
        result = find_files_with_suffix(path, ".txt")
        self.assertIn(".txt", result)
        self.assertEqual(len(result[".txt"]), 1)

    def test_multiple_suffixes(self):
        result = find_files_with_suffix(self.tmp_dir, [".txt", ".json"])
        self.assertIn(".txt", result)
        self.assertIn(".json", result)

    def test_nonexistent_suffix(self):
        result = find_files_with_suffix(self.tmp_dir, ".xyz")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
