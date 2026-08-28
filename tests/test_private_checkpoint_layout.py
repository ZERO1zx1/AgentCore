import os
import unittest

from src.checkpoint.manager import CheckpointManager


class PrivateCheckpointLayoutTests(unittest.TestCase):
    def test_private_checkpoint_is_stored_under_its_task(self):
        manager = CheckpointManager(private_task_root=".agentcore/tasks")
        self.assertEqual(
            manager.get_manifest_path("task/one"),
            os.path.join(".agentcore/tasks", "one", "checkpoints", "one_manifest.json"),
        )
