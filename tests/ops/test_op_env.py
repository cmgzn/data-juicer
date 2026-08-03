import os
import tempfile
import unittest

from data_juicer.ops.op_env import (
    OPEnvSpec,
    Requirement,
    parse_requirements_list,
    parse_single_requirement,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class ParseSingleRequirementTest(DataJuicerTestCaseBase):

    def test_simple_package(self):
        req = parse_single_requirement("numpy")
        self.assertEqual(req.name, "numpy")
        self.assertFalse(req.is_local)

    def test_package_with_version(self):
        req = parse_single_requirement("numpy>=1.20.0")
        self.assertEqual(req.name, "numpy")
        self.assertIn(">=1.20.0", str(req.version))

    def test_package_with_extras(self):
        req = parse_single_requirement("requests[security]")
        self.assertEqual(req.name, "requests")
        self.assertIn("security", req.extras)

    def test_editable_local(self):
        tmp_dir = tempfile.mkdtemp()
        req = parse_single_requirement(f"-e {tmp_dir}")
        self.assertTrue(req.is_local)
        self.assertTrue(req.is_editable)
        self.assertEqual(req.path, tmp_dir)

    def test_local_directory(self):
        tmp_dir = tempfile.mkdtemp()
        req = parse_single_requirement(tmp_dir)
        self.assertTrue(req.is_local)
        self.assertEqual(req.path, tmp_dir)

    def test_git_url(self):
        req = parse_single_requirement("git+https://github.com/org/repo.git")
        self.assertIsNotNone(req.url)
        self.assertIn("github.com", req.url)

    def test_invalid_requirement(self):
        req = parse_single_requirement("!!!invalid!!!")
        self.assertIsNone(req)

    def test_whitespace_stripped(self):
        req = parse_single_requirement("  numpy  ")
        self.assertEqual(req.name, "numpy")


@TEST_TAG("standalone")
class ParseRequirementsListTest(DataJuicerTestCaseBase):

    def test_multiple_packages(self):
        reqs = parse_requirements_list(["numpy>=1.20", "pandas", "scipy"])
        self.assertEqual(len(reqs), 3)

    def test_invalid_entries_skipped(self):
        reqs = parse_requirements_list(["numpy", "!!!bad!!!", "pandas"])
        self.assertEqual(len(reqs), 2)

    def test_empty_list(self):
        reqs = parse_requirements_list([])
        self.assertEqual(reqs, [])


@TEST_TAG("standalone")
class RequirementTest(DataJuicerTestCaseBase):

    def test_str_simple(self):
        req = Requirement(name="numpy", version=">=1.20")
        self.assertEqual(str(req), "numpy>=1.20")

    def test_str_with_extras(self):
        req = Requirement(name="requests", extras=["security", "socks"])
        self.assertIn("[security,socks]", str(req))

    def test_str_local_editable(self):
        req = Requirement(is_local=True, path="/tmp/pkg", is_editable=True)
        self.assertEqual(str(req), "-e /tmp/pkg")

    def test_str_local_non_editable(self):
        req = Requirement(is_local=True, path="/tmp/pkg")
        self.assertEqual(str(req), "/tmp/pkg")

    def test_str_url_based(self):
        req = Requirement(url="git+https://github.com/org/repo.git")
        self.assertIn("git+https://", str(req))

    def test_str_name_and_url(self):
        req = Requirement(name="mypackage", url="https://example.com/pkg.tar.gz")
        s = str(req)
        self.assertIn("mypackage", s)
        self.assertIn("@", s)

    def test_str_with_markers(self):
        req = Requirement(name="numpy", markers='python_version >= "3.8"')
        self.assertIn(";", str(req))

    def test_post_init_converts_version_string(self):
        req = Requirement(name="numpy", version=">=1.20,<2.0")
        from packaging.specifiers import SpecifierSet
        self.assertIsInstance(req.version, SpecifierSet)


@TEST_TAG("standalone")
class OPEnvSpecTest(DataJuicerTestCaseBase):

    def test_init_with_list(self):
        spec = OPEnvSpec(pip_pkgs=["numpy>=1.20", "pandas"])
        self.assertEqual(len(spec.pip_pkgs), 2)
        self.assertIn("numpy", spec.parsed_requirements)

    def test_init_with_requirements_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("numpy>=1.20\n# comment\npandas\n\nscipy\n")
            path = f.name
        try:
            spec = OPEnvSpec(pip_pkgs=path)
            self.assertEqual(len(spec.pip_pkgs), 3)
        finally:
            os.unlink(path)

    def test_init_empty(self):
        spec = OPEnvSpec()
        self.assertEqual(spec.pip_pkgs, [])

    def test_to_dict_with_uv(self):
        spec = OPEnvSpec(pip_pkgs=["numpy"], backend="uv")
        d = spec.to_dict()
        self.assertIn("uv", d)
        self.assertEqual(d["uv"], spec.pip_pkgs)

    def test_to_dict_with_pip(self):
        spec = OPEnvSpec(pip_pkgs=["numpy"], backend="pip")
        d = spec.to_dict()
        self.assertIn("pip", d)

    def test_to_dict_with_env_vars(self):
        spec = OPEnvSpec(env_vars={"KEY": "val"})
        d = spec.to_dict()
        self.assertEqual(d["env_vars"], {"KEY": "val"})

    def test_to_dict_with_working_dir(self):
        spec = OPEnvSpec(working_dir="/tmp/work")
        d = spec.to_dict()
        self.assertEqual(d["working_dir"], "/tmp/work")

    def test_get_hash(self):
        spec = OPEnvSpec(pip_pkgs=["numpy"])
        h = spec.get_hash()
        self.assertEqual(len(h), 40)  # sha1 hex

    def test_get_hash_deterministic(self):
        spec1 = OPEnvSpec(pip_pkgs=["numpy", "pandas"])
        spec2 = OPEnvSpec(pip_pkgs=["numpy", "pandas"])
        self.assertEqual(spec1.get_hash(), spec2.get_hash())

    def test_get_requirement_name_list(self):
        spec = OPEnvSpec(pip_pkgs=["pandas", "numpy", "scipy"])
        names = spec.get_requirement_name_list()
        self.assertEqual(names, ["numpy", "pandas", "scipy"])

    def test_invalid_backend_raises(self):
        with self.assertRaises(AssertionError):
            OPEnvSpec(backend="conda")

    def test_init_with_parsed_requirements(self):
        reqs = {"numpy": Requirement(name="numpy", version=">=1.20")}
        spec = OPEnvSpec(parsed_requirements=reqs)
        self.assertEqual(spec.pip_pkgs, ["numpy>=1.20"])


if __name__ == "__main__":
    unittest.main()
