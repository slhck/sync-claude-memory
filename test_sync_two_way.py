import contextlib
import io
import subprocess
import unittest
from pathlib import Path
from unittest import mock

import sync_two_way as two_way


class TwoWaySyncTest(unittest.TestCase):
    def test_transfers_run_claude_before_codex_with_opposite_mappings(self):
        commands = two_way.transfer_commands(
            "test-host", 2222, Path("/Users/a"), Path("/home/a"), True
        )
        self.assertEqual(len(commands), 4)
        for index, (_, command) in enumerate(commands):
            self.assertIn("--dry-run", command)
            self.assertNotIn("--delete", command)
            self.assertIn("--target-ssh" if index % 2 == 0 else "--source-ssh", command)
            self.assertIn(
                "/Users/a=/home/a" if index % 2 == 0 else "/home/a=/Users/a", command
            )
            self.assertEqual("--create-projects" in command, index >= 2)
            self.assertEqual(
                command[command.index("--direction") + 1],
                "claude-to-codex" if index < 2 else "codex-to-claude",
            )

    def test_stops_after_failed_transfer(self):
        with (
            mock.patch("sys.argv", ["sync_two_way.py", "test-host"]),
            mock.patch.object(
                two_way.sync, "remote_home", return_value=Path("/home/a")
            ),
            mock.patch.object(
                two_way.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 1),
            ) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(two_way.main(), 1)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
