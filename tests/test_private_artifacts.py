import os
import subprocess
import unittest
from unittest.mock import patch

from src.output.artifact_manager import ArtifactManager


class PrivateArtifactTests(unittest.TestCase):
    def test_default_manager_does_not_apply_acl(self):
        manager = ArtifactManager(base_dir=".test_private_artifacts")
        with patch.object(manager, "_apply_private_acl") as apply_acl:
            manager.resolve_task_dir("normal")
        apply_acl.assert_not_called()

    def test_private_context_dir_uses_the_same_protection_path(self):
        manager = ArtifactManager(base_dir=".test_private_artifacts", private_artifacts=True)
        with patch.object(manager, "_apply_private_acl") as apply_acl:
            manager.resolve_context_dir("private")
        self.assertEqual(apply_acl.call_count, 2)
        apply_acl.assert_any_call(os.path.abspath(".test_private_artifacts/private"))
        apply_acl.assert_any_call(os.path.abspath(".test_private_artifacts/private/context"))

    @patch("src.output.artifact_manager.os.name", "nt")
    @patch("src.output.artifact_manager.subprocess.run")
    def test_private_manager_applies_current_user_and_system_acl(self, run):
        run.side_effect = [
            subprocess.CompletedProcess(["whoami"], 0, "DOMAIN\\user\n", ""),
            subprocess.CompletedProcess(["icacls"], 0, "", ""),
        ]
        manager = ArtifactManager(base_dir=".test_private_artifacts", private_artifacts=True)
        manager.resolve_task_dir("private")
        icacls = run.call_args_list[1].args[0]
        self.assertIn("/inheritance:r", icacls)
        self.assertIn("DOMAIN\\user:(OI)(CI)F", icacls)
        self.assertIn("SYSTEM:(OI)(CI)F", icacls)

    @patch("src.output.artifact_manager.os.chmod")
    @patch("src.output.artifact_manager.os.name", "posix")
    def test_private_manager_uses_owner_only_mode_on_posix(self, chmod):
        manager = ArtifactManager(base_dir=".test_private_artifacts", private_artifacts=True)
        manager.resolve_task_dir("private")
        chmod.assert_called_once_with(
            os.path.abspath(".test_private_artifacts/private"), 0o700
        )

    @patch("src.output.artifact_manager.os.name", "unsupported")
    def test_private_manager_fails_closed_on_unknown_platform(self):
        manager = ArtifactManager(base_dir=".test_private_artifacts", private_artifacts=True)
        with self.assertRaisesRegex(RuntimeError, "Windows, macOS, and Linux"):
            manager.resolve_task_dir("private")
