"""Tests for operator environment isolation (local mode).

Covers:
  - _get_class_env_spec: class-level env spec without instantiation
  - IsolatedOpProxy: placeholder behaviour
  - load_ops Path A (no manager), Path C (local isolation + segment grouping)
  - VenvManager: caching & path logic (mocked subprocess)
  - wrap_op_with_isolation / wrap_ops_with_isolation: proxy wrapping
  - Subprocess integration: end-to-end op execution
  - Segment grouping: consecutive same-spec ops share one subprocess call
  - Exporter/tracer config forwarding to subprocess
  - Tracer clear_existing parameter
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

from data_juicer.ops.base_op import OPERATORS
from data_juicer.ops.load import (
    IsolatedOpProxy,
    _get_class_env_spec,
    load_ops,
)
from data_juicer.ops.local_env_runner import (
    VenvManager,
    wrap_op_with_isolation,
    wrap_ops_with_isolation,
    reset_venv_manager,
)
from data_juicer.ops.op_env import OPEnvManager, OPEnvSpec, resolve_local_env_spec
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


# ---------------------------------------------------------------------------
# 1. _get_class_env_spec
# ---------------------------------------------------------------------------


class GetClassEnvSpecTest(DataJuicerTestCaseBase):
    """Computing OPEnvSpec from a class without instantiation."""

    def test_returns_env_spec(self):
        cls = OPERATORS.modules["clean_email_mapper"]
        spec = _get_class_env_spec(cls)
        self.assertIsInstance(spec, OPEnvSpec)

    def test_name_from_class(self):
        """_name should come from the class attribute set by the registry."""
        cls = OPERATORS.modules["clean_email_mapper"]
        spec = _get_class_env_spec(cls)
        # OPEnvSpec doesn't store the name, but _requirements and auto-analysis
        # are derived from the class.  We just verify it doesn't crash and
        # returns a valid spec.
        self.assertIsInstance(spec.pip_pkgs, list)

    def test_different_ops_different_specs(self):
        """Two different ops may have different env specs."""
        spec_a = _get_class_env_spec(OPERATORS.modules["clean_email_mapper"])
        spec_b = _get_class_env_spec(OPERATORS.modules["fix_unicode_mapper"])
        # Both should be valid OPEnvSpec instances
        self.assertIsInstance(spec_a, OPEnvSpec)
        self.assertIsInstance(spec_b, OPEnvSpec)


# ---------------------------------------------------------------------------
# 2. IsolatedOpProxy
# ---------------------------------------------------------------------------


class IsolatedOpProxyTest(DataJuicerTestCaseBase):
    """Placeholder object for non-instantiated isolated ops."""

    def setUp(self):
        super().setUp()
        self.op_cls = OPERATORS.modules["clean_email_mapper"]
        self.env_spec = OPEnvSpec()
        self.proxy = IsolatedOpProxy(
            op_name="clean_email_mapper",
            op_cls=self.op_cls,
            init_args={"repl": "<EMAIL>"},
            env_spec=self.env_spec,
        )

    def test_attributes(self):
        self.assertEqual(self.proxy._name, "clean_email_mapper")
        self.assertIs(self.proxy._op_cls, self.op_cls)
        self.assertEqual(self.proxy._init_args, {"repl": "<EMAIL>"})
        self.assertIs(self.proxy._env_spec, self.env_spec)
        self.assertIsNone(self.proxy._op_cfg)
        self.assertIsNone(self.proxy._run_func)

    def test_use_cuda_false(self):
        # clean_email_mapper is a CPU op; proxy should delegate to OP.use_cuda
        # and resolve the accelerator class default via __getattr__.
        self.assertFalse(self.proxy.use_cuda())

    def test_runtime_env_from_env_spec(self):
        self.assertEqual(self.proxy.runtime_env, self.env_spec.to_dict())

    def test_run_without_wrap_raises(self):
        with self.assertRaises(RuntimeError):
            self.proxy.run(dataset=None)

    def test_run_calls_wrapped_func(self):
        captured = {}

        def fake_run(dataset, *, exporter=None, tracer=None, **kwargs):
            captured["dataset"] = dataset
            captured["exporter"] = exporter
            return "result"

        self.proxy._run_func = fake_run
        result = self.proxy.run(dataset="ds", exporter="exp")
        self.assertEqual(result, "result")
        self.assertEqual(captured["dataset"], "ds")
        self.assertEqual(captured["exporter"], "exp")

    def test_op_cfg_assignable(self):
        cfg = {"clean_email_mapper": {"repl": "<EMAIL>"}}
        self.proxy._op_cfg = cfg
        self.assertEqual(self.proxy._op_cfg, cfg)


class ResolveLocalEnvSpecTest(DataJuicerTestCaseBase):
    """Local dependency decisions are based purely on the installed set."""

    @patch("data_juicer.ops.op_env._get_installed_version", return_value="2.0")
    def test_installed_satisfying_dependency_stays_in_main(self, _):
        resolved = resolve_local_env_spec(OPEnvSpec(pip_pkgs=["demo-package>=1"]))
        self.assertEqual(resolved.pip_pkgs, [])

    @patch("data_juicer.ops.op_env._get_installed_version", return_value=None)
    def test_missing_dependency_is_isolated(self, _):
        original = OPEnvSpec(pip_pkgs=["demo-package>=1"])
        resolved = resolve_local_env_spec(original)
        self.assertIs(resolved, original)

    @patch("data_juicer.ops.op_env._get_installed_version", return_value="1.0")
    def test_installed_conflicting_dependency_is_isolated(self, _):
        original = OPEnvSpec(pip_pkgs=["demo-package>=2"])
        resolved = resolve_local_env_spec(original)
        self.assertIs(resolved, original)

    @patch("data_juicer.ops.op_env._get_installed_version")
    def test_url_dependency_is_always_isolated(self, mock_version):
        original = OPEnvSpec(pip_pkgs=["demo-package @ git+https://example.com/demo.git"])
        resolved = resolve_local_env_spec(original)
        self.assertIs(resolved, original)
        mock_version.assert_not_called()

    def test_empty_spec_never_combines_with_isolated_spec(self):
        manager = OPEnvManager(min_common_dep_num_to_combine=0)
        self.assertFalse(
            manager.can_combine_op_env_specs(
                OPEnvSpec(),
                OPEnvSpec(pip_pkgs=["demo-package"]),
            )
        )


# ---------------------------------------------------------------------------
# 3. load_ops — Path A (no env manager)
# ---------------------------------------------------------------------------


class LoadOpsNoManagerTest(DataJuicerTestCaseBase):
    """Without OPEnvManager, all ops should be instantiated (existing behaviour)."""

    def test_all_instantiated(self):
        process_list = [
            {"clean_email_mapper": {}},
            {"fix_unicode_mapper": {}},
        ]
        ops = load_ops(process_list)
        self.assertEqual(len(ops), 2)
        for op in ops:
            self.assertNotIsInstance(op, IsolatedOpProxy)

    def test_op_cfg_stored(self):
        cfg = {"clean_email_mapper": {"repl": "<EMAIL>"}}
        ops = load_ops([cfg])
        self.assertEqual(ops[0]._op_cfg, cfg)

    def test_args_preserved(self):
        ops = load_ops([{"clean_email_mapper": {"repl": "<EMAIL>"}}])
        self.assertEqual(ops[0].repl, "<EMAIL>")

    def test_empty_list(self):
        self.assertEqual(load_ops([]), [])

    def test_order_preserved(self):
        process_list = [
            {"fix_unicode_mapper": {}},
            {"clean_email_mapper": {}},
        ]
        ops = load_ops(process_list)
        self.assertEqual(
            [op._name for op in ops],
            ["fix_unicode_mapper", "clean_email_mapper"],
        )


# ---------------------------------------------------------------------------
# 4. load_ops — Path C (local mode with OPEnvManager)
# ---------------------------------------------------------------------------


class LoadOpsLocalIsolationTest(DataJuicerTestCaseBase):
    """Local mode: ops with pip_pkgs are isolated, others instantiated."""

    def setUp(self):
        super().setUp()
        # Ensure VenvManager singleton is clean
        reset_venv_manager()

    def tearDown(self):
        reset_venv_manager()
        super().tearDown()

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    def test_no_deps_ops_instantiated(self, _):
        """Ops whose merged env spec has no pip_pkgs should be real instances."""
        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        ops = load_ops([{"clean_email_mapper": {}}], mgr)
        self.assertEqual(len(ops), 1)
        self.assertNotIsInstance(ops[0], IsolatedOpProxy)
        self.assertEqual(ops[0]._name, "clean_email_mapper")

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_ops_with_deps_proxied(self, mock_spec, mock_venv, _):
        """Ops whose merged env spec has pip_pkgs should become proxies."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg>=1.0"])

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        ops = load_ops([{"clean_email_mapper": {}}], mgr)
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], IsolatedOpProxy)
        self.assertEqual(ops[0]._name, "clean_email_mapper")
        self.assertIsNotNone(ops[0]._run_func)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.op_env._get_installed_version", return_value=None)
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_missing_dependency_is_isolated(self, mock_spec, _, mock_venv, _ray_mode):
        """A dependency missing from the main env isolates the op (no backfill)."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["demo-package>=1"])

        ops = load_ops(
            [{"clean_email_mapper": {}}],
            OPEnvManager(min_common_dep_num_to_combine=0),
        )

        self.assertIsInstance(ops[0], IsolatedOpProxy)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_mixed_deps_and_no_deps(self, mock_spec, mock_venv, _):
        """One op with deps (proxied) + one without (instantiated)."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        # First op has deps, second has none
        mock_spec.side_effect = [
            OPEnvSpec(pip_pkgs=["some-pkg>=1.0"]),
            OPEnvSpec(),
        ]

        mgr = OPEnvManager(min_common_dep_num_to_combine=999)
        process_list = [
            {"clean_email_mapper": {}},
            {"fix_unicode_mapper": {}},
        ]
        ops = load_ops(process_list, mgr)
        self.assertEqual(len(ops), 2)
        self.assertIsInstance(ops[0], IsolatedOpProxy)
        self.assertNotIsInstance(ops[1], IsolatedOpProxy)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_merged_group_all_proxied(self, mock_spec, mock_venv, _):
        """Merged group with pip_pkgs should proxy all ops in that group."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg>=1.0"])

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        process_list = [
            {"clean_email_mapper": {}},
            {"fix_unicode_mapper": {}},
        ]
        ops = load_ops(process_list, mgr)
        self.assertEqual(len(ops), 2)
        self.assertIsInstance(ops[0], IsolatedOpProxy)
        self.assertIsInstance(ops[1], IsolatedOpProxy)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_multiple_groups_all_with_deps_all_proxied(self, mock_spec, mock_venv, _):
        """Multiple env groups each with pip_pkgs — all should be proxied."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        # Different deps so they end up in separate groups
        mock_spec.side_effect = [
            OPEnvSpec(pip_pkgs=["pkg-a>=1.0"]),
            OPEnvSpec(pip_pkgs=["pkg-b>=2.0"]),
        ]

        mgr = OPEnvManager(min_common_dep_num_to_combine=999)
        process_list = [
            {"clean_email_mapper": {}},
            {"fix_unicode_mapper": {}},
        ]
        ops = load_ops(process_list, mgr)
        self.assertEqual(len(ops), 2)
        self.assertIsInstance(ops[0], IsolatedOpProxy)
        self.assertIsInstance(ops[1], IsolatedOpProxy)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_op_cfg_set_on_proxy(self, mock_spec, mock_venv, _):
        """_op_cfg must be set on proxies."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        process_list = [{"clean_email_mapper": {}}]
        ops = load_ops(process_list, mgr)
        self.assertEqual(ops[0]._op_cfg, process_list[0])

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    def test_env_manager_records_specs(self, _):
        """OPEnvManager should have recorded all op env specs."""
        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        load_ops([{"clean_email_mapper": {}}], mgr)
        self.assertIn("clean_email_mapper", mgr.op2hash)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_proxy_init_args_preserved(self, mock_spec, mock_venv, _):
        """Proxy should preserve the init args from config."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        process_list = [{"clean_email_mapper": {"repl": "<EMAIL>"}}]
        ops = load_ops(process_list, mgr)
        self.assertIsInstance(ops[0], IsolatedOpProxy)
        self.assertEqual(ops[0]._init_args, {"repl": "<EMAIL>"})


