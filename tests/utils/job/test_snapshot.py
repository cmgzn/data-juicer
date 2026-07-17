import json
import os
import tempfile
import time
import unittest

from data_juicer.utils.job.snapshot import (
    JobSnapshot,
    OperationStatus,
    PartitionStatus,
    ProcessingSnapshotAnalyzer,
    ProcessingStatus,
    create_snapshot,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class ProcessingStatusTest(DataJuicerTestCaseBase):

    def test_enum_values(self):
        self.assertEqual(ProcessingStatus.NOT_STARTED.value, 'not_started')
        self.assertEqual(ProcessingStatus.IN_PROGRESS.value, 'in_progress')
        self.assertEqual(ProcessingStatus.COMPLETED.value, 'completed')
        self.assertEqual(ProcessingStatus.FAILED.value, 'failed')
        self.assertEqual(ProcessingStatus.CHECKPOINTED.value, 'checkpointed')

    def test_enum_from_value(self):
        self.assertEqual(ProcessingStatus('completed'),
                         ProcessingStatus.COMPLETED)


class OperationStatusTest(DataJuicerTestCaseBase):

    def test_defaults(self):
        op = OperationStatus(
            operation_name='filter_op',
            operation_idx=0,
            status=ProcessingStatus.NOT_STARTED,
        )
        self.assertIsNone(op.start_time)
        self.assertIsNone(op.end_time)
        self.assertIsNone(op.duration)
        self.assertIsNone(op.input_rows)
        self.assertIsNone(op.output_rows)
        self.assertIsNone(op.checkpoint_time)
        self.assertIsNone(op.error_message)

    def test_with_values(self):
        op = OperationStatus(
            operation_name='mapper_op',
            operation_idx=1,
            status=ProcessingStatus.COMPLETED,
            start_time=100.0,
            end_time=200.0,
            duration=100.0,
            input_rows=1000,
            output_rows=950,
        )
        self.assertEqual(op.operation_name, 'mapper_op')
        self.assertEqual(op.duration, 100.0)
        self.assertEqual(op.output_rows, 950)


class PartitionStatusTest(DataJuicerTestCaseBase):

    def test_mutable_defaults_initialized(self):
        p = PartitionStatus(
            partition_id=0,
            status=ProcessingStatus.NOT_STARTED,
        )
        self.assertIsInstance(p.completed_operations, list)
        self.assertIsInstance(p.failed_operations, list)
        self.assertIsInstance(p.checkpointed_operations, list)
        self.assertEqual(len(p.completed_operations), 0)

    def test_mutable_defaults_independent(self):
        p1 = PartitionStatus(partition_id=0,
                             status=ProcessingStatus.NOT_STARTED)
        p2 = PartitionStatus(partition_id=1,
                             status=ProcessingStatus.NOT_STARTED)
        p1.completed_operations.append('op_a')
        self.assertEqual(len(p2.completed_operations), 0)


class JobSnapshotTest(DataJuicerTestCaseBase):

    def test_defaults(self):
        snap = JobSnapshot(job_id='test_job')
        self.assertEqual(snap.job_id, 'test_job')
        self.assertEqual(snap.total_partitions, 0)
        self.assertEqual(snap.overall_status,
                         ProcessingStatus.NOT_STARTED)
        self.assertFalse(snap.resumable)


class AnalyzerAnalyzeEventsTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def _make_analyzer(self):
        return ProcessingSnapshotAnalyzer(self.work_dir)

    def test_empty_events(self):
        analyzer = self._make_analyzer()
        partitions, operations = analyzer.analyze_events([])
        self.assertEqual(len(partitions), 0)
        self.assertEqual(len(operations), 0)

    def test_partition_lifecycle(self):
        events = [
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'partition_creation_complete',
             'partition_id': 0, 'timestamp': 1001.0,
             'metadata': {'sample_count': 500}},
            {'event_type': 'partition_start',
             'partition_id': 0, 'timestamp': 1002.0},
            {'event_type': 'partition_complete',
             'partition_id': 0, 'timestamp': 1010.0},
        ]
        analyzer = self._make_analyzer()
        partitions, _ = analyzer.analyze_events(events)

        self.assertIn(0, partitions)
        p = partitions[0]
        self.assertEqual(p.status, ProcessingStatus.COMPLETED)
        self.assertEqual(p.sample_count, 500)
        self.assertEqual(p.creation_start_time, 1000.0)
        self.assertEqual(p.processing_end_time, 1010.0)

    def test_partition_failed(self):
        events = [
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'partition_start',
             'partition_id': 0, 'timestamp': 1002.0},
            {'event_type': 'partition_failed',
             'partition_id': 0, 'timestamp': 1005.0,
             'error_message': 'OOM'},
        ]
        analyzer = self._make_analyzer()
        partitions, _ = analyzer.analyze_events(events)
        self.assertEqual(partitions[0].status, ProcessingStatus.FAILED)
        self.assertEqual(partitions[0].error_message, 'OOM')

    def test_operation_lifecycle(self):
        events = [
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'op_start', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'filter_a',
             'timestamp': 1001.0},
            {'event_type': 'op_complete', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'filter_a',
             'timestamp': 1005.0,
             'metadata': {'input_rows': 100, 'output_rows': 80}},
        ]
        analyzer = self._make_analyzer()
        partitions, operations = analyzer.analyze_events(events)

        key = 'p0_op0_filter_a'
        self.assertIn(key, operations)
        op = operations[key]
        self.assertEqual(op.status, ProcessingStatus.COMPLETED)
        self.assertAlmostEqual(op.duration, 4.0)
        self.assertEqual(op.input_rows, 100)
        self.assertEqual(op.output_rows, 80)
        self.assertIn('filter_a', partitions[0].completed_operations)

    def test_operation_failed(self):
        events = [
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'op_start', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'bad_op',
             'timestamp': 1001.0},
            {'event_type': 'op_failed', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'bad_op',
             'timestamp': 1002.0,
             'error_message': 'division by zero'},
        ]
        analyzer = self._make_analyzer()
        partitions, operations = analyzer.analyze_events(events)
        self.assertEqual(operations['p0_op0_bad_op'].status,
                         ProcessingStatus.FAILED)
        self.assertIn('bad_op', partitions[0].failed_operations)

    def test_checkpoint_save(self):
        events = [
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'op_start', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'mapper_a',
             'timestamp': 1001.0},
            {'event_type': 'checkpoint_save', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'mapper_a',
             'timestamp': 1003.0},
        ]
        analyzer = self._make_analyzer()
        partitions, operations = analyzer.analyze_events(events)
        op = operations['p0_op0_mapper_a']
        self.assertEqual(op.status, ProcessingStatus.CHECKPOINTED)
        self.assertEqual(op.checkpoint_time, 1003.0)
        self.assertIn('mapper_a',
                       partitions[0].checkpointed_operations)

    def test_multiple_partitions(self):
        events = [
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'partition_creation_start',
             'partition_id': 1, 'timestamp': 1000.0},
            {'event_type': 'partition_start',
             'partition_id': 0, 'timestamp': 1001.0},
            {'event_type': 'partition_complete',
             'partition_id': 0, 'timestamp': 1005.0},
            {'event_type': 'partition_start',
             'partition_id': 1, 'timestamp': 1002.0},
        ]
        analyzer = self._make_analyzer()
        partitions, _ = analyzer.analyze_events(events)
        self.assertEqual(len(partitions), 2)
        self.assertEqual(partitions[0].status,
                         ProcessingStatus.COMPLETED)
        self.assertEqual(partitions[1].status,
                         ProcessingStatus.IN_PROGRESS)

    def test_current_operation_tracked(self):
        events = [
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'op_start', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'running_op',
             'timestamp': 1001.0},
        ]
        analyzer = self._make_analyzer()
        partitions, _ = analyzer.analyze_events(events)
        self.assertEqual(partitions[0].current_operation, 'running_op')


class AnalyzerDetermineOverallStatusTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()
        self.analyzer = ProcessingSnapshotAnalyzer(self.work_dir)

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def _make_partitions(self, statuses):
        return {
            i: PartitionStatus(partition_id=i, status=s)
            for i, s in enumerate(statuses)
        }

    def test_empty(self):
        self.assertEqual(
            self.analyzer.determine_overall_status({}, {}),
            ProcessingStatus.NOT_STARTED)

    def test_all_completed(self):
        ps = self._make_partitions([
            ProcessingStatus.COMPLETED,
            ProcessingStatus.COMPLETED,
        ])
        self.assertEqual(
            self.analyzer.determine_overall_status(ps, {}),
            ProcessingStatus.COMPLETED)

    def test_all_failed(self):
        ps = self._make_partitions([ProcessingStatus.FAILED])
        self.assertEqual(
            self.analyzer.determine_overall_status(ps, {}),
            ProcessingStatus.FAILED)

    def test_mixed_in_progress(self):
        ps = self._make_partitions([
            ProcessingStatus.COMPLETED,
            ProcessingStatus.IN_PROGRESS,
        ])
        self.assertEqual(
            self.analyzer.determine_overall_status(ps, {}),
            ProcessingStatus.IN_PROGRESS)

    def test_failed_with_completed(self):
        ps = self._make_partitions([
            ProcessingStatus.FAILED,
            ProcessingStatus.COMPLETED,
        ])
        self.assertEqual(
            self.analyzer.determine_overall_status(ps, {}),
            ProcessingStatus.IN_PROGRESS)

    def test_all_not_started(self):
        ps = self._make_partitions([ProcessingStatus.NOT_STARTED])
        self.assertEqual(
            self.analyzer.determine_overall_status(ps, {}),
            ProcessingStatus.NOT_STARTED)


class AnalyzerCalculateStatisticsTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()
        self.analyzer = ProcessingSnapshotAnalyzer(self.work_dir)

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_mixed_stats(self):
        partitions = {
            0: PartitionStatus(0, ProcessingStatus.COMPLETED),
            1: PartitionStatus(1, ProcessingStatus.FAILED),
            2: PartitionStatus(2, ProcessingStatus.IN_PROGRESS),
        }
        operations = {
            'a': OperationStatus('op_a', 0, ProcessingStatus.COMPLETED),
            'b': OperationStatus('op_b', 1, ProcessingStatus.FAILED),
            'c': OperationStatus('op_c', 2, ProcessingStatus.CHECKPOINTED),
            'd': OperationStatus('op_d', 3, ProcessingStatus.IN_PROGRESS),
        }
        stats = self.analyzer.calculate_statistics(partitions, operations)
        self.assertEqual(stats['total_partitions'], 3)
        self.assertEqual(stats['completed_partitions'], 1)
        self.assertEqual(stats['failed_partitions'], 1)
        self.assertEqual(stats['in_progress_partitions'], 1)
        self.assertEqual(stats['total_operations'], 4)
        self.assertEqual(stats['completed_operations'], 1)
        self.assertEqual(stats['failed_operations'], 1)
        self.assertEqual(stats['checkpointed_operations'], 1)


class AnalyzerFormatDurationTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()
        self.analyzer = ProcessingSnapshotAnalyzer(self.work_dir)

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_seconds_only(self):
        self.assertEqual(self.analyzer._format_duration(42), '42s')

    def test_minutes_and_seconds(self):
        self.assertEqual(self.analyzer._format_duration(125), '2m 5s')

    def test_hours_minutes_seconds(self):
        self.assertEqual(self.analyzer._format_duration(3661), '1h 1m 1s')

    def test_zero(self):
        self.assertEqual(self.analyzer._format_duration(0), '0s')

    def test_none(self):
        self.assertIsNone(self.analyzer._format_duration(None))


class AnalyzerProgressCalculationTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()
        self.analyzer = ProcessingSnapshotAnalyzer(self.work_dir)

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_partition_progress_completed(self):
        p = PartitionStatus(0, ProcessingStatus.COMPLETED)
        self.assertAlmostEqual(
            self.analyzer._calculate_partition_progress(p), 100.0)

    def test_partition_progress_failed(self):
        p = PartitionStatus(0, ProcessingStatus.FAILED)
        self.assertAlmostEqual(
            self.analyzer._calculate_partition_progress(p), 0.0)

    def test_partition_progress_in_progress_no_ops(self):
        p = PartitionStatus(0, ProcessingStatus.IN_PROGRESS)
        self.assertAlmostEqual(
            self.analyzer._calculate_partition_progress(p), 10.0)

    def test_partition_progress_in_progress_with_ops(self):
        p = PartitionStatus(0, ProcessingStatus.IN_PROGRESS)
        p.completed_operations = ['a', 'b', 'c']
        progress = self.analyzer._calculate_partition_progress(p)
        self.assertGreater(progress, 10.0)
        self.assertLessEqual(progress, 90.0)

    def test_partition_progress_not_started(self):
        p = PartitionStatus(0, ProcessingStatus.NOT_STARTED)
        self.assertAlmostEqual(
            self.analyzer._calculate_partition_progress(p), 0.0)

    def test_operation_progress_completed(self):
        op = OperationStatus('op', 0, ProcessingStatus.COMPLETED)
        self.assertAlmostEqual(
            self.analyzer._calculate_operation_progress(op), 100.0)

    def test_operation_progress_checkpointed(self):
        op = OperationStatus('op', 0, ProcessingStatus.CHECKPOINTED)
        self.assertAlmostEqual(
            self.analyzer._calculate_operation_progress(op), 100.0)

    def test_operation_progress_failed(self):
        op = OperationStatus('op', 0, ProcessingStatus.FAILED)
        self.assertAlmostEqual(
            self.analyzer._calculate_operation_progress(op), 0.0)

    def test_operation_progress_not_started(self):
        op = OperationStatus('op', 0, ProcessingStatus.NOT_STARTED)
        self.assertAlmostEqual(
            self.analyzer._calculate_operation_progress(op), 0.0)

    def test_overall_progress(self):
        snap = JobSnapshot(
            job_id='test',
            total_partitions=4,
            completed_partitions=2,
            total_operations=8,
            completed_operations=4,
        )
        result = self.analyzer._calculate_overall_progress(snap)
        self.assertAlmostEqual(result['partition_percentage'], 50.0)
        self.assertAlmostEqual(result['operation_percentage'], 50.0)
        self.assertAlmostEqual(result['overall_percentage'], 50.0)

    def test_partition_progress_percentage_zero_partitions(self):
        snap = JobSnapshot(job_id='test', total_partitions=0)
        self.assertAlmostEqual(
            self.analyzer._calculate_partition_progress_percentage(snap),
            100.0)

    def test_operation_progress_percentage_zero_ops(self):
        snap = JobSnapshot(job_id='test', total_operations=0)
        self.assertAlmostEqual(
            self.analyzer._calculate_operation_progress_percentage(snap),
            100.0)

    def test_checkpoint_progress(self):
        snap = JobSnapshot(
            job_id='test',
            total_operations=4,
            checkpointed_operations=2,
            operation_statuses={
                'a': OperationStatus('op_a', 0,
                                     ProcessingStatus.CHECKPOINTED,
                                     checkpoint_time=1000.0),
                'b': OperationStatus('op_b', 1,
                                     ProcessingStatus.COMPLETED),
            },
        )
        result = self.analyzer._calculate_checkpoint_progress(snap)
        self.assertAlmostEqual(result['percentage'], 50.0)
        self.assertEqual(len(result['checkpointed_operations']), 1)

    def test_checkpoint_progress_zero_ops(self):
        snap = JobSnapshot(
            job_id='test',
            total_operations=0,
            operation_statuses={},
        )
        result = self.analyzer._calculate_checkpoint_progress(snap)
        self.assertAlmostEqual(result['percentage'], 0.0)


class AnalyzerFileIOTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_load_events_valid(self):
        events_file = os.path.join(self.work_dir, 'events.jsonl')
        with open(events_file, 'w') as f:
            f.write(json.dumps({'event_type': 'job_start',
                                'timestamp': 1000.0}) + '\n')
            f.write(json.dumps({'event_type': 'job_complete',
                                'timestamp': 2000.0}) + '\n')
        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        events = analyzer.load_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['event_type'], 'job_start')

    def test_load_events_missing(self):
        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        events = analyzer.load_events()
        self.assertEqual(len(events), 0)

    def test_load_events_latest_file(self):
        old_file = os.path.join(self.work_dir, 'events_001.jsonl')
        with open(old_file, 'w') as f:
            f.write(json.dumps({'event_type': 'old'}) + '\n')

        time.sleep(0.05)
        new_file = os.path.join(self.work_dir, 'events_002.jsonl')
        with open(new_file, 'w') as f:
            f.write(json.dumps({'event_type': 'new'}) + '\n')

        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        events = analyzer.load_events()
        self.assertEqual(events[0]['event_type'], 'new')

    def test_load_dag_plan_valid(self):
        dag_file = os.path.join(self.work_dir, 'dag_execution_plan.json')
        plan = {'nodes': ['a', 'b'], 'edges': []}
        with open(dag_file, 'w') as f:
            json.dump(plan, f)
        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        loaded = analyzer.load_dag_plan()
        self.assertEqual(loaded['nodes'], ['a', 'b'])

    def test_load_dag_plan_missing(self):
        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        self.assertEqual(analyzer.load_dag_plan(), {})

    def test_load_job_summary_valid(self):
        summary_file = os.path.join(self.work_dir, 'job_summary.json')
        summary = {'status': 'completed', 'start_time': 1000.0}
        with open(summary_file, 'w') as f:
            json.dump(summary, f)
        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        loaded = analyzer.load_job_summary()
        self.assertEqual(loaded['status'], 'completed')

    def test_load_job_summary_missing(self):
        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        self.assertEqual(analyzer.load_job_summary(), {})


class GenerateSnapshotIntegrationTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def _write_events(self, events):
        path = os.path.join(self.work_dir, 'events.jsonl')
        with open(path, 'w') as f:
            for e in events:
                f.write(json.dumps(e) + '\n')

    def _write_summary(self, summary):
        path = os.path.join(self.work_dir, 'job_summary.json')
        with open(path, 'w') as f:
            json.dump(summary, f)

    def test_generate_snapshot_completed_job(self):
        self._write_events([
            {'event_type': 'job_start', 'timestamp': 1000.0,
             'metadata': {'checkpoint_strategy': 'per_op'}},
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1001.0},
            {'event_type': 'partition_creation_complete',
             'partition_id': 0, 'timestamp': 1002.0,
             'metadata': {'sample_count': 100}},
            {'event_type': 'partition_start',
             'partition_id': 0, 'timestamp': 1003.0},
            {'event_type': 'op_start', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'filter_x',
             'timestamp': 1004.0},
            {'event_type': 'op_complete', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'filter_x',
             'timestamp': 1006.0,
             'metadata': {'input_rows': 100, 'output_rows': 90}},
            {'event_type': 'partition_complete',
             'partition_id': 0, 'timestamp': 1007.0},
            {'event_type': 'job_complete', 'timestamp': 1008.0},
        ])
        self._write_summary({
            'status': 'completed',
            'start_time': 1000.0,
            'end_time': 1008.0,
            'duration': 8.0,
        })

        snapshot = create_snapshot(self.work_dir)

        self.assertEqual(snapshot.overall_status,
                         ProcessingStatus.COMPLETED)
        self.assertEqual(snapshot.total_partitions, 1)
        self.assertEqual(snapshot.completed_partitions, 1)
        self.assertEqual(snapshot.completed_operations, 1)
        self.assertEqual(snapshot.job_start_time, 1000.0)
        self.assertEqual(snapshot.total_duration, 8.0)
        self.assertEqual(snapshot.checkpoint_strategy, 'per_op')

    def test_generate_snapshot_with_checkpoint(self):
        self._write_events([
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'op_start', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'slow_op',
             'timestamp': 1001.0},
            {'event_type': 'checkpoint_save', 'partition_id': 0,
             'operation_idx': 0, 'operation_name': 'slow_op',
             'timestamp': 1005.0},
        ])

        snapshot = create_snapshot(self.work_dir)

        self.assertTrue(snapshot.resumable)
        self.assertEqual(snapshot.last_checkpoint_time, 1005.0)
        self.assertEqual(snapshot.checkpointed_operations, 1)

    def test_to_json_dict(self):
        self._write_events([
            {'event_type': 'partition_creation_start',
             'partition_id': 0, 'timestamp': 1000.0},
            {'event_type': 'partition_start',
             'partition_id': 0, 'timestamp': 1001.0},
            {'event_type': 'partition_complete',
             'partition_id': 0, 'timestamp': 1005.0},
        ])
        self._write_summary({
            'status': 'completed',
            'start_time': 1000.0,
            'end_time': 1005.0,
            'duration': 5.0,
        })

        analyzer = ProcessingSnapshotAnalyzer(self.work_dir)
        snapshot = analyzer.generate_snapshot()
        json_dict = analyzer.to_json_dict(snapshot)

        self.assertIn('job_info', json_dict)
        self.assertIn('overall_status', json_dict)
        self.assertIn('progress_summary', json_dict)
        self.assertIn('partition_progress', json_dict)
        self.assertIn('timing', json_dict)
        self.assertEqual(json_dict['timing']['duration_formatted'], '5s')
        self.assertEqual(
            json_dict['progress_summary']['completed_partitions'], 1)

    def test_generate_snapshot_timing_from_events_fallback(self):
        self._write_events([
            {'event_type': 'job_start', 'timestamp': 100.0},
            {'event_type': 'job_complete', 'timestamp': 200.0},
        ])
        snapshot = create_snapshot(self.work_dir)
        self.assertEqual(snapshot.job_start_time, 100.0)
        self.assertEqual(snapshot.job_end_time, 200.0)
        self.assertAlmostEqual(snapshot.total_duration, 100.0)


if __name__ == '__main__':
    unittest.main()
