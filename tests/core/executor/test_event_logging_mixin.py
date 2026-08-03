import json
import os
import tempfile
import threading
import time
import unittest

from data_juicer.core.executor.event_logging_mixin import (
    Event,
    EventLogger,
    EventLoggingMixin,
    EventType,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, TEST_TAG


@TEST_TAG("standalone")
class EventTypeTest(DataJuicerTestCaseBase):

    def test_all_event_types_have_values(self):
        for et in EventType:
            self.assertIsInstance(et.value, str)
            self.assertTrue(len(et.value) > 0)

    def test_key_event_types_exist(self):
        self.assertEqual(EventType.JOB_START.value, "job_start")
        self.assertEqual(EventType.JOB_COMPLETE.value, "job_complete")
        self.assertEqual(EventType.OP_START.value, "op_start")
        self.assertEqual(EventType.DAG_NODE_START.value, "dag_node_start")


@TEST_TAG("standalone")
class EventLoggerTest(DataJuicerTestCaseBase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.logger = EventLogger(self.tmp_dir, job_id="test-job-001")

    def test_init(self):
        self.assertEqual(self.logger.job_id, "test-job-001")
        self.assertTrue(self.logger.log_dir.exists())
        self.assertTrue(str(self.logger.jsonl_file).endswith(".jsonl"))

    def test_init_auto_job_id(self):
        logger = EventLogger(self.tmp_dir)
        self.assertIn("-", logger.job_id)

    def test_init_with_work_dir(self):
        work_dir = os.path.join(self.tmp_dir, "work")
        logger = EventLogger(self.tmp_dir, work_dir=work_dir)
        self.assertEqual(str(logger.jsonl_dir), work_dir)

    def test_log_event(self):
        event = Event(
            event_type=EventType.JOB_START,
            timestamp=time.time(),
            message="Job started",
        )
        self.logger.log_event(event)
        self.assertEqual(len(self.logger.events), 1)
        self.assertEqual(self.logger.events[0].job_id, "test-job-001")

    def test_log_event_writes_jsonl(self):
        event = Event(
            event_type=EventType.JOB_START,
            timestamp=time.time(),
            message="test",
        )
        self.logger.log_event(event)
        with open(self.logger.jsonl_file) as f:
            line = f.readline()
        data = json.loads(line)
        self.assertEqual(data["event_type"], "job_start")
        self.assertEqual(data["message"], "test")

    def test_get_events_no_filter(self):
        for i in range(3):
            self.logger.log_event(Event(
                event_type=EventType.OP_START,
                timestamp=time.time(),
                message=f"op {i}",
            ))
        events = self.logger.get_events()
        self.assertEqual(len(events), 3)

    def test_get_events_filter_by_type(self):
        self.logger.log_event(Event(
            event_type=EventType.JOB_START, timestamp=time.time(), message="a"))
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=time.time(), message="b"))
        events = self.logger.get_events(event_type=EventType.OP_START)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].message, "b")

    def test_get_events_filter_by_partition(self):
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=time.time(),
            message="p0", partition_id=0))
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=time.time(),
            message="p1", partition_id=1))
        events = self.logger.get_events(partition_id=0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].message, "p0")

    def test_get_events_filter_by_operation(self):
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=time.time(),
            message="a", operation_name="filter"))
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=time.time(),
            message="b", operation_name="mapper"))
        events = self.logger.get_events(operation_name="filter")
        self.assertEqual(len(events), 1)

    def test_get_events_filter_by_time(self):
        t1 = time.time()
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=t1, message="old"))
        t2 = t1 + 10
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=t2, message="new"))
        events = self.logger.get_events(start_time=t1 + 5)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].message, "new")

    def test_get_events_with_limit(self):
        for i in range(10):
            self.logger.log_event(Event(
                event_type=EventType.OP_START, timestamp=time.time(),
                message=f"m{i}"))
        events = self.logger.get_events(limit=3)
        self.assertEqual(len(events), 3)

    def test_generate_status_report_empty(self):
        report = self.logger.generate_status_report()
        self.assertEqual(report, "No events logged yet.")

    def test_generate_status_report_with_events(self):
        self.logger.log_event(Event(
            event_type=EventType.JOB_START, timestamp=time.time(), message="a"))
        self.logger.log_event(Event(
            event_type=EventType.OP_START, timestamp=time.time(), message="b"))
        report = self.logger.generate_status_report()
        self.assertIn("Total Events: 2", report)
        self.assertIn("job_start", report)
        self.assertIn("op_start", report)

    def test_format_event_basic(self):
        event = Event(
            event_type=EventType.JOB_START,
            timestamp=1700000000.0,
            message="test msg",
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("EVENT[job_start]", formatted)
        self.assertIn("MSG[test msg]", formatted)

    def test_format_event_with_duration(self):
        event = Event(
            event_type=EventType.OP_COMPLETE,
            timestamp=time.time(),
            message="done",
            duration=1.234,
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("DURATION[1.234s]", formatted)

    def test_format_event_with_partition(self):
        event = Event(
            event_type=EventType.OP_START,
            timestamp=time.time(),
            message="x",
            partition_id=5,
            operation_name="filter",
            operation_idx=2,
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("PARTITION[5]", formatted)
        self.assertIn("OP[filter]", formatted)
        self.assertIn("OP_IDX[2]", formatted)

    def test_format_event_with_error(self):
        event = Event(
            event_type=EventType.OP_FAILED,
            timestamp=time.time(),
            message="failed",
            error_message="timeout",
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("ERROR[timeout]", formatted)

    def test_format_event_with_checkpoint(self):
        event = Event(
            event_type=EventType.CHECKPOINT_SAVE,
            timestamp=time.time(),
            message="saved",
            checkpoint_path="/tmp/cp/data.parquet",
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("CHECKPOINT[data.parquet]", formatted)

    def test_format_event_with_output_path(self):
        event = Event(
            event_type=EventType.JOB_COMPLETE,
            timestamp=time.time(),
            message="done",
            output_path="/out/result.json",
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("OUTPUT[result.json]", formatted)

    def test_format_event_with_metadata(self):
        event = Event(
            event_type=EventType.OP_START,
            timestamp=time.time(),
            message="x",
            metadata={"status": "running", "retry_count": 2},
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("META[", formatted)

    def test_format_event_duration_as_string(self):
        event = Event(
            event_type=EventType.OP_COMPLETE,
            timestamp=time.time(),
            message="done",
            duration="unknown",
        )
        formatted = self.logger._format_event_for_logging(event)
        self.assertIn("DURATION[unknown]", formatted)

    def test_find_latest_events_file(self):
        self.logger.log_event(Event(
            event_type=EventType.JOB_START, timestamp=time.time(), message="x"))
        result = self.logger.find_latest_events_file(self.tmp_dir)
        self.assertIsNotNone(result)
        self.assertTrue(str(result).endswith(".jsonl"))

    def test_find_latest_events_file_nonexistent_dir(self):
        result = self.logger.find_latest_events_file("/nonexistent/path")
        self.assertIsNone(result)

    def test_find_latest_events_file_no_files(self):
        empty_dir = os.path.join(self.tmp_dir, "empty")
        os.makedirs(empty_dir)
        result = self.logger.find_latest_events_file(empty_dir)
        self.assertIsNone(result)

    def test_check_job_completion_false(self):
        self.logger.log_event(Event(
            event_type=EventType.JOB_START, timestamp=time.time(), message="s"))
        self.assertFalse(self.logger.check_job_completion(self.logger.jsonl_file))

    def test_check_job_completion_true(self):
        self.logger.log_event(Event(
            event_type=EventType.JOB_COMPLETE, timestamp=time.time(), message="d"))
        self.assertTrue(self.logger.check_job_completion(self.logger.jsonl_file))

    def test_check_job_completion_nonexistent_file(self):
        from pathlib import Path
        self.assertFalse(self.logger.check_job_completion(Path("/nonexistent")))

    def test_thread_safety(self):
        def log_events(n):
            for i in range(n):
                self.logger.log_event(Event(
                    event_type=EventType.OP_START,
                    timestamp=time.time(),
                    message=f"thread-{threading.current_thread().name}-{i}",
                ))

        threads = [threading.Thread(target=log_events, args=(10,)) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(self.logger.events), 40)

    def test_list_available_jobs_empty(self):
        jobs = EventLogger.list_available_jobs(self.tmp_dir)
        self.assertEqual(jobs, [])

    def test_list_available_jobs_nonexistent(self):
        jobs = EventLogger.list_available_jobs("/nonexistent")
        self.assertEqual(jobs, [])

    def test_list_available_jobs_with_summary(self):
        job_dir = os.path.join(self.tmp_dir, "job_001")
        os.makedirs(job_dir)
        summary = {"job_id": "001", "status": "completed"}
        with open(os.path.join(job_dir, "job_summary.json"), "w") as f:
            json.dump(summary, f)
        jobs = EventLogger.list_available_jobs(self.tmp_dir)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], "001")
        self.assertIn("work_dir", jobs[0])


@TEST_TAG("standalone")
class EventLoggingMixinTest(DataJuicerTestCaseBase):

    def _make_mixin(self):
        """Create an EventLoggingMixin with minimal config."""
        tmp_dir = tempfile.mkdtemp()
        work_dir = os.path.join(tmp_dir, "work")
        os.makedirs(work_dir, exist_ok=True)

        class FakeCfg:
            event_logging = {"enabled": True}
            job_id = "test-job"

        mixin = object.__new__(EventLoggingMixin)
        mixin.cfg = FakeCfg()
        mixin.work_dir = work_dir
        mixin.executor_type = "test"
        mixin._setup_event_logging()
        return mixin

    def _make_disabled_mixin(self):
        class FakeCfg:
            event_logging = {"enabled": False}

        mixin = object.__new__(EventLoggingMixin)
        mixin.cfg = FakeCfg()
        mixin.work_dir = "/tmp"
        mixin.executor_type = "test"
        mixin._setup_event_logging()
        return mixin

    def test_setup_creates_logger(self):
        mixin = self._make_mixin()
        self.assertIsNotNone(mixin.event_logger)

    def test_setup_disabled(self):
        mixin = self._make_disabled_mixin()
        self.assertIsNone(mixin.event_logger)

    def test_log_event_disabled_does_not_crash(self):
        mixin = self._make_disabled_mixin()
        mixin._log_event(EventType.JOB_START, "test")

    def test_log_event_creates_event(self):
        mixin = self._make_mixin()
        mixin._log_event(EventType.JOB_START, "started")
        events = mixin.event_logger.get_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, EventType.JOB_START)

    def test_log_event_captures_pid_and_tid(self):
        mixin = self._make_mixin()
        mixin._log_event(EventType.JOB_START, "test")
        event = mixin.event_logger.events[0]
        self.assertEqual(event.process_id, os.getpid())
        self.assertEqual(event.thread_id, threading.get_ident())

    def test_log_job_start(self):
        mixin = self._make_mixin()
        config = {"executor_type": "default", "dataset_path": "/data"}
        mixin.log_job_start(config, total_partitions=4)
        events = mixin.event_logger.get_events(event_type=EventType.JOB_START)
        self.assertEqual(len(events), 1)

    def test_log_job_complete(self):
        mixin = self._make_mixin()
        mixin.log_job_complete(duration=10.5, output_path="/out")
        events = mixin.event_logger.get_events(event_type=EventType.JOB_COMPLETE)
        self.assertEqual(len(events), 1)
        self.assertIn("10.50s", events[0].message)

    def test_log_job_failed(self):
        mixin = self._make_mixin()
        mixin.log_job_failed("OOM error", duration=5.0)
        events = mixin.event_logger.get_events(event_type=EventType.JOB_FAILED)
        self.assertEqual(len(events), 1)
        self.assertIn("OOM error", events[0].message)

    def test_log_partition_start(self):
        mixin = self._make_mixin()
        mixin.log_partition_start(0, {"partition_path": "/p0", "start_time": 1.0})
        events = mixin.event_logger.get_events(event_type=EventType.PARTITION_START)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].partition_id, 0)

    def test_log_partition_complete_success(self):
        mixin = self._make_mixin()
        mixin.log_partition_complete(1, duration=3.0, output_path="/out/p1")
        events = mixin.event_logger.get_events(event_type=EventType.PARTITION_COMPLETE)
        self.assertEqual(len(events), 1)
        self.assertIn("successfully", events[0].message)

    def test_log_partition_complete_failure(self):
        mixin = self._make_mixin()
        mixin.log_partition_complete(1, duration=2.0, output_path="/out",
                                     success=False, error="disk full")
        events = mixin.event_logger.get_events(event_type=EventType.PARTITION_COMPLETE)
        self.assertIn("failure", events[0].message)

    def test_log_partition_failed(self):
        mixin = self._make_mixin()
        mixin.log_partition_failed(2, "segfault", retry_count=3)
        events = mixin.event_logger.get_events(event_type=EventType.PARTITION_FAILED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].partition_id, 2)

    def test_log_op_start(self):
        mixin = self._make_mixin()
        mixin.log_op_start(0, "text_filter", 1, {"min_len": 10})
        events = mixin.event_logger.get_events(event_type=EventType.OP_START)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].operation_name, "text_filter")

    def test_log_op_complete(self):
        mixin = self._make_mixin()
        mixin.log_op_complete(0, "filter", 1, duration=2.5,
                              checkpoint_path="/cp", input_rows=100,
                              output_rows=80)
        events = mixin.event_logger.get_events(event_type=EventType.OP_COMPLETE)
        self.assertEqual(len(events), 1)
        self.assertIn("2.500s", events[0].message)

    def test_log_op_failed(self):
        mixin = self._make_mixin()
        mixin.log_op_failed(0, "mapper", 2, "ValueError", retry_count=1)
        events = mixin.event_logger.get_events(event_type=EventType.OP_FAILED)
        self.assertEqual(len(events), 1)

    def test_log_checkpoint_save(self):
        mixin = self._make_mixin()
        mixin.log_checkpoint_save(0, "filter", 1, "/tmp/cp.parquet")
        events = mixin.event_logger.get_events(event_type=EventType.CHECKPOINT_SAVE)
        self.assertEqual(len(events), 1)

    def test_log_checkpoint_load(self):
        mixin = self._make_mixin()
        mixin.log_checkpoint_load(0, "filter", 1, "/tmp/cp.parquet")
        events = mixin.event_logger.get_events(event_type=EventType.CHECKPOINT_LOAD)
        self.assertEqual(len(events), 1)

    def test_log_dag_build_start(self):
        mixin = self._make_mixin()
        mixin.log_dag_build_start({"node_count": 5, "depth": 3})
        events = mixin.event_logger.get_events(event_type=EventType.DAG_BUILD_START)
        self.assertEqual(len(events), 1)

    def test_log_dag_build_complete(self):
        mixin = self._make_mixin()
        mixin.log_dag_build_complete({
            "node_count": 10, "edge_count": 9,
            "parallel_groups_count": 2, "execution_plan_length": 10,
            "build_duration": 0.5,
        })
        events = mixin.event_logger.get_events(event_type=EventType.DAG_BUILD_COMPLETE)
        self.assertEqual(len(events), 1)
        self.assertIn("10 nodes", events[0].message)

    def test_setup_missing_job_id_raises(self):
        class FakeCfg:
            event_logging = {"enabled": True}
            job_id = None

        mixin = object.__new__(EventLoggingMixin)
        mixin.cfg = FakeCfg()
        mixin.work_dir = "/tmp"
        mixin.executor_type = "test"
        with self.assertRaises(ValueError):
            mixin._setup_event_logging()

    def test_get_config_name_from_config_file(self):
        mixin = self._make_mixin()
        mixin.cfg.config = "/path/to/my_recipe.yaml"
        name = mixin._get_config_name()
        self.assertEqual(name, "my_recipe")

    def test_get_config_name_from_project(self):
        mixin = self._make_mixin()
        mixin.cfg.config = None
        mixin.cfg.project_name = "data-clean"
        name = mixin._get_config_name()
        self.assertEqual(name, "data-clean")

    def test_get_config_name_fallback(self):
        mixin = self._make_mixin()
        mixin.cfg.config = None
        if hasattr(mixin.cfg, 'project_name'):
            delattr(mixin.cfg, 'project_name')
        name = mixin._get_config_name()
        self.assertEqual(name, "dj")

    def test_log_dag_node_ready(self):
        mixin = self._make_mixin()
        mixin.log_dag_node_ready("node_1", {"op_name": "filter", "op_type": "Filter"})
        events = mixin.event_logger.get_events(event_type=EventType.DAG_NODE_READY)
        self.assertEqual(len(events), 1)

    def test_log_dag_node_start(self):
        mixin = self._make_mixin()
        mixin.log_dag_node_start("node_1", {"op_name": "filter", "execution_order": 1})
        events = mixin.event_logger.get_events(event_type=EventType.DAG_NODE_START)
        self.assertEqual(len(events), 1)

    def test_log_dag_node_complete(self):
        mixin = self._make_mixin()
        mixin.log_dag_node_complete("node_1", {"op_name": "filter"}, duration=2.5)
        events = mixin.event_logger.get_events(event_type=EventType.DAG_NODE_COMPLETE)
        self.assertEqual(len(events), 1)
        self.assertIn("2.500s", events[0].message)

    def test_log_dag_node_failed(self):
        mixin = self._make_mixin()
        mixin.log_dag_node_failed("node_1", {"op_name": "mapper"}, "OOM", duration=1.0)
        events = mixin.event_logger.get_events(event_type=EventType.DAG_NODE_FAILED)
        self.assertEqual(len(events), 1)
        self.assertIn("OOM", events[0].message)

    def test_log_dag_parallel_group_start(self):
        mixin = self._make_mixin()
        mixin.log_dag_parallel_group_start("g1", {"node_count": 3, "node_ids": ["a", "b", "c"]})
        events = mixin.event_logger.get_events(event_type=EventType.DAG_PARALLEL_GROUP_START)
        self.assertEqual(len(events), 1)

    def test_log_dag_parallel_group_complete(self):
        mixin = self._make_mixin()
        mixin.log_dag_parallel_group_complete(
            "g1", {"node_count": 3, "completed_nodes": 3}, duration=5.0)
        events = mixin.event_logger.get_events(event_type=EventType.DAG_PARALLEL_GROUP_COMPLETE)
        self.assertEqual(len(events), 1)

    def test_log_dag_execution_plan_saved(self):
        mixin = self._make_mixin()
        mixin.log_dag_execution_plan_saved("/tmp/plan.json", {"node_count": 5})
        events = mixin.event_logger.get_events(event_type=EventType.DAG_EXECUTION_PLAN_SAVED)
        self.assertEqual(len(events), 1)

    def test_log_dag_execution_plan_loaded(self):
        mixin = self._make_mixin()
        mixin.log_dag_execution_plan_loaded("/tmp/plan.json", {"node_count": 5})
        events = mixin.event_logger.get_events(event_type=EventType.DAG_EXECUTION_PLAN_LOADED)
        self.assertEqual(len(events), 1)

    def test_log_job_restart(self):
        mixin = self._make_mixin()
        mixin.log_job_restart("crash", 1000.0, [0, 1], 3, ["/cp1", "/cp2"])
        events = mixin.event_logger.get_events(event_type=EventType.JOB_RESTART)
        self.assertEqual(len(events), 1)
        self.assertIn("crash", events[0].message)

    def test_log_partition_resume(self):
        mixin = self._make_mixin()
        mixin.log_partition_resume(0, 2, "/tmp/cp.parquet", "interrupted")
        events = mixin.event_logger.get_events(event_type=EventType.PARTITION_RESUME)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].partition_id, 0)

    def test_mixin_get_events(self):
        mixin = self._make_mixin()
        mixin._log_event(EventType.JOB_START, "test")
        events = mixin.get_events(event_type=EventType.JOB_START)
        self.assertEqual(len(events), 1)

    def test_mixin_get_events_disabled(self):
        mixin = self._make_disabled_mixin()
        events = mixin.get_events()
        self.assertEqual(events, [])

    def test_mixin_generate_status_report(self):
        mixin = self._make_mixin()
        mixin._log_event(EventType.JOB_START, "test")
        report = mixin.generate_status_report()
        self.assertIn("Total Events: 1", report)

    def test_mixin_generate_status_report_disabled(self):
        mixin = self._make_disabled_mixin()
        report = mixin.generate_status_report()
        self.assertEqual(report, "Event logging is disabled.")

    def test_update_job_summary(self):
        mixin = self._make_mixin()
        summary_file = os.path.join(mixin.work_dir, "job_summary.json")
        with open(summary_file, "w") as f:
            json.dump({"start_time": time.time(), "resumption_command": "dj run"}, f)
        mixin._update_job_summary("completed")
        with open(summary_file) as f:
            data = json.load(f)
        self.assertEqual(data["status"], "completed")

    def test_update_job_summary_failed(self):
        mixin = self._make_mixin()
        summary_file = os.path.join(mixin.work_dir, "job_summary.json")
        with open(summary_file, "w") as f:
            json.dump({"start_time": time.time(), "resumption_command": "dj run"}, f)
        mixin._update_job_summary("failed", error_message="disk full")
        with open(summary_file) as f:
            data = json.load(f)
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["error_message"], "disk full")

    def test_update_job_summary_no_file(self):
        mixin = self._make_mixin()
        mixin._update_job_summary("completed")  # should not raise

    def test_load_job_summary(self):
        mixin = self._make_mixin()
        summary_file = os.path.join(mixin.work_dir, "job_summary.json")
        with open(summary_file, "w") as f:
            json.dump({"job_id": "test", "status": "running"}, f)
        result = mixin._load_job_summary()
        self.assertEqual(result["job_id"], "test")

    def test_load_job_summary_no_file(self):
        mixin = self._make_mixin()
        result = mixin._load_job_summary()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
