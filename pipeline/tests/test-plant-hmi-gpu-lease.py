"""Unit tests for the GPU lease shared by the Plant HMI batch start and the realism
loop (plan Bước 1): acquire/release, refusal of a second owner, stale-on-dead-pid
expiry, the pid-reuse guard (mocked start time) and a real concurrent-acquire race
between two OS processes (only one may win the flock).

Run: .venv/bin/python tests/test-plant-hmi-gpu-lease.py
"""
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plant_hmi import plant_gpu_lease as lease  # noqa: E402


class GpuLeaseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(lease, "CONTROL_DIR", d),
            mock.patch.object(lease, "LEASE_PATH", d / "gpu-lease.json"),
            mock.patch.object(lease, "LOCK_PATH", d / "gpu-lease.lock"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def _sleeper(self):
        """A real, cheap child process this test can treat as a live pid."""
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.addCleanup(lambda: (proc.kill(), proc.wait()))
        time.sleep(0.2)  # let /proc/<pid>/stat exist before the test reads it
        return proc.pid


class AcquireReleaseTests(GpuLeaseTestCase):
    def test_acquire_then_current_then_release(self):
        pid = self._sleeper()
        ok, holder = lease.acquire("owner-a", "test cycle", pid)
        self.assertTrue(ok)
        self.assertIsNone(holder)
        cur = lease.current()
        self.assertEqual(cur["owner"], "owner-a")
        self.assertEqual(cur["purpose"], "test cycle")
        self.assertEqual(cur["pid"], pid)
        lease.release("owner-a")
        self.assertIsNone(lease.current())

    def test_same_owner_reacquire_refreshes_record(self):
        pid = self._sleeper()
        self.assertTrue(lease.acquire("owner-a", "first", pid)[0])
        ok, holder = lease.acquire("owner-a", "second", pid)
        self.assertTrue(ok)
        self.assertIsNone(holder)
        self.assertEqual(lease.current()["purpose"], "second")

    def test_second_owner_refused_with_holder_info(self):
        pid = self._sleeper()
        self.assertTrue(lease.acquire("owner-a", "holds it", pid)[0])
        ok, holder = lease.acquire("owner-b", "wants it", pid)
        self.assertFalse(ok)
        self.assertEqual(holder["owner"], "owner-a")
        self.assertEqual(holder["purpose"], "holds it")

    def test_release_by_non_owner_is_a_noop(self):
        pid = self._sleeper()
        self.assertTrue(lease.acquire("owner-a", "x", pid)[0])
        lease.release("owner-b")
        self.assertIsNotNone(lease.current())
        self.assertEqual(lease.current()["owner"], "owner-a")

    def test_acquire_with_dead_pid_is_refused(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        ok, holder = lease.acquire("owner-a", "x", proc.pid)
        self.assertFalse(ok)
        self.assertIsNone(holder)
        self.assertIsNone(lease.current())


class StaleLeaseTests(GpuLeaseTestCase):
    def test_lease_on_dead_pid_is_stale_and_can_be_reacquired(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()  # dies immediately
        with mock.patch("plant_hmi.plant_host_readers.process_start_ts", return_value=123.0):
            lease._write({"owner": "owner-a", "purpose": "crashed", "pid": proc.pid,
                          "start_ts": 123.0, "ts": time.time()})
        self.assertIsNone(lease.current())  # dead pid: stale
        pid = self._sleeper()
        ok, holder = lease.acquire("owner-b", "fresh", pid)
        self.assertTrue(ok)
        self.assertIsNone(holder)

    def test_pid_reuse_guard_rejects_stale_start_time(self):
        """A live pid whose recorded start_ts no longer matches its ACTUAL start
        time (the original owner died and the pid number was reused by an
        unrelated process) must be treated as stale, not as a live holder."""
        pid = self._sleeper()
        lease._write({"owner": "owner-a", "purpose": "old process", "pid": pid,
                      "start_ts": 1.0, "ts": time.time()})  # fabricated, far from reality
        self.assertIsNone(lease.current())
        ok, holder = lease.acquire("owner-b", "new", pid)
        self.assertTrue(ok)
        self.assertIsNone(holder)


def _race_worker(control_dir, lease_path, lock_path, owner, barrier, result_queue):
    """Runs in a separate OS process: patches the module-level paths the same
    way the parent test does, waits at a barrier so both workers call acquire()
    as close to simultaneously as possible, then reports what happened."""
    from plant_hmi import plant_gpu_lease as child_lease
    child_lease.CONTROL_DIR = Path(control_dir)
    child_lease.LEASE_PATH = Path(lease_path)
    child_lease.LOCK_PATH = Path(lock_path)
    barrier.wait()
    ok, holder = child_lease.acquire(owner, "race", os.getpid())
    result_queue.put((owner, ok, holder))


class ConcurrentAcquireTests(GpuLeaseTestCase):
    def test_only_one_of_two_processes_wins_the_lease(self):
        ctx = multiprocessing.get_context("spawn")
        barrier = ctx.Barrier(2)
        q = ctx.Queue()
        args_a = (str(lease.CONTROL_DIR), str(lease.LEASE_PATH), str(lease.LOCK_PATH), "proc-a", barrier, q)
        args_b = (str(lease.CONTROL_DIR), str(lease.LEASE_PATH), str(lease.LOCK_PATH), "proc-b", barrier, q)
        pa = ctx.Process(target=_race_worker, args=args_a)
        pb = ctx.Process(target=_race_worker, args=args_b)
        pa.start()
        pb.start()
        pa.join(timeout=10)
        pb.join(timeout=10)
        results = [q.get(timeout=1), q.get(timeout=1)]
        winners = [r for r in results if r[1]]
        losers = [r for r in results if not r[1]]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(len(losers), 1, results)
        self.assertEqual(losers[0][2]["owner"], winners[0][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
