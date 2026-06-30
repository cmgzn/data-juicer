import json
import os
import shutil
import tempfile
import threading
import time
from types import SimpleNamespace

import numpy as np
from datasets import Dataset

from data_juicer.core import exporter as exporter_module
from data_juicer.core.executor import event_logging_mixin as event_module
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class CoreExporterFileTest(DataJuicerTestCaseBase):
    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp(prefix="dj_exporter_file_")
        self.Exporter = exporter_module.Exporter
        self.Fields = exporter_module.Fields
        self.HashKeys = exporter_module.HashKeys
        self.dataset = Dataset.from_list([
            {
                "text": "text 1",
                self.Fields.stats: {"score": 1},
                self.Fields.meta: {"source": "a"},
                self.HashKeys.hash: "h1",
            },
            {
                "text": "text 2",
                self.Fields.stats: {"score": 2},
                self.Fields.meta: {"source": "b"},
                self.HashKeys.hash: "h2",
            },
            {
                "text": "text 3",
                self.Fields.stats: {"score": 3},
                self.Fields.meta: {"source": "c"},
                self.HashKeys.hash: "h3",
            },
        ])

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        super().tearDown()

    def test_meta_stats_json_strings_are_restored_before_export(self):
        ds = Dataset.from_dict({
            self.Fields.meta: ['{"source": "zh"}', '{"source": "en"}'],
            self.Fields.stats: ['{"score": 1}', '{"score": 2}'],
        })

        fixed = self.Exporter._ensure_meta_stats_dicts_for_export(ds)

        self.assertEqual(fixed[0][self.Fields.meta], {"source": "zh"})
        self.assertEqual(fixed[0][self.Fields.stats], {"score": 1})
        self.assertEqual(fixed[1][self.Fields.meta], {"source": "en"})
        self.assertEqual(fixed[1][self.Fields.stats], {"score": 2})

    def test_invalid_meta_stats_json_strings_are_left_unchanged(self):
        ds = Dataset.from_dict({
            self.Fields.meta: ["not-json"],
            self.Fields.stats: ["also-not-json"],
        })

        fixed = self.Exporter._ensure_meta_stats_dicts_for_export(ds)

        self.assertEqual(fixed[0][self.Fields.meta], "not-json")
        self.assertEqual(fixed[0][self.Fields.stats], "also-not-json")

    def test_meta_stats_restore_is_noop_without_columns(self):
        ds = Dataset.from_list([{"text": "plain"}])

        self.assertIs(self.Exporter._ensure_meta_stats_dicts_for_export(ds), ds)

    def test_row_to_json_serializable_handles_scalars_lists_and_arrow_values(self):
        class ArrowLike:
            def as_py(self):
                return {"nested": np.int64(3)}

        class ListLike:
            def tolist(self):
                return [1, 2]

        row = {
            "scalar": np.int64(7),
            "array": ListLike(),
            "nested": [ArrowLike()],
        }

        self.assertEqual(
            self.Exporter._row_to_json_serializable(row),
            {"scalar": 7, "array": [1, 2], "nested": [{"nested": 3}]},
        )

    def test_json_jsonl_parquet_exports_and_filtered_shards(self):
        jsonl_path = os.path.join(self.tmp_dir, "out.jsonl")
        json_path = os.path.join(self.tmp_dir, "out.json")
        parquet_path = os.path.join(self.tmp_dir, "out.parquet")
        shard_path = os.path.join(self.tmp_dir, "shards", "out.jsonl")

        self.Exporter.to_jsonl(self.dataset, jsonl_path)
        self.Exporter.to_json(self.dataset, json_path, num_proc=1)
        self.Exporter.to_parquet(self.dataset, parquet_path)

        with open(jsonl_path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        self.assertEqual(rows[0]["text"], "text 1")
        self.assertTrue(os.path.exists(json_path))
        self.assertTrue(os.path.exists(parquet_path))

        filtered = self.dataset.filter(lambda row: row["text"] != "text 2")
        exporter = self.Exporter(
            export_path=shard_path,
            export_shard_size=1,
            export_in_parallel=False,
            num_proc=1,
            export_ds=True,
            keep_stats_in_res_ds=False,
            keep_hashes_in_res_ds=False,
            export_stats=False,
        )
        exporter.export(filtered)

        shard_files = os.listdir(os.path.dirname(shard_path))
        self.assertTrue(any(name.endswith(".jsonl") for name in shard_files))


class CoreEventLoggingFileTest(DataJuicerTestCaseBase):
    class ConcreteExecutor(event_module.EventLoggingMixin):
        def __init__(self, work_dir, enabled=True, job_id="job-real"):
            self.cfg = SimpleNamespace(
                event_logging={"enabled": enabled},
                job_id=job_id,
                config="/tmp/Config With Spaces.yaml",
                project_name="project/name with spaces",
            )
            self.work_dir = work_dir
            self.executor_type = "unit"
            super().__init__()

        def _get_dag_node_for_operation(self, operation_name, operation_idx, partition_id=None):
            return f"{partition_id}:{operation_idx}:{operation_name}"

    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp(prefix="dj_event_logging_file_")
        self.work_dir = os.path.join(self.tmp_dir, "job")
        self.EventType = event_module.EventType

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        super().tearDown()

    def write_summary(self, executor):
        os.makedirs(executor.work_dir, exist_ok=True)
        summary = {
            "job_id": executor.cfg.job_id,
            "start_time": time.time() - 10,
            "resumption_command": "dj-process --config cfg.yaml",
        }
        with open(os.path.join(executor.work_dir, "job_summary.json"), "w") as f:
            json.dump(summary, f)

    def test_lifecycle_methods_write_events_summary_and_status(self):
        executor = self.ConcreteExecutor(self.work_dir)
        self.write_summary(executor)
        node_info = {
            "op_name": "clean",
            "op_type": "mapper",
            "dependencies_count": 1,
            "dependents_count": 2,
            "execution_order": 3,
        }
        group_info = {
            "node_count": 2,
            "node_ids": ["n1", "n2"],
            "op_types": ["mapper"],
            "completed_nodes": 1,
            "failed_nodes": 1,
        }
        plan_info = {
            "node_count": 2,
            "edge_count": 1,
            "parallel_groups_count": 1,
            "execution_plan_length": 2,
        }

        executor.log_job_start({"dataset_path": "data.jsonl", "executor_type": "unit"}, 2)
        executor.log_partition_start(0, {"partition_path": "part.jsonl", "sample_count": 4})
        executor.log_partition_complete(0, 1.5, "out/0.jsonl", success=True)
        executor.log_partition_complete(1, 2.0, "out/1.jsonl", success=False, error="bad rows")
        executor.log_partition_failed(1, "bad rows", retry_count=2)
        executor.log_op_start(0, "clean", 1, {"threshold": 0.7}, metadata={"custom": "yes"})
        executor.log_op_complete(0, "clean", 1, 0.5, "ckpt/clean.pkl", 10, 7)
        executor.log_op_failed(1, "clean", 1, "boom", 3)
        executor.log_checkpoint_save(0, "clean", 1, "ckpt/save.pkl")
        executor.log_checkpoint_load(0, "clean", 1, "ckpt/save.pkl")
        executor.log_dag_build_start({"node_count": 2, "depth": 1, "operation_types": ["mapper"]})
        executor.log_dag_build_complete({"node_count": 2, "edge_count": 1, "parallel_groups_count": 1})
        executor.log_dag_node_ready("n1", node_info)
        executor.log_dag_node_start("n1", node_info)
        executor.log_dag_node_complete("n1", node_info, 0.25)
        executor.log_dag_node_failed("n2", node_info, "node failed", duration=0.75)
        executor.log_dag_parallel_group_start("g1", group_info)
        executor.log_dag_parallel_group_complete("g1", group_info, 1.25)
        executor.log_dag_execution_plan_saved("plan.json", plan_info)
        executor.log_dag_execution_plan_loaded("plan.json", plan_info)
        executor.log_job_restart("manual", 1.0, [1], 2, ["ckpt/save.pkl"])
        executor.log_partition_resume(1, 2, "ckpt/save.pkl", "retry failed partition")
        executor.log_job_complete(3.0, output_path="out")
        executor.log_job_failed("late failure marker", 4.0)

        events = executor.get_events()
        self.assertGreaterEqual(len(events), 20)
        self.assertTrue(os.path.exists(executor.event_logger.jsonl_file))
        op_start = executor.get_events(event_type=self.EventType.OP_START)[0]
        self.assertEqual(op_start.metadata["dag_node_id"], "0:1:clean")
        self.assertEqual(executor._get_config_name(), "Config_With_Spaces")
        self.assertIn("Total Events:", executor.generate_status_report())

        with open(os.path.join(executor.work_dir, "job_summary.json")) as f:
            summary = json.load(f)
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["error_message"], "late failure marker")

    def test_resumption_analysis_uses_real_event_log(self):
        executor = self.ConcreteExecutor(self.work_dir, job_id="resume-job")
        start = time.time() - 20
        raw_events = [
            {"event_type": "job_start", "timestamp": start},
            {"event_type": "partition_start", "timestamp": start + 1, "partition_id": 0},
            {
                "event_type": "op_start",
                "timestamp": start + 2,
                "partition_id": 0,
                "operation_name": "clean",
                "operation_idx": 0,
            },
            {
                "event_type": "op_complete",
                "timestamp": start + 3,
                "partition_id": 0,
                "operation_name": "clean",
                "operation_idx": 0,
            },
            {
                "event_type": "partition_complete",
                "timestamp": start + 4,
                "partition_id": 0,
                "metadata": {
                    "success": True,
                    "duration_seconds": 3,
                    "output_path": "out/0.jsonl",
                },
            },
            {"event_type": "partition_start", "timestamp": start + 5, "partition_id": 1},
            {
                "event_type": "partition_complete",
                "timestamp": start + 6,
                "partition_id": 1,
                "metadata": {
                    "success": False,
                    "error": "bad rows",
                    "duration_seconds": 1,
                },
            },
            {"event_type": "partition_failed", "timestamp": start + 7, "partition_id": 1},
            {
                "event_type": "checkpoint_saved",
                "timestamp": start + 8,
                "metadata": {"checkpoint_path": "ckpt/latest.pkl"},
            },
        ]
        with open(executor.event_logger.jsonl_file, "w") as f:
            for event in raw_events:
                f.write(json.dumps(event) + "\n")
            f.write("not-json\n")

        analysis = executor.analyze_resumption_state("resume-job")

        self.assertEqual(analysis["job_status"], "completed_with_failures")
        self.assertTrue(analysis["can_resume"])
        self.assertEqual(analysis["resume_from_checkpoint"], "ckpt/latest.pkl")
        self.assertEqual(analysis["partitions_to_retry"], [1])
        self.assertEqual(analysis["partitions_to_skip"], [0])
        self.assertEqual(analysis["progress_metrics"]["completed_partitions"], 1)

    def test_event_logger_queries_reports_and_job_discovery(self):
        logger = event_module.EventLogger(self.tmp_dir, job_id="events-job", work_dir=self.tmp_dir)
        Event = event_module.Event

        first = Event(
            self.EventType.OP_COMPLETE,
            timestamp=time.time() - 2,
            message="finished clean",
            partition_id=1,
            operation_name="clean",
            duration="slow",
            output_path="/tmp/out.jsonl",
            metadata={"status": "success", "operation_class": "clean"},
        )
        second = Event(
            self.EventType.JOB_FAILED,
            timestamp=time.time() - 1,
            message="job failed",
            error_message="bad rows",
        )
        logger.log_event(first)
        logger.log_event(second)

        formatted = logger._format_event_for_logging(first)
        self.assertIn("DURATION[slow]", formatted)
        self.assertIn("OUTPUT[out.jsonl]", formatted)
        self.assertIn("META[", formatted)
        self.assertEqual(logger.get_events(partition_id=1), [first])
        self.assertEqual(logger.get_events(operation_name="clean"), [first])
        self.assertEqual(logger.get_events(event_type=self.EventType.JOB_FAILED), [second])
        self.assertEqual(logger.get_events(start_time=second.timestamp - 0.1, limit=1), [second])
        self.assertEqual(logger.generate_status_report().count("job_failed"), 1)

        os.makedirs(os.path.join(self.tmp_dir, "job-ok"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp_dir, "job-bad"), exist_ok=True)
        with open(os.path.join(self.tmp_dir, "job-ok", "job_summary.json"), "w") as f:
            json.dump({"job_id": "job-ok", "status": "completed"}, f)
        with open(os.path.join(self.tmp_dir, "job-bad", "job_summary.json"), "w") as f:
            f.write("{bad json")

        jobs = event_module.EventLogger.list_available_jobs(self.tmp_dir)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], "job-ok")
        self.assertTrue(jobs[0]["work_dir"].endswith("job-ok"))
        self.assertIsNone(logger.find_latest_events_file(os.path.join(self.tmp_dir, "missing")))
        self.assertEqual(logger.find_latest_events_file(self.tmp_dir), logger.jsonl_file)
        self.assertTrue(logger.check_job_completion(logger.jsonl_file) is False)

    def test_event_monitor_yields_new_real_events(self):
        logger = event_module.EventLogger(self.tmp_dir, job_id="monitor-job", work_dir=self.tmp_dir)
        Event = event_module.Event
        stream = logger.monitor_events(self.EventType.PARTITION_START)

        def write_event():
            time.sleep(0.05)
            logger.log_event(
                Event(
                    self.EventType.PARTITION_START,
                    timestamp=time.time(),
                    message="partition starts",
                    partition_id=3,
                )
            )

        writer = threading.Thread(target=write_event)
        writer.start()
        try:
            event = next(stream)
        finally:
            writer.join()

        self.assertEqual(event.partition_id, 3)

    def test_resumption_helpers_cover_terminal_and_empty_states(self):
        disabled = self.ConcreteExecutor(self.work_dir, enabled=False)
        self.assertEqual(disabled.get_events(), [])
        self.assertEqual(disabled.generate_status_report(), "Event logging is disabled.")
        self.assertEqual(list(disabled.monitor_events()), [])
        self.assertEqual(disabled.analyze_resumption_state("disabled"), {"error": "Event logger not available"})

        executor = self.ConcreteExecutor(self.work_dir, job_id="helper-job")
        missing = executor.analyze_resumption_state("helper-job")
        self.assertIn("Events file not found", missing["error"])

        executor.cfg.config = ""
        executor.cfg.project_name = "project/name with spaces and extra suffix"
        self.assertEqual(executor._get_config_name(), "project_name_wi")

        for events, completes, failures, expected in [
            ([{"event_type": "job_complete"}], [], [], "completed"),
            ([{"event_type": "job_failed"}], [], [], "failed"),
            ([], [{"metadata": {"success": False}}], [], "running"),
            ([], [], [], "not_started"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(executor._determine_job_status(events, completes, failures), expected)

        running_state = executor._determine_partition_state(
            2,
            {"timestamp": 1.0},
            [],
            [],
            [{"timestamp": 2.0, "operation_name": "normalize", "operation_idx": 4}],
            [],
        )
        self.assertEqual(running_state["status"], "running")
        self.assertEqual(running_state["current_operation"]["name"], "normalize")
        self.assertFalse(running_state["current_operation"]["completed"])

        completed_plan = executor._generate_resumption_plan({0: {"status": "completed"}}, [], "completed")
        failed_plan = executor._generate_resumption_plan({1: {"status": "failed"}}, [], "failed")
        checkpoint_plan = executor._generate_resumption_plan(
            {2: {"status": "running"}},
            [{"timestamp": 1.0, "metadata": {"checkpoint_path": "ckpt/latest.pkl"}}],
            "running",
        )
        empty_plan = executor._generate_resumption_plan({}, [], "running")
        self.assertFalse(completed_plan["can_resume"])
        self.assertTrue(failed_plan["can_resume"])
        self.assertEqual(checkpoint_plan["resume_from_checkpoint"], "ckpt/latest.pkl")
        self.assertFalse(empty_plan["can_resume"])
        self.assertEqual(executor._calculate_progress_metrics({}, [])["progress_percentage"], 0)

    def test_dag_context_absent_or_failed_is_non_fatal(self):
        class NoDagNodeExecutor(self.ConcreteExecutor):
            def _get_dag_node_for_operation(self, operation_name, operation_idx, partition_id=None):
                return None

        class FailingDagNodeExecutor(self.ConcreteExecutor):
            def _get_dag_node_for_operation(self, operation_name, operation_idx, partition_id=None):
                raise RuntimeError("dag lookup failed")

        for executor_cls in [NoDagNodeExecutor, FailingDagNodeExecutor]:
            with self.subTest(executor=executor_cls.__name__):
                executor = executor_cls(self.work_dir)
                metadata = {}
                executor._add_dag_context_to_metadata(metadata, "clean", 0, 0)
                self.assertEqual(metadata, {})
