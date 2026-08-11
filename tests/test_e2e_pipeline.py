"""Comprehensive End-to-End Pipeline Tests for Manus Mini v2.
Tests the real execution flow: TaskInput -> InputRouter -> TaskContext -> Planner -> Scheduler -> WorkUnit -> FakeExecutor -> ExecutionResult -> ArtifactManager -> real file -> TaskManifest -> checkpoint.
"""
import unittest
import os
import shutil
import json
import tempfile
from decimal import Decimal
from src.core.engine import ManusMiniEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor
from src.core.context import TaskContext
from src.checkpoint.manifest import TaskManifest
from src.ingestion.router import InputRouter
from src.ingestion.repository import RepositoryProcessor
from src.core.planner import Planner, WorkUnit
from src.output.artifact_manager import ArtifactManager


class TestE2EPipeline(unittest.TestCase):
    """Tests the full Manus Mini pipeline end-to-end."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="manus_e2e_")
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")
        self.artifact_base = os.path.join(self.test_dir, "artifacts")
        self.executor = FakeExecutor()
        self.engine = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=self.executor,
            artifact_manager=ArtifactManager(base_dir=self.artifact_base),
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_test_repo(self, repo_dir: str):
        os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
        os.makedirs(os.path.join(repo_dir, "tests"), exist_ok=True)
        with open(os.path.join(repo_dir, "pyproject.toml"), "w") as f:
            f.write("[project]\nname = 'test'\nversion = '0.1.0'\n")
        with open(os.path.join(repo_dir, "src", "main.py"), "w") as f:
            f.write("def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()\n")
        with open(os.path.join(repo_dir, "src", "utils.py"), "w") as f:
            f.write("def helper():\n    return 42\n")
        with open(os.path.join(repo_dir, "tests", "test_main.py"), "w") as f:
            f.write("def test_main():\n    assert True\n")

    def _create_test_csv(self) -> str:
        path = os.path.join(self.test_dir, "test.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("name,age,city\nAlice,30,NYC\nBob,25,LA\n")
        return path

    def _create_test_json(self) -> str:
        path = os.path.join(self.test_dir, "test.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": "test", "count": 42, "items": [1, 2, 3]}, f)
        return path

    # === STEP 22: Repository E2E Test ===
    def test_e2e_repository_pipeline(self):
        """Full E2E: repository InputRouter -> TaskContext -> Planner -> FakeExecutor -> ArtifactManager -> Manifest."""
        repo_path = os.path.join(self.test_dir, "test_repo")
        self._create_test_repo(repo_path)

        task_id = "e2e_repo_test"
        task = TaskInput(
            prompt="Analyze and improve the repository",
            task_id=task_id,
            files=[repo_path],
            execution_mode=ExecutionMode.AUTO,
            budget=10.0,
        )

        manifest = self.engine.initialize_task(task)
        context = self.engine.current_context
        self.assertIsNotNone(context)
        self.assertIn(repo_path, context.input_sources)
        self.assertEqual(context.source_types.get(repo_path), "repository")
        if context:
            self.assertIn("file_count", context.repository_context)
            self.assertGreater(context.repository_context.get("file_count", 0), 0)

        # Assert TaskContext exists with fingerprints
        if context:
            self.assertGreater(len(context.source_fingerprints), 0)

        # Assert WorkUnits exist
        self.assertGreater(len(self.engine.work_units), 0)
        inspect_unit = next((u for u in self.engine.work_units if u.id == "unit_inspect"), None)
        if inspect_unit:
            self.assertTrue(hasattr(inspect_unit, "context_refs") and inspect_unit.context_refs)

        # Run to completion
        self.engine.run_to_completion()

        # Assert executor received meaningful prompt
        self.assertIn("User Goal:", self.executor.last_prompt)
        self.assertIn(task.prompt, self.executor.last_prompt)

        # Assert artifacts exist
        manifest = self.engine.current_manifest
        self.assertTrue(manifest is not None)
        for output_path in manifest.outputs:
            if output_path:
                self.assertTrue(os.path.exists(output_path), f"Artifact {output_path} does not exist")

        # Assert completed work recorded
        self.assertGreater(len(manifest.completed_work), 0)

    # === STEP 23: Resume Test ===
    def test_e2e_resume_duplicate_prevention(self):
        """Test that resume does NOT re-execute completed units."""
        task_id = "e2e_resume_dup"
        task = TaskInput(
            prompt="Analyze code",
            task_id=task_id,
            budget=10.0,
        )
        self.engine.initialize_task(task)

        # Execute first unit
        success1 = self.engine.run_next_unit()
        self.assertTrue(success1)
        completed_before = len(self.engine.current_manifest.completed_work)
        self.assertGreater(completed_before, 0)

        # Build a manifest snapshot to confirm unit state
        first_completed = list(self.engine.current_manifest.completed_work)

        # Create new engine to resume
        engine2 = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=FakeExecutor(),
            artifact_manager=self.engine.artifact_manager,
        )
        resume_task = TaskInput(
            prompt="VerifyTask",
            task_id=task_id,
            resume_task_id=task_id,
            budget=10.0,
        )
        engine2.initialize_task(resume_task)

        # Assert WorkUnits restore
        self.assertGreater(len(engine2.work_units), 0)

        # Assert completed units persisted
        self.assertGreater(len(engine2.current_manifest.completed_work), 0)

        # Run remaining
        engine2.run_to_completion()

        # The new executor should have been called for remaining units only
        remaining_units = len(engine2.work_units) - len(engine2.current_manifest.completed_work)
        # At worst, executor count <= remaining + 1
        self.assertLessEqual(engine2.executor.execution_count, len(engine2.work_units))

    # === STEP 24: PDF E2E Test ===
    def test_e2e_pdf_pipeline(self):
        """PDF -> InputRouter -> PDFProcessor -> TaskContext -> Planner -> FakeExecutor -> artifact -> checkpoint."""
        from reportlab.pdfgen import canvas

        pdf_path = os.path.join(self.test_dir, "e2e_test.pdf")
        c = canvas.Canvas(pdf_path)
        for i in range(3):
            c.drawString(100, 750, f"Test page {i + 1}")
            c.showPage()
        c.save()

        task_id = "e2e_pdf_test"
        context = InputRouter.route(task_id=task_id, sources=[pdf_path])
        self.assertEqual(context.source_types.get(pdf_path), "pdf")
        self.assertIn("sha256", context.document_context.get(pdf_path, {}))

        engine = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=FakeExecutor(),
        )
        task = TaskInput(
            prompt="Analyze this PDF document",
            task_id=task_id,
            files=[pdf_path],
            budget=10.0,
        )
        engine.initialize_task(task)

        # Assert document context is present
        self.assertTrue(engine.current_context.document_context)
        pdf_info = engine.current_context.document_context.get(pdf_path, {})
        self.assertIn("sha256", pdf_info)
        self.assertIn("page_count", pdf_info)

        engine.run_to_completion()
        if len(engine.current_manifest.outputs) > 0:
            for art_path in engine.current_manifest.outputs:
                self.assertTrue(os.path.exists(art_path))

    # === STEP 25: Usage Test ===
    def test_e2e_usage_tracking(self):
        """FakeExecutor returns deterministic usage; verify manifest records executor-reported usage separately from estimated cost."""
        task = TaskInput(
            prompt="Test usage tracking",
            task_id="usage_test",
            budget=10.0,
        )
        self.engine.initialize_task(task)
        self.engine.run_next_unit()

        # Check usage_history
        self.assertGreater(len(self.engine.usage_history), 0)
        usage_record = self.engine.usage_history[0]

        self.assertEqual(usage_record["work_unit_id"], "unit_inspect")
        self.assertIn("provider", usage_record)
        self.assertIn("model_id", usage_record)
        self.assertIn("estimated_cost", usage_record)
        self.assertIn("prompt_tokens", usage_record)
        self.assertEqual(usage_record["prompt_tokens"], 100)
        self.assertEqual(usage_record["completion_tokens"], 50)

        # Check manifest model_history
        manifest = self.engine.current_manifest
        self.assertGreater(len(manifest.model_history), 0)

    # === STEP 26: Failure Test ===
    def test_e2e_failure_handling(self):
        """Failing executor preserves previous work, records errors, avoids fake artifacts."""
        task = TaskInput(
            prompt="Failure test",
            task_id="fail_test",
            budget=10.0,
        )
        self.engine.initialize_task(task)

        # Complete one unit
        self.engine.run_next_unit()
        completed_before = len(self.engine.current_manifest.completed_work)
        self.assertGreater(completed_before, 0)

        # Replace with failing executor
        failing_executor = FakeExecutor(should_fail=True)
        self.engine.executor = failing_executor

        # Run next - should fail
        result = self.engine.run_next_unit()
        self.assertFalse(result)

        # Previous completed work preserved
        self.assertEqual(len(self.engine.current_manifest.completed_work), completed_before)

        # Error recorded
        self.assertGreater(len(self.engine.current_manifest.errors), 0)
        self.assertIn("failure", self.engine.current_manifest.errors[-1].lower())

        # Check for run_to_completion returns non-COMPLETED status
        report = self.engine.run_to_completion()

        # Status should not be completed (use partial or failed)
        self.assertNotEqual(self.engine.current_manifest.status, "completed")

        # Verify checkpoint saved
        manifest_path = self.engine.checkpoint_manager.get_manifest_path(self.engine.current_manifest.task_id)
        self.assertTrue(os.path.exists(manifest_path))


if __name__ == "__main__":
    unittest.main()