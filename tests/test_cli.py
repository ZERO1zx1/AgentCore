"""Integration tests for AgentCore CLI runner."""

import unittest
from unittest.mock import patch
import sys
import os
import json
from io import StringIO

from src.cli.main import main


class TestCLI(unittest.TestCase):
    def test_cli_help(self):
        with patch.object(sys, "argv", ["agentcore", "--help"]), patch("sys.stdout", new_callable=StringIO) as mock_out:
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("AgentCore", mock_out.getvalue())

    def test_cli_list_command(self):
        # Ensure the checkpoints directory exists so this test is deterministic
        # regardless of prior state (a clean checkout has no .agentcore/checkpoints).
        os.makedirs(".agentcore/checkpoints", exist_ok=True)
        with patch.object(sys, "argv", ["agentcore", "list"]), patch("sys.stdout", new_callable=StringIO) as mock_out:
            main()
            self.assertIn("Checkpoint", mock_out.getvalue())

    def test_cli_run_fake_command(self):
        with patch.object(sys, "argv", [
            "agentcore", "run",
            "--prompt", "CLI test prompt",
            "--budget", "2.0",
            "--provider", "fake",
            "--task-id", "cli_test_task_01",
        ]), patch("sys.stdout", new_callable=StringIO) as mock_out:
            main()
            out = mock_out.getvalue()
            self.assertIn("Initializing AgentCore Task", out)
            self.assertIn("Execution Finished", out)

    def test_cli_resume_uses_persisted_prompt(self):
        task_id = "cli_resume_contract_01"
        with patch.object(sys, "argv", [
            "agentcore", "run", "--prompt", "Resume contract prompt",
            "--provider", "fake", "--task-id", task_id,
        ]), patch("sys.stdout", new_callable=StringIO):
            main()

        with patch.object(sys, "argv", ["agentcore", "resume", task_id, "--provider", "fake"]), patch(
            "sys.stdout", new_callable=StringIO
        ) as mock_out:
            main()
            self.assertIn("Resumed task finished", mock_out.getvalue())

    def test_cli_observe_records_terminal_command_for_dashboard(self):
        with patch.object(sys, "argv", [
            "agentcore", "observe", "--title", "Terminal command test", "--",
            sys.executable, "-c", "print('visible to dashboard')",
        ]), patch("sys.stdout", new_callable=StringIO) as mock_out:
            main()
            self.assertIn("бүртгэгдлээ", mock_out.getvalue())

if __name__ == "__main__":
    unittest.main()
