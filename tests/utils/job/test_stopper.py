import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

import psutil

from data_juicer.utils.job.stopper import JobStopper
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class JobStopperInitTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_init(self):
        stopper = JobStopper(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        self.assertEqual(stopper.job_id,
                         os.path.basename(self.work_dir))


class TerminateProcessGracefullyTest(DataJuicerTestCaseBase):
    """Uses mock psutil.Process — can't create/kill real processes in tests."""

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()
        self.stopper = JobStopper(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_graceful_termination(self):
        proc = MagicMock(spec=psutil.Process)
        proc.pid = 12345
        proc.wait.return_value = None
        result = self.stopper.terminate_process_gracefully(proc, timeout=5)
        self.assertTrue(result)
        proc.terminate.assert_called_once()
        proc.kill.assert_not_called()

    def test_force_kill_on_timeout(self):
        proc = MagicMock(spec=psutil.Process)
        proc.pid = 12345
        proc.wait.side_effect = [psutil.TimeoutExpired(5), None]
        result = self.stopper.terminate_process_gracefully(proc, timeout=1)
        self.assertTrue(result)
        proc.kill.assert_called_once()

    def test_already_terminated(self):
        proc = MagicMock(spec=psutil.Process)
        proc.pid = 12345
        proc.terminate.side_effect = psutil.NoSuchProcess(12345)
        result = self.stopper.terminate_process_gracefully(proc)
        self.assertTrue(result)

    def test_access_denied(self):
        proc = MagicMock(spec=psutil.Process)
        proc.pid = 12345
        proc.terminate.side_effect = psutil.AccessDenied(12345)
        result = self.stopper.terminate_process_gracefully(proc)
        self.assertFalse(result)


class CleanupJobResourcesTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_updates_job_summary(self):
        summary = {'status': 'running', 'start_time': 1000.0}
        with open(os.path.join(self.work_dir, 'job_summary.json'), 'w') as f:
            json.dump(summary, f)

        stopper = JobStopper(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        stopper.cleanup_job_resources()

        with open(os.path.join(self.work_dir, 'job_summary.json')) as f:
            updated = json.load(f)
        self.assertEqual(updated['status'], 'stopped')
        self.assertEqual(updated['stop_reason'], 'manual_stop')
        self.assertIn('stop_time', updated)

    def test_no_summary_no_error(self):
        stopper = JobStopper(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        stopper.cleanup_job_resources()


class StopJobIntegrationTest(DataJuicerTestCaseBase):

    def setUp(self):
        super().setUp()
        self.work_dir = tempfile.mkdtemp()

    def tearDown(self):
        os.system(f'rm -rf {self.work_dir}')
        super().tearDown()

    def test_stop_job_no_processes(self):
        with open(os.path.join(self.work_dir, 'events.jsonl'), 'w') as f:
            f.write(json.dumps({
                'event_type': 'job_start',
                'process_id': 99999999,
                'thread_id': 88888888,
            }) + '\n')
        with open(os.path.join(self.work_dir, 'job_summary.json'), 'w') as f:
            json.dump({'status': 'running'}, f)

        stopper = JobStopper(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        result = stopper.stop_job()
        self.assertEqual(result['processes_found'], 1)
        self.assertEqual(result['processes_terminated'], 0)

    def test_stop_job_no_events(self):
        with open(os.path.join(self.work_dir, 'job_summary.json'), 'w') as f:
            json.dump({'status': 'running'}, f)

        stopper = JobStopper(
            os.path.basename(self.work_dir),
            base_dir=os.path.dirname(self.work_dir),
        )
        result = stopper.stop_job()
        self.assertFalse(result['success'])
        self.assertIn('No process or thread IDs found', result['errors'][0])


if __name__ == '__main__':
    unittest.main()
