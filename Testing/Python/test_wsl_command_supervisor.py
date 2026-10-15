"""Real owned-process cleanup tests; these do not claim native WSL acceptance."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/wsl/run_command.py'


@unittest.skipUnless(sys.platform.startswith('linux'), 'Real process-group test requires Linux')
class WslCommandSupervisorTest(unittest.TestCase):
    def alive(self, pid):
        try:
            return Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()[0] != 'Z'
        except FileNotFoundError:
            return False

    def run_case(self, early_exit):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            heartbeat, pidfile = root / 'heartbeat', root / 'child'
            heartbeat.touch()
            code = ('import subprocess,sys,time; from pathlib import Path; '
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]); '
                    f'Path({str(pidfile)!r}).write_text(str(p.pid)); '
                    + ('sys.exit(0)' if early_exit else 'time.sleep(60)'))
            unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
            process = subprocess.Popen([sys.executable, str(SCRIPT), '--heartbeat', str(heartbeat),
                                        '--timeout-seconds', '0.8', '--', sys.executable, '-c', code])
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(pidfile.is_file())
                child = int(pidfile.read_text())
                if not early_exit:
                    heartbeat.unlink()
                self.assertEqual(process.wait(timeout=10), 0 if early_exit else 130)
                deadline = time.monotonic() + 2
                while self.alive(child) and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertFalse(self.alive(child))
                self.assertIsNone(unrelated.poll())
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_expired_bridge_cancels_linux_descendants_only(self):
        self.run_case(False)

    def test_exited_launcher_does_not_leave_linux_descendants(self):
        self.run_case(True)

    def test_missing_heartbeat_fails_before_launch(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--heartbeat', '/missing/heartbeat',
                                 '--', sys.executable, '-c', 'raise AssertionError("must not run")'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'heartbeat is missing', result.stderr)
