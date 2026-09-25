#!/usr/bin/env python3
"""Tests for shared/process_group.py's launch/kill helpers."""

from __future__ import annotations

import os
import signal
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.process_group import grouped_launch_command, kill_process_tree


class GroupedLaunchCommandTest(unittest.TestCase):
    def test_prefixes_with_setsid_when_available_on_posix(self) -> None:
        with mock.patch("shared.process_group.os.name", "posix"), mock.patch(
            "shared.process_group.shutil.which", return_value="/usr/bin/setsid"
        ):
            program, args, grouped = grouped_launch_command("/usr/bin/python3", ["-m", "pipeline"])

        self.assertEqual(program, "/usr/bin/setsid")
        self.assertEqual(args, ["/usr/bin/python3", "-m", "pipeline"])
        self.assertTrue(grouped)

    def test_leaves_command_unchanged_when_setsid_is_unavailable(self) -> None:
        with mock.patch("shared.process_group.os.name", "posix"), mock.patch(
            "shared.process_group.shutil.which", return_value=None
        ):
            program, args, grouped = grouped_launch_command("/usr/bin/python3", ["-m", "pipeline"])

        self.assertEqual(program, "/usr/bin/python3")
        self.assertEqual(args, ["-m", "pipeline"])
        self.assertFalse(grouped)

    def test_leaves_command_unchanged_on_windows(self) -> None:
        with mock.patch("shared.process_group.os.name", "nt"):
            program, args, grouped = grouped_launch_command("C:/Python/python.exe", ["-m", "pipeline"])

        self.assertEqual(program, "C:/Python/python.exe")
        self.assertEqual(args, ["-m", "pipeline"])
        self.assertFalse(grouped)


class KillProcessTreeTest(unittest.TestCase):
    def test_windows_uses_taskkill_with_tree_flag(self) -> None:
        with mock.patch("shared.process_group.subprocess.run") as mock_run:
            kill_process_tree(4242, grouped=False, force=False, platform_name="Windows")
        mock_run.assert_called_once()
        command = mock_run.call_args.args[0]
        self.assertEqual(command, ["taskkill", "/PID", "4242", "/T"])

    def test_windows_force_adds_f_flag(self) -> None:
        with mock.patch("shared.process_group.subprocess.run") as mock_run:
            kill_process_tree(4242, grouped=False, force=True, platform_name="Windows")
        command = mock_run.call_args.args[0]
        self.assertEqual(command, ["taskkill", "/PID", "4242", "/T", "/F"])

    def test_posix_grouped_uses_killpg_when_pid_is_group_leader(self) -> None:
        with mock.patch("shared.process_group.os.getpgid", return_value=555), mock.patch(
            "shared.process_group.os.killpg"
        ) as mock_killpg:
            kill_process_tree(555, grouped=True, force=False, platform_name="Linux")
        mock_killpg.assert_called_once_with(555, signal.SIGTERM)

    def test_posix_grouped_force_sends_sigkill(self) -> None:
        with mock.patch("shared.process_group.os.getpgid", return_value=555), mock.patch(
            "shared.process_group.os.killpg"
        ) as mock_killpg:
            kill_process_tree(555, grouped=True, force=True, platform_name="Linux")
        mock_killpg.assert_called_once_with(555, signal.SIGKILL)

    def test_posix_falls_back_to_os_kill_when_not_grouped(self) -> None:
        with mock.patch("shared.process_group.os.kill") as mock_kill:
            kill_process_tree(555, grouped=False, force=False, platform_name="Linux")
        mock_kill.assert_called_once_with(555, signal.SIGTERM)

    def test_posix_falls_back_to_os_kill_when_pid_is_not_the_group_leader(self) -> None:
        # grouped=True but the pid is not itself the process-group leader
        # (os.getpgid(pid) != pid): fall back rather than killpg-ing a group
        # this pid does not actually lead.
        with mock.patch("shared.process_group.os.getpgid", return_value=999), mock.patch(
            "shared.process_group.os.killpg"
        ) as mock_killpg, mock.patch("shared.process_group.os.kill") as mock_kill:
            kill_process_tree(555, grouped=True, force=False, platform_name="Linux")
        mock_killpg.assert_not_called()
        mock_kill.assert_called_once_with(555, signal.SIGTERM)

    def test_ignores_process_lookup_error(self) -> None:
        with mock.patch("shared.process_group.os.kill", side_effect=ProcessLookupError):
            kill_process_tree(555, grouped=False, force=False, platform_name="Linux")  # must not raise

    def test_non_positive_pid_is_a_no_op(self) -> None:
        with mock.patch("shared.process_group.subprocess.run") as mock_run, mock.patch(
            "shared.process_group.os.kill"
        ) as mock_kill:
            kill_process_tree(0, grouped=False, force=False, platform_name="Windows")
            kill_process_tree(-1, grouped=False, force=False, platform_name="Linux")
        mock_run.assert_not_called()
        mock_kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
