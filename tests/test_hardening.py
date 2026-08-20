import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.budget.state import BudgetManager
from src.checkpoint.manager import CheckpointManager
from src.checkpoint.manifest import TaskManifest
from src.core.engine import AgentCoreEngine
from src.core.executor import FakeExecutor
from src.core.task import TaskInput
from src.ingestion.router import InputRouter
from src.models.router import ModelRouter
from src.output.artifact_manager import ArtifactManager
from src.core.notifications import GitManager


class HardeningTest(unittest.TestCase):
    def test_missing_pdf_dependency_returns_blocked_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder) / "input.pdf"; pdf.write_bytes(b"%PDF-1.4")
            engine = AgentCoreEngine(checkpoint_dir=str(Path(folder)/"checkpoints"), artifact_manager=ArtifactManager(str(Path(folder)/"tasks")), repo_root=folder)
            with patch("src.ingestion.pdf.pypdf", None):
                manifest = engine.initialize_task(TaskInput(prompt="inspect pdf", task_id="pdf-blocked", files=[str(pdf)]))
            self.assertEqual(manifest.status, "BLOCKED")
            self.assertEqual(manifest.reason, "DEPENDENCY_UNAVAILABLE")
            self.assertIn("pypdf dependency unavailable", manifest.errors[0])

    def test_model_router_honors_execution_mode(self):
        router = ModelRouter()
        full = router.get_model_for_task("analyze", "NORMAL", ["text"], "FULL")
        safe = router.get_model_for_task("analyze", "NORMAL", ["text"], "CREDIT_SAFE")
        self.assertEqual(full.tier, "tier2")
        self.assertEqual(safe.tier, "tier1")

    def test_git_stages_only_explicit_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/".git").mkdir(); checkpoint=root/".agentcore"/"checkpoints"/"t_manifest.json"; checkpoint.parent.mkdir(parents=True); checkpoint.write_text("{}")
            with patch("src.core.notifications.subprocess.run") as run:
                run.return_value.returncode = 0
                self.assertTrue(GitManager(folder).stage_checkpoint(str(checkpoint)))
                args = run.call_args.args[0]
            self.assertEqual(args[:3], ["git", "add", "--"])
            self.assertEqual(args[3].replace("\\", "/"), ".agentcore/checkpoints/t_manifest.json")

    def test_git_rejects_checkpoint_outside_repository(self):
        with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as external:
            self.assertFalse(GitManager(repo).stage_checkpoint(str(Path(external)/"manifest.json")))

    def test_checkpoint_retention_keeps_newest(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = CheckpointManager(folder, max_manifests=2)
            first = manager.save_checkpoint(TaskManifest("one", "text", []))
            second = manager.save_checkpoint(TaskManifest("two", "text", []))
            third = manager.save_checkpoint(TaskManifest("three", "text", []))
            self.assertFalse(Path(first).exists())
            self.assertTrue(Path(second).exists())
            self.assertTrue(Path(third).exists())

    def test_router_creates_context_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            text = Path(folder)/"input.txt"; text.write_text("hello", encoding="utf-8")
            context_dir = Path(folder)/"nested"/"context"
            InputRouter.route("t", [str(text)], context_dir=str(context_dir))
            self.assertTrue(context_dir.is_dir())
            self.assertTrue(any(context_dir.iterdir()))

    def test_budget_snapshot_matches_charged_state(self):
        manager = BudgetManager(initial_budget=10)
        snapshot = manager.record_usage_snapshot("2.5")
        self.assertEqual(snapshot["used"], 2.5)
        self.assertEqual(snapshot["remaining"], 7.5)

    def test_fake_executor_uses_canonical_usage_keys(self):
        result = FakeExecutor().execute("test", "fake-local", "prompt")
        self.assertEqual(result.usage, {"input_tokens":100, "output_tokens":50, "total_tokens":150})


if __name__ == "__main__": unittest.main()