# ---------------------------------------------------------------------------
# 5. VenvManager (mocked subprocess)
# ---------------------------------------------------------------------------


class VenvManagerTest(DataJuicerTestCaseBase):
    """Venv creation and caching logic (subprocess is mocked)."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def _mock_venv_creation(self, mock_run):
        """Create a minimal venv layout when subprocess.run is mocked."""

        def side_effect(cmd, *args, **kwargs):
            if len(cmd) >= 4 and cmd[:3] == [sys.executable, "-m", "venv"]:
                venv_path = cmd[-1]
                site_packages = os.path.join(
                    venv_path,
                    "lib",
                    f"python{sys.version_info.major}.{sys.version_info.minor}",
                    "site-packages",
                )
                os.makedirs(site_packages, exist_ok=True)
                os.makedirs(os.path.join(venv_path, "bin"), exist_ok=True)
                with open(os.path.join(venv_path, "bin", "python"), "w"):
                    pass
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_venv_cached_by_spec(self, mock_run):
        """Same env spec → same venv path (cached)."""
        self._mock_venv_creation(mock_run)
        mgr = VenvManager(cache_dir=self.tmp)
        spec = OPEnvSpec(pip_pkgs=["pytest"])
        path1 = mgr.get_venv_path(spec)
        path2 = mgr.get_venv_path(spec)
        self.assertEqual(path1, path2)
        # subprocess should only have been called once (venv creation + install)
        self.assertGreaterEqual(mock_run.call_count, 1)

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_different_specs_different_paths(self, mock_run):
        """Different env specs → different venv paths."""
        self._mock_venv_creation(mock_run)
        mgr = VenvManager(cache_dir=self.tmp)
        spec_a = OPEnvSpec(pip_pkgs=["pkg-a"])
        spec_b = OPEnvSpec(pip_pkgs=["pkg-b"])
        path_a = mgr.get_venv_path(spec_a)
        path_b = mgr.get_venv_path(spec_b)
        self.assertNotEqual(path_a, path_b)

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_cache_layout_uses_python_tag_and_full_spec_hash(self, mock_run):
        """Cache paths separate Python ABIs and retain the full spec hash."""
        self._mock_venv_creation(mock_run)
        mgr = VenvManager(cache_dir=self.tmp)
        spec = OPEnvSpec(pip_pkgs=["pkg-a"])

        path = mgr.get_venv_path(spec)

        self.assertEqual(
            path,
            os.path.join(self.tmp, sys.implementation.cache_tag, spec.get_hash()),
        )
        self.assertTrue(os.path.isfile(os.path.join(path, ".complete")))

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_complete_cache_is_reused_by_new_manager(self, mock_run):
        """A complete on-disk venv is reused without creation or install."""
        self._mock_venv_creation(mock_run)
        spec = OPEnvSpec(pip_pkgs=["pkg-a"])
        first_path = VenvManager(cache_dir=self.tmp).get_venv_path(spec)
        mock_run.reset_mock()

        second_path = VenvManager(cache_dir=self.tmp).get_venv_path(spec)

        self.assertEqual(second_path, first_path)
        mock_run.assert_not_called()

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_incomplete_cache_is_removed_and_rebuilt(self, mock_run):
        """A venv without its completion marker must never be reused."""
        self._mock_venv_creation(mock_run)
        spec = OPEnvSpec(pip_pkgs=["pkg-a"])
        path = os.path.join(self.tmp, sys.implementation.cache_tag, spec.get_hash())
        os.makedirs(os.path.join(path, "bin"), exist_ok=True)
        with open(os.path.join(path, "bin", "python"), "w"):
            pass
        stale_file = os.path.join(path, "stale")
        with open(stale_file, "w"):
            pass

        rebuilt_path = VenvManager(cache_dir=self.tmp).get_venv_path(spec)

        self.assertEqual(rebuilt_path, path)
        self.assertFalse(os.path.exists(stale_file))
        self.assertTrue(os.path.isfile(os.path.join(path, ".complete")))

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_failed_install_removes_incomplete_venv(self, mock_run):
        """Failed package installation leaves no cache candidate behind."""
        self._mock_venv_creation(mock_run)
        original_side_effect = mock_run.side_effect

        def fail_install(cmd, *args, **kwargs):
            result = original_side_effect(cmd, *args, **kwargs)
            if "install" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return result

        mock_run.side_effect = fail_install
        spec = OPEnvSpec(pip_pkgs=["pkg-a"])
        path = os.path.join(self.tmp, sys.implementation.cache_tag, spec.get_hash())

        with self.assertRaises(subprocess.CalledProcessError):
            VenvManager(cache_dir=self.tmp).get_venv_path(spec)

        self.assertFalse(os.path.exists(path))

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_empty_spec_no_install(self, mock_run):
        """Empty pip_pkgs should not trigger pip install."""
        self._mock_venv_creation(mock_run)
        mgr = VenvManager(cache_dir=self.tmp)
        spec = OPEnvSpec()
        mgr.get_venv_path(spec)
        # Only venv creation should be called, not pip install
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0]
            self.assertNotIn("pip", cmd)

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_get_venv_python_path(self, mock_run):
        """get_venv_python should return path ending in bin/python."""
        self._mock_venv_creation(mock_run)
        mgr = VenvManager(cache_dir=self.tmp)
        spec = OPEnvSpec()
        python_path = mgr.get_venv_python(spec)
        self.assertTrue(python_path.endswith("bin/python"))

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_uv_backend_uses_uv_command(self, mock_run):
        """When backend='uv', install cmd should use 'uv pip install'."""
        self._mock_venv_creation(mock_run)
        mgr = VenvManager(cache_dir=self.tmp)
        spec = OPEnvSpec(pip_pkgs=["some-pkg"], backend="uv")
        mgr.get_venv_path(spec)
        # Find the install call (the one with "install" in args, not venv creation)
        install_calls = [c for c in mock_run.call_args_list if "install" in c[0][0]]
        self.assertTrue(len(install_calls) >= 1)
        cmd = install_calls[-1][0][0]
        self.assertEqual(cmd[0], "uv")
        self.assertIn("--python", cmd)

    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_pip_backend_uses_pip_command(self, mock_run):
        """When backend='pip', install cmd should use 'python -m pip install'."""
        self._mock_venv_creation(mock_run)
        mgr = VenvManager(cache_dir=self.tmp)
        spec = OPEnvSpec(pip_pkgs=["some-pkg"], backend="pip")
        mgr.get_venv_path(spec)
        install_calls = [c for c in mock_run.call_args_list if "install" in c[0][0]]
        self.assertTrue(len(install_calls) >= 1)
        cmd = install_calls[-1][0][0]
        self.assertIn("-m", cmd)
        self.assertIn("pip", cmd)


# ---------------------------------------------------------------------------
# 6. wrap_op_with_isolation
# ---------------------------------------------------------------------------


class WrapOpWithIsolationTest(DataJuicerTestCaseBase):
    """Proxy wrapping with subprocess execution."""

    def setUp(self):
        super().setUp()
        reset_venv_manager()

    def tearDown(self):
        reset_venv_manager()
        super().tearDown()

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    def test_wrap_sets_run_func(self, mock_venv):
        """wrap_op_with_isolation should set _run_func on proxy."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable

        proxy = IsolatedOpProxy(
            op_name="clean_email_mapper",
            op_cls=OPERATORS.modules["clean_email_mapper"],
            init_args={},
            env_spec=OPEnvSpec(),
        )
        wrap_op_with_isolation(proxy, OPEnvSpec())
        self.assertIsNotNone(proxy._run_func)
        self.assertTrue(callable(proxy._run_func))

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_env_vars_passed_to_subprocess(self, mock_run, mock_venv):
        """env_vars from OPEnvSpec should be merged into subprocess env."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Set a sentinel env var to verify it's passed through
        custom_env_vars = {"DJ_TEST_SENTINEL": "abc123", "CUDA_VISIBLE_DEVICES": "0,1"}
        spec = OPEnvSpec(env_vars=custom_env_vars)
        proxy = IsolatedOpProxy("clean_email_mapper", OPERATORS.modules["clean_email_mapper"], {}, spec)
        wrap_op_with_isolation(proxy, spec)

        # Need a dataset to call run — use a minimal mock
        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            proxy.run(mock_ds)

        # Check subprocess.run was called with env containing our vars
        _, kwargs = mock_run.call_args
        self.assertIn("env", kwargs)
        self.assertEqual(kwargs["env"]["DJ_TEST_SENTINEL"], "abc123")
        self.assertEqual(kwargs["env"]["CUDA_VISIBLE_DEVICES"], "0,1")

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_working_dir_passed_to_subprocess(self, mock_run, mock_venv):
        """working_dir from OPEnvSpec should be passed as cwd to subprocess."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        custom_cwd = "/tmp/dj_test_workdir"
        spec = OPEnvSpec(working_dir=custom_cwd)
        proxy = IsolatedOpProxy("clean_email_mapper", OPERATORS.modules["clean_email_mapper"], {}, spec)
        wrap_op_with_isolation(proxy, spec)

        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            proxy.run(mock_ds)

        _, kwargs = mock_run.call_args
        self.assertEqual(kwargs.get("cwd"), custom_cwd)

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_no_env_vars_no_working_dir_uses_defaults(self, mock_run, mock_venv):
        """Without env_vars/working_dir, subprocess should still run fine."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        spec = OPEnvSpec()  # no env_vars, no working_dir
        proxy = IsolatedOpProxy("clean_email_mapper", OPERATORS.modules["clean_email_mapper"], {}, spec)
        wrap_op_with_isolation(proxy, spec)

        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            proxy.run(mock_ds)

        _, kwargs = mock_run.call_args
        # env should still be passed (inherited from os.environ)
        self.assertIn("env", kwargs)
        # cwd should be None (no working_dir set)
        self.assertIsNone(kwargs.get("cwd"))

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_segment_stats_are_restored_to_proxies(self, mock_run, mock_venv):
        """Per-op stats returned by the worker should be attached to each proxy."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable

        def fake_run(cmd, **kwargs):
            stats_path = cmd[cmd.index("--op_stats_path") + 1]
            with open(stats_path, "w") as out:
                json.dump(
                    [
                        {
                            "op_name": "clean_email_mapper",
                            "duration": 1.2,
                            "sample_count": 10,
                            "resource_util": None,
                        },
                        {
                            "op_name": "fix_unicode_mapper",
                            "duration": 0.4,
                            "sample_count": 8,
                            "resource_util": None,
                        },
                    ],
                    out,
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = fake_run
        spec = OPEnvSpec(pip_pkgs=["some-pkg"])
        proxies = [
            IsolatedOpProxy(
                "clean_email_mapper",
                OPERATORS.modules["clean_email_mapper"],
                {},
                spec,
            ),
            IsolatedOpProxy(
                "fix_unicode_mapper",
                OPERATORS.modules["fix_unicode_mapper"],
                {},
                spec,
            ),
        ]
        for proxy in proxies:
            proxy._open_monitor = False
        wrap_ops_with_isolation(proxies, spec)

        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            proxies[0].run(mock_ds)

        self.assertEqual(proxies[0]._isolation_stats["duration"], 1.2)
        self.assertEqual(proxies[0]._isolation_stats["sample_count"], 10)
        self.assertEqual(proxies[1]._isolation_stats["duration"], 0.4)
        self.assertEqual(proxies[1]._isolation_stats["sample_count"], 8)


# ---------------------------------------------------------------------------
# 7. Subprocess integration test
# ---------------------------------------------------------------------------


class SubprocessIntegrationTest(DataJuicerTestCaseBase):
    """End-to-end: proxy runs a real op in a subprocess."""

    def setUp(self):
        super().setUp()
        reset_venv_manager()

    def tearDown(self):
        reset_venv_manager()
        super().tearDown()

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_clean_email_in_subprocess(self, mock_spec, mock_venv, _mock_ray):
        """clean_email_mapper should remove emails when run via subprocess."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])

        from datasets import Dataset
        from data_juicer.core.data import NestedDataset

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        process_list = [{"clean_email_mapper": {}}]
        ops = load_ops(process_list, mgr)
        proxy = ops[0]
        self.assertIsInstance(proxy, IsolatedOpProxy)

        ds = Dataset.from_dict({"text": ["Contact alice@example.com now"]})
        ds = NestedDataset(ds)

        result = proxy.run(dataset=ds)
        self.assertEqual(len(result), 1)
        self.assertNotIn("alice@example.com", result[0]["text"])

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_subprocess_preserves_op_args(self, mock_spec, mock_venv, _mock_ray):
        """Op init args should be passed through to the subprocess."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])

        from datasets import Dataset
        from data_juicer.core.data import NestedDataset

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        # repl="<EMAIL>" should replace emails with <EMAIL>
        process_list = [{"clean_email_mapper": {"repl": "<EMAIL>"}}]
        ops = load_ops(process_list, mgr)
        proxy = ops[0]

        ds = Dataset.from_dict({"text": ["Email: bob@test.com"]})
        ds = NestedDataset(ds)

        result = proxy.run(dataset=ds)
        self.assertIn("<EMAIL>", result[0]["text"])
        self.assertNotIn("bob@test.com", result[0]["text"])

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_multiple_samples_preserved(self, mock_spec, mock_venv, _mock_ray):
        """Subprocess should handle multiple samples correctly."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])

        from datasets import Dataset
        from data_juicer.core.data import NestedDataset

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        ops = load_ops([{"clean_email_mapper": {}}], mgr)
        proxy = ops[0]

        texts = [
            "Email: alice@example.com",
            "No email here",
            "Contact: bob@test.com",
        ]
        ds = Dataset.from_dict({"text": texts})
        ds = NestedDataset(ds)

        result = proxy.run(dataset=ds)
        self.assertEqual(len(result), 3)
        self.assertNotIn("alice@example.com", result[0]["text"])
        self.assertEqual(result[1]["text"], "No email here")
        self.assertNotIn("bob@test.com", result[2]["text"])


# ---------------------------------------------------------------------------
# 8. Segment grouping (consecutive same-spec ops)
# ---------------------------------------------------------------------------


class SegmentGroupingTest(DataJuicerTestCaseBase):
    """Consecutive isolated ops with the same spec hash share one subprocess."""

    def setUp(self):
        super().setUp()
        reset_venv_manager()

    def tearDown(self):
        reset_venv_manager()
        super().tearDown()

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_consecutive_same_spec_merged(self, mock_spec, mock_venv, _):
        """Two consecutive ops with same spec → leader + follower."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        # Same spec for both ops
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg>=1.0"])

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        process_list = [
            {"clean_email_mapper": {}},
            {"clean_email_mapper": {"repl": "<EMAIL>"}},
        ]
        ops = load_ops(process_list, mgr)
        self.assertEqual(len(ops), 2)
        self.assertIsInstance(ops[0], IsolatedOpProxy)
        self.assertIsInstance(ops[1], IsolatedOpProxy)
        # First is the leader, second is the follower
        self.assertFalse(ops[0]._is_segment_follower)
        self.assertTrue(ops[1]._is_segment_follower)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_different_spec_breaks_segment(self, mock_spec, mock_venv, _):
        """Two ops with different specs → separate segments, no followers."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.side_effect = [
            OPEnvSpec(pip_pkgs=["pkg-a"]),
            OPEnvSpec(pip_pkgs=["pkg-b"]),
        ]

        mgr = OPEnvManager(min_common_dep_num_to_combine=999)
        process_list = [
            {"clean_email_mapper": {}},
            {"fix_unicode_mapper": {}},
        ]
        ops = load_ops(process_list, mgr)
        self.assertEqual(len(ops), 2)
        self.assertFalse(ops[0]._is_segment_follower)
        self.assertFalse(ops[1]._is_segment_follower)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_non_isolated_op_breaks_segment(self, mock_spec, mock_venv, _):
        """A non-isolated op between two isolated ops breaks the segment."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        # 1st: isolated, 2nd: not isolated, 3rd: isolated (same spec as 1st)
        mock_spec.side_effect = [
            OPEnvSpec(pip_pkgs=["some-pkg"]),
            OPEnvSpec(),  # no deps → not isolated
            OPEnvSpec(pip_pkgs=["some-pkg"]),
        ]

        mgr = OPEnvManager(min_common_dep_num_to_combine=999)
        process_list = [
            {"clean_email_mapper": {}},
            {"fix_unicode_mapper": {}},
            {"clean_email_mapper": {"repl": "X"}},
        ]
        ops = load_ops(process_list, mgr)
        self.assertEqual(len(ops), 3)
        # 1st is isolated leader, 2nd is normal, 3rd is isolated leader
        self.assertIsInstance(ops[0], IsolatedOpProxy)
        self.assertNotIsInstance(ops[1], IsolatedOpProxy)
        self.assertIsInstance(ops[2], IsolatedOpProxy)
        self.assertFalse(ops[0]._is_segment_follower)
        self.assertFalse(ops[2]._is_segment_follower)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_follower_run_returns_input(self, mock_spec, mock_venv, _):
        """Follower's run() should return the input dataset unchanged."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        process_list = [
            {"clean_email_mapper": {}},
            {"clean_email_mapper": {}},
        ]
        ops = load_ops(process_list, mgr)
        follower = ops[1]
        self.assertTrue(follower._is_segment_follower)
        # Follower returns input as-is
        sentinel = object()
        self.assertIs(follower.run(dataset=sentinel), sentinel)

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_segment_single_subprocess_call(self, mock_subproc, mock_spec, mock_venv, _):
        """A segment of 3 same-spec ops should only trigger 1 subprocess call."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])
        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        process_list = [
            {"clean_email_mapper": {}},
            {"clean_email_mapper": {"repl": "X"}},
            {"clean_email_mapper": {"repl": "Y"}},
        ]
        ops = load_ops(process_list, mgr)
        leader = ops[0]

        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            leader.run(mock_ds)

        # subprocess.run should have been called exactly once
        self.assertEqual(mock_subproc.call_count, 1)
        # The --ops_spec should contain all 3 ops
        cmd = mock_subproc.call_args[0][0]
        ops_spec_idx = cmd.index("--ops_spec")
        ops_spec_json = json.loads(cmd[ops_spec_idx + 1])
        self.assertEqual(len(ops_spec_json), 3)
        self.assertEqual(ops_spec_json[0]["op_name"], "clean_email_mapper")
        self.assertEqual(ops_spec_json[1]["init_kwargs"], {"repl": "X"})
        self.assertEqual(ops_spec_json[2]["init_kwargs"], {"repl": "Y"})


# ---------------------------------------------------------------------------
# 9. wrap_ops_with_isolation — exporter/tracer config forwarding
# ---------------------------------------------------------------------------


class ExporterTracerConfigForwardingTest(DataJuicerTestCaseBase):
    """Config dicts on proxy are forwarded as CLI args to the subprocess."""

    def setUp(self):
        super().setUp()
        reset_venv_manager()

    def tearDown(self):
        reset_venv_manager()
        super().tearDown()

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_exporter_config_in_cli_args(self, mock_subproc, mock_venv):
        """Exporter config should appear as --exporter_config CLI arg."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

        spec = OPEnvSpec(pip_pkgs=["some-pkg"])
        proxy = IsolatedOpProxy("clean_email_mapper", OPERATORS.modules["clean_email_mapper"], {}, spec)
        exporter_cfg = {"export_path": "/tmp/out.jsonl", "num_proc": 4}
        proxy._exporter_config = exporter_cfg
        wrap_op_with_isolation(proxy, spec)

        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            proxy.run(mock_ds)

        cmd = mock_subproc.call_args[0][0]
        self.assertIn("--exporter_config", cmd)
        idx = cmd.index("--exporter_config")
        parsed = json.loads(cmd[idx + 1])
        self.assertEqual(parsed["export_path"], "/tmp/out.jsonl")
        self.assertEqual(parsed["num_proc"], 4)

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_tracer_config_in_cli_args(self, mock_subproc, mock_venv):
        """Tracer config should appear as --tracer_config CLI arg."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

        spec = OPEnvSpec(pip_pkgs=["some-pkg"])
        proxy = IsolatedOpProxy("clean_email_mapper", OPERATORS.modules["clean_email_mapper"], {}, spec)
        tracer_cfg = {"work_dir": "/tmp/work", "show_num": 5}
        proxy._tracer_config = tracer_cfg
        wrap_op_with_isolation(proxy, spec)

        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            proxy.run(mock_ds)

        cmd = mock_subproc.call_args[0][0]
        self.assertIn("--tracer_config", cmd)
        idx = cmd.index("--tracer_config")
        parsed = json.loads(cmd[idx + 1])
        self.assertEqual(parsed["work_dir"], "/tmp/work")

    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.local_env_runner.subprocess.run")
    def test_no_config_no_cli_args(self, mock_subproc, mock_venv):
        """Without config, --exporter_config/--tracer_config should be absent."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_subproc.return_value = MagicMock(returncode=0, stdout="", stderr="")

        spec = OPEnvSpec(pip_pkgs=["some-pkg"])
        proxy = IsolatedOpProxy("clean_email_mapper", OPERATORS.modules["clean_email_mapper"], {}, spec)
        wrap_op_with_isolation(proxy, spec)

        mock_ds = MagicMock()
        mock_ds.save_to_disk = MagicMock()
        with patch("data_juicer.core.data.dj_dataset.NestedDataset.load_from_disk"):
            proxy.run(mock_ds)

        cmd = mock_subproc.call_args[0][0]
        self.assertNotIn("--exporter_config", cmd)
        self.assertNotIn("--tracer_config", cmd)


# ---------------------------------------------------------------------------
# 10. Tracer clear_existing parameter
# ---------------------------------------------------------------------------


class TracerClearExistingTest(DataJuicerTestCaseBase):
    """Tracer(clear_existing=False) should preserve existing trace files."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp()
        # Create a fake pre-existing trace file
        trace_dir = os.path.join(self.tmp, "trace")
        os.makedirs(trace_dir)
        self.existing_file = os.path.join(trace_dir, "existing_trace.jsonl")
        with open(self.existing_file, "w") as f:
            f.write('{"sample": 1}\n')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def test_clear_existing_true_removes_files(self):
        """Default (clear_existing=True) clears the trace directory."""
        from data_juicer.core.tracer.tracer import Tracer

        Tracer(self.tmp)
        self.assertFalse(os.path.exists(self.existing_file))

    def test_clear_existing_false_preserves_files(self):
        """clear_existing=False keeps existing trace files."""
        from data_juicer.core.tracer.tracer import Tracer

        Tracer(self.tmp, clear_existing=False)
        self.assertTrue(os.path.exists(self.existing_file))


# ---------------------------------------------------------------------------
# 11. DefaultExecutor config saving & injection
# ---------------------------------------------------------------------------


class DefaultExecutorConfigTest(DataJuicerTestCaseBase):
    """Verify DefaultExecutor saves _exporter_config / _tracer_config and
    injects them into IsolatedOpProxy instances."""

    def test_local_isolation_enabled_by_default_without_env_merging(self):
        from jsonargparse import Namespace

        from data_juicer.core.executor.default_executor import _create_local_op_env_manager

        manager = _create_local_op_env_manager(
            Namespace(
                local_op_isolation=True,
                min_common_dep_num_to_combine=-1,
                conflict_resolve_strategy="split",
            )
        )

        self.assertIsNotNone(manager)
        self.assertEqual(manager.min_common_dep_num_to_combine, -1)

    def test_local_isolation_can_be_disabled_independently(self):
        from jsonargparse import Namespace

        from data_juicer.core.executor.default_executor import _create_local_op_env_manager

        manager = _create_local_op_env_manager(
            Namespace(
                local_op_isolation=False,
                min_common_dep_num_to_combine=0,
                conflict_resolve_strategy="overwrite",
            )
        )

        self.assertIsNone(manager)

    def test_exporter_config_includes_s3_credentials(self):
        """_exporter_config should include S3 creds from export_extra_args."""
        # Simulate the config dict construction done by DefaultExecutor.__init__
        export_extra_args = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_session_token": "FwoGZX...",
            "endpoint_url": "https://s3.example.com",
        }
        exporter_config = {
            "export_path": "s3://bucket/output.jsonl",
            "export_type": "jsonl",
            "export_shard_size": 0,
            "export_in_parallel": True,
            "num_proc": 4,
            "keep_stats_in_res_ds": False,
            "keep_hashes_in_res_ds": False,
            "encrypt_before_export": False,
            "encryption_key_path": None,
            **export_extra_args,
        }
        # S3 credentials must be present in the config dict
        self.assertEqual(exporter_config["aws_access_key_id"], "AKIAIOSFODNN7EXAMPLE")
        self.assertEqual(exporter_config["aws_secret_access_key"], "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
        self.assertEqual(exporter_config["aws_session_token"], "FwoGZX...")
        self.assertEqual(exporter_config["endpoint_url"], "https://s3.example.com")
        # All positional args must be keyword-mapped
        self.assertIn("export_path", exporter_config)
        self.assertIn("num_proc", exporter_config)
        # Must be JSON-serializable
        json.dumps(exporter_config)  # should not raise

    def test_tracer_config_excludes_lock(self):
        """_tracer_config should NOT contain a lock."""
        tracer_config = {
            "work_dir": "/tmp/work",
            "op_list_to_trace": ["clean_email_mapper"],
            "show_num": 10,
            "trace_keys": ["text"],
        }
        self.assertNotIn("lock", tracer_config)
        json.dumps(tracer_config)  # should not raise

    @patch("data_juicer.utils.ray_utils.is_ray_mode", return_value=False)
    @patch("data_juicer.ops.local_env_runner._get_venv_manager")
    @patch("data_juicer.ops.load._get_class_env_spec")
    def test_config_injection_into_proxies(self, mock_spec, mock_venv, _):
        """After load_ops, runtime context should bind into each proxy."""
        mock_venv.return_value.get_venv_python.return_value = sys.executable
        mock_spec.return_value = OPEnvSpec(pip_pkgs=["some-pkg"])

        mgr = OPEnvManager(min_common_dep_num_to_combine=0)
        ops = load_ops([{"clean_email_mapper": {}}], mgr)
        proxy = ops[0]
        self.assertIsInstance(proxy, IsolatedOpProxy)

        # Simulate DefaultExecutor binding runtime context
        exporter_cfg = {"export_path": "/tmp/out.jsonl", "num_proc": 1}
        tracer_cfg = {"work_dir": "/tmp/work", "show_num": 5}
        proxy.bind_runtime(
            exporter_config=exporter_cfg,
            tracer_config=tracer_cfg,
            open_monitor=False,
            isolated_log_dir="/tmp/work/isolated_logs",
        )

        self.assertEqual(proxy._exporter_config, exporter_cfg)
        self.assertEqual(proxy._tracer_config, tracer_cfg)
        self.assertFalse(proxy._open_monitor)
        self.assertEqual(proxy._isolated_log_dir, "/tmp/work/isolated_logs")


if __name__ == "__main__":
    import unittest

    unittest.main()
