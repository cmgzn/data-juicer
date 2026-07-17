import json
import os
import tempfile
import time
import unittest

from data_juicer.utils.job.common import JobUtils, list_running_jobs
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class JobUtilsInitTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_init_with_work_dir(self):
        ju = JobUtils('test_job', work_dir=self.work_dir)
        self.assertEqual(str(ju.work_dir), self.work_dir)
        self.assertEqual(ju.job_id, 'test_job')

    def test_init_with_base_dir(self):
        job_dir = os.path.join(self.work_dir, 'my_job')
        os.makedirs(job_dir)
        ju = JobUtils('my_job', base_dir=self.work_dir)
        self.assertEqual(str(ju.work_dir), job_dir)

    def test_init_missing_dir_raises(self):
        with self.assertRaises(FileNotFoundError):
            JobUtils('nonexistent', work_dir='/tmp/no_such_dir_99999')


class JobUtilsLoadJobSummaryTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_valid_summary(self):
        summary = {'status': 'completed', 'start_time': 1000.0}
        with open(os.path.join(self.work_dir, 'job_summary.json'), 'w') as f:
            json.dump(summary, f)
        ju = JobUtils('test', work_dir=self.work_dir)
        loaded = ju.load_job_summary()
        self.assertEqual(loaded['status'], 'completed')

    def test_missing_summary(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        self.assertIsNone(ju.load_job_summary())

    def test_malformed_summary(self):
        with open(os.path.join(self.work_dir, 'job_summary.json'), 'w') as f:
            f.write('{invalid json}')
        ju = JobUtils('test', work_dir=self.work_dir)
        self.assertIsNone(ju.load_job_summary())


class JobUtilsLoadDatasetMappingTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_valid_mapping(self):
        meta_dir = os.path.join(self.work_dir, 'metadata')
        os.makedirs(meta_dir)
        mapping = {'partitions': [{'partition_id': 0, 'sample_count': 100}]}
        with open(os.path.join(meta_dir, 'dataset_mapping.json'), 'w') as f:
            json.dump(mapping, f)
        ju = JobUtils('test', work_dir=self.work_dir)
        loaded = ju.load_dataset_mapping()
        self.assertEqual(len(loaded['partitions']), 1)

    def test_missing_mapping(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        self.assertEqual(ju.load_dataset_mapping(), {})


class JobUtilsFindEventsFileTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_fallback_to_events_jsonl(self):
        events_file = os.path.join(self.work_dir, 'events.jsonl')
        with open(events_file, 'w') as f:
            f.write('{"event_type": "test"}\n')
        ju = JobUtils('test', work_dir=self.work_dir)
        found = ju._find_latest_events_file()
        self.assertEqual(str(found), events_file)

    def test_picks_latest_timestamped(self):
        old = os.path.join(self.work_dir, 'events_001.jsonl')
        with open(old, 'w') as f:
            f.write('{"event_type": "old"}\n')
        time.sleep(0.05)
        new = os.path.join(self.work_dir, 'events_002.jsonl')
        with open(new, 'w') as f:
            f.write('{"event_type": "new"}\n')

        ju = JobUtils('test', work_dir=self.work_dir)
        found = ju._find_latest_events_file()
        self.assertEqual(str(found), new)

    def test_no_events_returns_none(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        self.assertIsNone(ju._find_latest_events_file())


class JobUtilsLoadEventLogsTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_valid_events(self):
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            f.write(json.dumps({'event_type': 'a', 'timestamp': 1.0}) + '\n')
            f.write(json.dumps({'event_type': 'b', 'timestamp': 2.0}) + '\n')
        ju = JobUtils('test', work_dir=self.work_dir)
        events = ju.load_event_logs()
        self.assertEqual(len(events), 2)

    def test_malformed_lines_skipped(self):
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            f.write(json.dumps({'event_type': 'good'}) + '\n')
            f.write('not valid json\n')
            f.write(json.dumps({'event_type': 'also_good'}) + '\n')
        ju = JobUtils('test', work_dir=self.work_dir)
        events = ju.load_event_logs()
        self.assertEqual(len(events), 2)

    def test_empty_file(self):
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            pass
        ju = JobUtils('test', work_dir=self.work_dir)
        events = ju.load_event_logs()
        self.assertEqual(len(events), 0)

    def test_no_events_file(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        events = ju.load_event_logs()
        self.assertEqual(len(events), 0)


class JobUtilsExtractProcessThreadIdsTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_extracts_ids(self):
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            f.write(json.dumps({
                'event_type': 'op_start',
                'process_id': 1234,
                'thread_id': 5678,
            }) + '\n')
            f.write(json.dumps({
                'event_type': 'op_start',
                'process_id': 1234,
                'thread_id': 9999,
            }) + '\n')
        ju = JobUtils('test', work_dir=self.work_dir)
        ids = ju.extract_process_thread_ids()
        self.assertEqual(ids['process_ids'], {1234})
        self.assertEqual(ids['thread_ids'], {5678, 9999})

    def test_skips_none_ids(self):
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            f.write(json.dumps({
                'event_type': 'x',
                'process_id': None,
                'thread_id': None,
            }) + '\n')
        ju = JobUtils('test', work_dir=self.work_dir)
        ids = ju.extract_process_thread_ids()
        self.assertEqual(len(ids['process_ids']), 0)

    def test_events_without_ids(self):
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            f.write(json.dumps({'event_type': 'job_start'}) + '\n')
        ju = JobUtils('test', work_dir=self.work_dir)
        ids = ju.extract_process_thread_ids()
        self.assertEqual(len(ids['process_ids']), 0)
        self.assertEqual(len(ids['thread_ids']), 0)


class JobUtilsFindProcessesTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_finds_current_process(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        current_pid = os.getpid()
        procs = ju.find_processes_by_ids({current_pid})
        self.assertEqual(len(procs), 0)

    def test_nonexistent_pid(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        procs = ju.find_processes_by_ids({99999999})
        self.assertEqual(len(procs), 0)

    def test_find_threads_placeholder(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        threads = ju.find_threads_by_ids({1, 2, 3})
        self.assertEqual(len(threads), 0)


class JobUtilsGetPartitionStatusTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def _setup_job(self, mapping=None, events=None):
        if mapping:
            meta_dir = os.path.join(self.work_dir, 'metadata')
            os.makedirs(meta_dir, exist_ok=True)
            with open(os.path.join(meta_dir, 'dataset_mapping.json'),
                      'w') as f:
                json.dump(mapping, f)
        if events:
            with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
                for e in events:
                    f.write(json.dumps(e) + '\n')

    def test_from_mapping_and_events(self):
        self._setup_job(
            mapping={
                'partitions': [
                    {'partition_id': 0, 'sample_count': 50,
                     'processing_status': 'pending'},
                ],
            },
            events=[
                {'event_type': 'partition_start', 'partition_id': 0,
                 'timestamp': 1000.0},
                {'event_type': 'op_start', 'partition_id': 0,
                 'operation_name': 'filter_x', 'operation_idx': 0,
                 'timestamp': 1001.0},
                {'event_type': 'op_complete', 'partition_id': 0,
                 'operation_name': 'filter_x', 'operation_idx': 0,
                 'timestamp': 1003.0, 'duration': 2.0,
                 'input_rows': 50, 'output_rows': 40,
                 'performance_metrics': {
                     'throughput': 25.0, 'reduction_ratio': 0.2}},
                {'event_type': 'partition_complete', 'partition_id': 0,
                 'timestamp': 1005.0},
            ],
        )
        ju = JobUtils('test', work_dir=self.work_dir)
        status = ju.get_partition_status()
        self.assertIn(0, status)
        self.assertEqual(status[0]['status'], 'completed')
        self.assertEqual(len(status[0]['completed_ops']), 1)
        self.assertIsNone(status[0]['current_op'])

    def test_checkpoint_tracked(self):
        self._setup_job(events=[
            {'event_type': 'partition_start', 'partition_id': 0,
             'timestamp': 1000.0},
            {'event_type': 'checkpoint_save', 'partition_id': 0,
             'operation_name': 'op_a', 'operation_idx': 0,
             'checkpoint_path': '/tmp/ckpt', 'timestamp': 1002.0},
        ])
        ju = JobUtils('test', work_dir=self.work_dir)
        status = ju.get_partition_status()
        self.assertEqual(len(status[0]['checkpoints']), 1)
        self.assertEqual(status[0]['checkpoints'][0]['checkpoint_path'],
                         '/tmp/ckpt')


class JobUtilsCalculateOverallProgressTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_complete_job(self):
        meta_dir = os.path.join(self.work_dir, 'metadata')
        os.makedirs(meta_dir)
        with open(os.path.join(meta_dir, 'dataset_mapping.json'), 'w') as f:
            json.dump({'partitions': [
                {'partition_id': 0, 'sample_count': 100,
                 'processing_status': 'completed'},
                {'partition_id': 1, 'sample_count': 100,
                 'processing_status': 'completed'},
            ]}, f)
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            for pid in [0, 1]:
                f.write(json.dumps({
                    'event_type': 'partition_complete',
                    'partition_id': pid, 'timestamp': 1000.0,
                }) + '\n')
        with open(os.path.join(self.work_dir, 'job_summary.json'), 'w') as f:
            json.dump({'status': 'completed', 'start_time': 900.0}, f)

        ju = JobUtils('test', work_dir=self.work_dir)
        progress = ju.calculate_overall_progress()
        self.assertAlmostEqual(progress['progress_percentage'], 100.0)
        self.assertEqual(progress['completed_partitions'], 2)
        self.assertEqual(progress['total_samples'], 200)

    def test_empty_job(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        progress = ju.calculate_overall_progress()
        self.assertEqual(progress['total_partitions'], 0)
        self.assertAlmostEqual(progress['progress_percentage'], 0)


class JobUtilsGetOperationPipelineTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_valid_config(self):
        config = (
            'project_name: test\n'
            'process:\n'
            '  - language_id_score_filter:\n'
            '      lang: en\n'
            '  - text_length_filter:\n'
            '      min_len: 10\n'
        )
        with open(os.path.join(self.work_dir,
                               'partition-checkpoint-eventlog.yaml'),
                  'w') as f:
            f.write(config)
        ju = JobUtils('test', work_dir=self.work_dir)
        ops = ju.get_operation_pipeline()
        self.assertEqual(len(ops), 2)
        self.assertEqual(ops[0]['name'], 'language_id_score_filter')

    def test_missing_config(self):
        ju = JobUtils('test', work_dir=self.work_dir)
        ops = ju.get_operation_pipeline()
        self.assertEqual(ops, [])


class ListRunningJobsTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.base_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.base_dir}')
        super().tearDown()

    def test_lists_jobs(self):
        job1_dir = os.path.join(self.base_dir, 'job_001')
        os.makedirs(job1_dir)
        with open(os.path.join(job1_dir, 'job_summary.json'), 'w') as f:
            json.dump({'status': 'completed', 'start_time': 1000.0}, f)

        job2_dir = os.path.join(self.base_dir, 'job_002')
        os.makedirs(job2_dir)
        with open(os.path.join(job2_dir, 'job_summary.json'), 'w') as f:
            json.dump({'status': 'running', 'start_time': 2000.0}, f)

        jobs = list_running_jobs(self.base_dir)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]['job_id'], 'job_002')
        self.assertEqual(jobs[1]['job_id'], 'job_001')

    def test_empty_base_dir(self):
        jobs = list_running_jobs(self.base_dir)
        self.assertEqual(len(jobs), 0)

    def test_nonexistent_base_dir(self):
        jobs = list_running_jobs('/tmp/no_such_dir_99999')
        self.assertEqual(len(jobs), 0)

    def test_dirs_without_summary_skipped(self):
        os.makedirs(os.path.join(self.base_dir, 'no_summary_job'))
        jobs = list_running_jobs(self.base_dir)
        self.assertEqual(len(jobs), 0)


if __name__ == '__main__':
    unittest.main()
