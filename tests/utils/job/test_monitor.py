import json
import os
import sys
import tempfile
import unittest
from io import StringIO

from data_juicer.utils.job.monitor import JobProgressMonitor, show_job_progress
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class JobProgressMonitorTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()
        self._setup_fixtures()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def _setup_fixtures(self):
        with open(os.path.join(self.work_dir, 'job_summary.json'), 'w') as f:
            json.dump({
                'status': 'completed',
                'start_time': 1000.0,
                'end_time': 1010.0,
                'duration': 10.0,
            }, f)

        meta_dir = os.path.join(self.work_dir, 'metadata')
        os.makedirs(meta_dir)
        with open(os.path.join(meta_dir, 'dataset_mapping.json'), 'w') as f:
            json.dump({
                'original_dataset_path': '/data/test.jsonl',
                'original_dataset_size': 1000,
                'partition_size': 500,
                'partitions': [
                    {'partition_id': 0, 'sample_count': 500,
                     'processing_status': 'completed'},
                    {'partition_id': 1, 'sample_count': 500,
                     'processing_status': 'completed'},
                ],
            }, f)

        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            for pid in [0, 1]:
                f.write(json.dumps({
                    'event_type': 'partition_start',
                    'partition_id': pid, 'timestamp': 1001.0,
                }) + '\n')
                f.write(json.dumps({
                    'event_type': 'op_start',
                    'partition_id': pid, 'operation_name': 'filter_x',
                    'operation_idx': 0, 'timestamp': 1002.0,
                }) + '\n')
                f.write(json.dumps({
                    'event_type': 'op_complete',
                    'partition_id': pid, 'operation_name': 'filter_x',
                    'operation_idx': 0, 'timestamp': 1004.0,
                    'duration': 2.0, 'input_rows': 500, 'output_rows': 400,
                    'performance_metrics': {
                        'throughput': 250.0, 'reduction_ratio': 0.2},
                }) + '\n')
                f.write(json.dumps({
                    'event_type': 'partition_complete',
                    'partition_id': pid, 'timestamp': 1005.0,
                }) + '\n')

    def test_get_progress_data(self):
        monitor = JobProgressMonitor(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        data = monitor.get_progress_data()
        self.assertEqual(data['job_id'], os.path.basename(self.work_dir))
        self.assertIn('job_summary', data)
        self.assertIn('overall_progress', data)
        self.assertAlmostEqual(
            data['overall_progress']['progress_percentage'], 100.0)

    def test_display_progress(self):
        monitor = JobProgressMonitor(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            monitor.display_progress()
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn('JOB OVERVIEW', output)
        self.assertIn('OVERALL PROGRESS', output)
        self.assertIn('PARTITION STATUS', output)

    def test_display_progress_detailed(self):
        monitor = JobProgressMonitor(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            monitor.display_progress(detailed=True)
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn('OPERATION DETAILS', output)
        self.assertIn('filter_x', output)

    def test_show_job_progress_convenience(self):
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            data = show_job_progress(
                os.path.basename(self.work_dir),
                base_dir=os.path.dirname(self.work_dir),
            )
        finally:
            sys.stdout = old_stdout
        self.assertIn('overall_progress', data)


class JobProgressMonitorEmptyTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_display_progress_no_data(self):
        monitor = JobProgressMonitor(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            monitor.display_progress()
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn('JOB OVERVIEW', output)


if __name__ == '__main__':
    unittest.main()
